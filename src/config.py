from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class InterceptedPrompt:
    id: str
    timestamp: datetime
    source: str  # windsurf, vscode, etc.
    user_agent: str
    url: str
    method: str
    prompt: str
    messages: List[Dict[str, Any]]
    response: Optional[str]
    metadata: Dict[str, Any]

class Config:
    # Proxy
    PROXY_PORT = int(os.getenv('PROXY_PORT', 8080))
    
    # AI API Monitoring
    MONITOR_OPENAI = os.getenv('MONITOR_OPENAI', 'true').lower() == 'true'
    MONITOR_ANTHROPIC = os.getenv('MONITOR_ANTHROPIC', 'true').lower() == 'true'
    MONITOR_CODEIUM = os.getenv('MONITOR_CODEIUM', 'true').lower() == 'true'
    MONITOR_ALL_AI_APIS = os.getenv('MONITOR_ALL_AI_APIS', 'true').lower() == 'true'
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # SSL
    AUTO_INSTALL_CERT = os.getenv('AUTO_INSTALL_CERT', 'true').lower() == 'true'
    CERT_PATH = os.path.expanduser(os.getenv('CERT_PATH', '~/.mitmproxy/mitmproxy-ca-cert.pem'))

    # AI API Patterns
    AI_API_PATTERNS = [
        'api.openai.com',
        'api.anthropic.com', 
        'api.codeium.com',
        '/v1/chat/completions',
        '/v1/completions',
        '/v1/messages',
        '/chat/completions',
        'windsurf',
        'cursor',
        'copilot'
    ]

    @classmethod
    def get_monitored_patterns(cls):
        """Return list of URL patterns to monitor based on config"""
        patterns = []
        
        if cls.MONITOR_OPENAI:
            patterns.extend(['api.openai.com', '/v1/chat/completions', '/v1/completions'])
        
        if cls.MONITOR_ANTHROPIC:
            patterns.extend(['api.anthropic.com', '/v1/messages'])
            
        if cls.MONITOR_CODEIUM:
            patterns.extend(['api.codeium.com', 'codeium'])
            
        if cls.MONITOR_ALL_AI_APIS:
            patterns.extend(cls.AI_API_PATTERNS)
            
        return list(set(patterns))  # Remove duplicates