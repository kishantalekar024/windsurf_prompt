# 🔍 Quick Start Guide - Windsurf Prompt Interceptor

**Capture and view Windsurf AI prompts in real-time with zero database setup!**

## 🚀 Super Quick Start

```bash
# 1. Run quick setup
./quick_setup.sh

# 2. Activate environment  
source venv/bin/activate

# 3. Start intercepting
python src/main.py
```

That's it! Open Windsurf and start chatting with AI - you'll see all prompts and responses in your terminal.

## 📋 What You'll See

When you start chatting with Windsurf's AI, you'll see formatted output like:

```
================================================================================
🔍 CAPTURED AI PROMPT
================================================================================
Source: windsurf
Timestamp: 2026-02-09 19:45:30
URL: https://api.openai.com/v1/chat/completions
Method: POST

📝 PROMPT:
Refactor this function to use async/await

🤖 AI RESPONSE for 12ab34cd...
--------------------------------------------------------------------------------
Here's the refactored function using async/await:

async function processData() {
  try {
    const result = await fetchData();
    return await transformData(result);
  } catch (error) {
    console.error('Processing failed:', error);
  }
}
--------------------------------------------------------------------------------
```

## 🛠️ Requirements

- **macOS** (Linux/Windows support coming soon)
- **Python 3.8+**
- **Admin access** (for SSL certificate installation)

## ⚙️ How It Works

1. **SSL Certificate**: Automatically installs and trusts mitmproxy certificate
2. **System Proxy**: Configures macOS to route traffic through port 8080
3. **AI Detection**: Identifies API calls to OpenAI, Anthropic, Codeium, etc.
4. **Real-time Display**: Shows prompts and responses as they happen

## 🔧 Troubleshooting

### Certificate Issues
```bash
# If auto-install fails, run with sudo
sudo python src/main.py
```

### Proxy Not Working
```bash
# Reset proxy settings
networksetup -setwebproxystate "Wi-Fi" off
networksetup -setsecurewebproxystate "Wi-Fi" off
```

### No Prompts Detected
- Ensure Windsurf is running
- Check that system proxy is enabled
- Try restarting Windsurf after starting the interceptor

## 🎯 Supported Applications

- ✅ **Windsurf** (primary target)
- ✅ **VS Code** (with AI extensions)
- ✅ **Cursor**
- ✅ **Any Electron-based AI IDE**

## 🔄 Switching to Database Mode

Want to store prompts permanently? Switch to full database mode:

```bash
# Use full setup instead
./setup.sh
source venv/bin/activate

# Configure database in .env file
nano .env

# Uncomment database code in src/proxy_interceptor.py
# Then run normally
python src/main.py
```

## ⚠️ Important Notes

- **Privacy**: All interception happens locally on your machine
- **Security**: Only use on your own accounts and data
- **Performance**: Minimal impact on system performance
- **Cleanup**: Tool automatically restores proxy settings on exit

## 🆘 Quick Commands

```bash
# Stop the interceptor
Ctrl+C

# Check if proxy is enabled
networksetup -getwebproxy "Wi-Fi"

# View certificate status
security find-certificate -c "mitmproxy" -a

# Reset everything
./reset_proxy.sh  # (if created)
```

## 🚀 That's It!

The tool is designed to "just work" - no complex configuration, no database setup, just install and run!

**Happy prompt intercepting! 🔍✨**