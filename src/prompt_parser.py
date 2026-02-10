import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import re
from urllib.parse import urlparse

from config import InterceptedPrompt, Config
from rich.console import Console

console = Console()

class PromptParser:
    """Extract and parse AI prompts from intercepted HTTP requests"""
    
    def __init__(self):
        self.ai_patterns = Config.get_monitored_patterns()
    
    # ── Windsurf-specific endpoint patterns ──
    WINDSURF_ENDPOINTS = [
        "SendUserCascadeMessage",
        "LanguageServerService",
        "exa.language_server_pb",
    ]

    def is_ai_request(self, url: str, body: str, headers: Dict[str, str]) -> bool:
        """Check if the request is an AI API call"""
        url_lower = url.lower()
        body_lower = body.lower() if body else ""
        user_agent = headers.get('user-agent', '').lower()
        
        # ── Windsurf local language server (highest priority) ──
        for ep in self.WINDSURF_ENDPOINTS:
            if ep.lower() in url_lower:
                return True
        
        # Check URL patterns
        for pattern in self.ai_patterns:
            if pattern.lower() in url_lower:
                return True
        
        # Check for AI-related keywords in body
        ai_keywords = [
            'messages', 'prompt', 'completion', 'chat', 'model', 'gpt', 'claude',
            'temperature', 'max_tokens', 'stream', 'assistant', 'user', 'system'
        ]
        
        for keyword in ai_keywords:
            if keyword in body_lower:
                return True
        
        # Check User-Agent for IDE/editor patterns
        ide_patterns = ['windsurf', 'cursor', 'vscode', 'electron', 'copilot']
        for pattern in ide_patterns:
            if pattern in user_agent:
                return True
                
        return False
    
    def extract_prompt_from_request(self, url: str, method: str, body: str, 
                                  headers: Dict[str, str]) -> Optional[InterceptedPrompt]:
        """Extract prompt data from HTTP request"""
        
        if not self.is_ai_request(url, body, headers):
            return None
        
        try:
            # Parse JSON body
            data = json.loads(body) if body else {}
            
            # Extract messages/prompt
            messages = []
            prompt_text = ""
            
            # ── Windsurf Cascade format (SendUserCascadeMessage) ──
            if 'cascadeId' in data and 'items' in data:
                return self._parse_windsurf_cascade(data, url, method, headers)
            
            # Standard OpenAI/Anthropic format
            elif 'messages' in data:
                messages = data['messages']
                # Find the latest user message
                for msg in reversed(messages):
                    if msg.get('role') == 'user':
                        prompt_text = msg.get('content', '')
                        break
            
            # Direct prompt field
            elif 'prompt' in data:
                prompt_text = data['prompt']
                messages = [{'role': 'user', 'content': prompt_text}]
            
            # Codeium format
            elif 'query' in data or 'text' in data:
                prompt_text = data.get('query', data.get('text', ''))
                messages = [{'role': 'user', 'content': prompt_text}]
            
            # Extract metadata
            metadata = {
                'model': data.get('model', ''),
                'temperature': data.get('temperature'),
                'max_tokens': data.get('max_tokens'),
                'stream': data.get('stream', False),
                'content_type': headers.get('content-type', ''),
                'authorization_present': 'authorization' in headers,
                'request_size': len(body) if body else 0
            }
            
            # Detect source application
            source = self._detect_source(headers.get('user-agent', ''), url)
            
            return InterceptedPrompt(
                id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                source=source,
                user_agent=headers.get('user-agent', ''),
                url=url,
                method=method,
                prompt=prompt_text,
                messages=messages,
                response=None,  # Will be filled when response is intercepted
                metadata=metadata
            )
            
        except json.JSONDecodeError:
            console.print(f"[yellow]Failed to parse JSON body for URL: {url}[/yellow]")
            return None
        except Exception as e:
            console.print(f"[red]Error extracting prompt: {e}[/red]")
            return None
    
    def _parse_windsurf_cascade(self, data: dict, url: str, method: str,
                                 headers: Dict[str, str]) -> Optional[InterceptedPrompt]:
        """Parse Windsurf's SendUserCascadeMessage format.
        
        Body shape:
        {
          "cascadeId": "...",
          "items": [{"text": "user prompt here"}, ...],
          "metadata": {"apiKey": "...", "ideName": "windsurf", ...},
          "cascadeConfig": {
            "plannerConfig": {
              "requestedModelUid": "MODEL_SWE_1_5_SLOW",
              ...
            }, ...
          }
        }
        """
        # Extract prompt text from items
        items = data.get('items', [])
        prompt_parts = []
        for item in items:
            if isinstance(item, dict) and 'text' in item:
                prompt_parts.append(item['text'])
            elif isinstance(item, str):
                prompt_parts.append(item)
        
        prompt_text = "\n".join(prompt_parts)
        
        # Extract model from cascadeConfig
        cascade_config = data.get('cascadeConfig', {})
        planner_config = cascade_config.get('plannerConfig', {})
        model_uid = planner_config.get('requestedModelUid', '')
        
        # Extract planner mode
        conversational = planner_config.get('conversational', {})
        planner_mode = conversational.get('plannerMode', '')
        
        # Extract metadata from the Windsurf metadata field
        ws_meta = data.get('metadata', {})
        cascade_id = data.get('cascadeId', '')
        
        # Build messages list
        messages = [{'role': 'user', 'content': prompt_text}]
        
        metadata = {
            'model': model_uid,
            'cascade_id': cascade_id,
            'planner_mode': planner_mode,
            'ide_name': ws_meta.get('ideName', 'windsurf'),
            'ide_version': ws_meta.get('ideVersion', ''),
            'extension_version': ws_meta.get('extensionVersion', ''),
            'locale': ws_meta.get('locale', ''),
            'api_key_present': bool(ws_meta.get('apiKey')),
            'brain_enabled': cascade_config.get('brainConfig', {}).get('enabled', False),
            'content_type': headers.get('content-type', ''),
            'request_size': 0,  # will be set by caller if needed
        }
        
        return InterceptedPrompt(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            source='windsurf',
            user_agent=headers.get('user-agent', ''),
            url=url,
            method=method,
            prompt=prompt_text,
            messages=messages,
            response=None,
            metadata=metadata,
        )
    
    def extract_response(self, response_body: str) -> Optional[str]:
        """Extract AI response from HTTP response"""
        try:
            if not response_body:
                return None
                
            # Handle streaming responses (Server-Sent Events)
            if response_body.startswith('data: '):
                lines = response_body.split('\n')
                response_text = ""
                
                for line in lines:
                    if line.startswith('data: ') and line != 'data: [DONE]':
                        try:
                            chunk_data = json.loads(line[6:])  # Remove 'data: '
                            
                            # OpenAI streaming format
                            choices = chunk_data.get('choices', [])
                            if choices:
                                delta = choices[0].get('delta', {})
                                content = delta.get('content', '')
                                response_text += content
                                
                        except json.JSONDecodeError:
                            continue
                
                return response_text if response_text else None
            
            # Regular JSON response
            else:
                data = json.loads(response_body)
                
                # OpenAI format
                if 'choices' in data:
                    choices = data['choices']
                    if choices:
                        message = choices[0].get('message', {})
                        return message.get('content', '')
                
                # Anthropic format
                elif 'content' in data:
                    content = data['content']
                    if isinstance(content, list) and content:
                        return content[0].get('text', '')
                    elif isinstance(content, str):
                        return content
                
                # Generic response field
                elif 'response' in data:
                    return data['response']
                
                return None
                
        except json.JSONDecodeError:
            return None
        except Exception as e:
            console.print(f"[red]Error extracting response: {e}[/red]")
            return None
    
    def _detect_source(self, user_agent: str, url: str) -> str:
        """Detect the source application making the request"""
        user_agent_lower = user_agent.lower()
        url_lower = url.lower()
        
        if 'windsurf' in user_agent_lower or 'windsurf' in url_lower:
            return 'windsurf'
        elif 'cursor' in user_agent_lower:
            return 'cursor'
        elif 'vscode' in user_agent_lower:
            return 'vscode'
        elif 'copilot' in user_agent_lower:
            return 'github-copilot'
        elif 'electron' in user_agent_lower:
            return 'electron-app'
        else:
            return 'unknown'
    
    def should_log_request(self, prompt: InterceptedPrompt) -> bool:
        """Determine if this prompt should be logged based on filters"""
        # Skip empty prompts
        if not prompt.prompt.strip():
            return False
        
        # Skip very short prompts (likely autocomplete)
        if len(prompt.prompt) < 10:
            return False
            
        # Skip system/internal requests
        system_patterns = ['health', 'ping', 'status', 'auth', 'token']
        for pattern in system_patterns:
            if pattern in prompt.url.lower():
                return False
        
        return True