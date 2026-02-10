# Windsurf AI Prompt Interceptor

A lightweight MITM proxy tool for capturing and viewing AI chat prompts from Windsurf and other Electron-based IDEs in real-time. Simple console output - no database required.

## 🚀 Features

- **Real-time MITM Interception**: Captures HTTPS traffic from Windsurf and other AI-enabled editors
- **Console Output**: Beautiful formatted display of prompts and responses in terminal
- **Smart Filtering**: Automatically detects and filters AI API calls (OpenAI, Anthropic, Codeium)
- **Source Detection**: Identifies which application sent the prompt (Windsurf, VS Code, Cursor, etc.)
- **Automatic SSL Setup**: Handles certificate installation and system proxy configuration
- **Zero Configuration**: No database setup required - just install and run

## 📋 Requirements

- **macOS** (primary target, Linux/Windows support planned)
- **Python 3.8+**
- **Admin privileges** (for certificate and proxy setup)

## 🛠️ Installation

### Super Quick Setup

```bash
# Install dependencies
pip install -r requirements-simple.txt

# Start intercepting
python src/main.py
```

### Alternative Setup

```bash
# Manual install if requirements file fails
pip install mitmproxy requests rich colorama python-dotenv

# Start intercepting
python src/main.py
```

## ⚙️ Configuration

Optional: Edit the `.env` file to customize:

```env
# Proxy Settings
PROXY_PORT=8080

# AI API Monitoring
MONITOR_OPENAI=true
MONITOR_ANTHROPIC=true
MONITOR_CODEIUM=true
MONITOR_ALL_AI_APIS=true

# SSL Certificate
AUTO_INSTALL_CERT=true
```

## 🚀 Usage

### Starting the Interceptor

```bash
# Start intercepting
python src/main.py

# The system will:
# 1. Install and trust the MITM certificate
# 2. Configure system proxy settings
# 3. Start capturing and printing AI traffic
```

### Using with Windsurf

1. **Launch the interceptor** (as shown above)
2. **Open Windsurf** - it will automatically use the system proxy
3. **Start chatting** with Windsurf's AI features
4. **Watch your terminal** - all prompts and responses will be displayed in real-time

### What You'll See

```
================================================================================
🔍 CAPTURED AI PROMPT
================================================================================
Source: windsurf
Timestamp: 2026-02-09 19:45:30
URL: https://api.openai.com/v1/chat/completions

📝 PROMPT:
Refactor this function to use async/await

🤖 AI RESPONSE:
Here's the refactored function using async/await...
================================================================================
```

## � What Gets Captured

The interceptor captures and displays:

- **Prompt Text**: The actual question/request sent to AI
- **AI Response**: The complete response from the AI service
- **Source Application**: Which app sent the request (Windsurf, VS Code, etc.)
- **API Details**: URL, method, timestamp
- **Metadata**: Model name, parameters, etc.

Everything is displayed in real-time in your terminal - no storage, no database, just live monitoring.

## 🛡️ Security & Privacy

### Important Considerations

- **Data Sensitivity**: This tool captures AI prompts which may contain sensitive code/data
- **No Storage**: All data is only displayed in terminal - nothing is saved
- **HTTPS Interception**: Requires trusting a custom certificate authority
- **System Proxy**: Temporarily modifies system network settings

### Best Practices

1. **Use only on your own machine** with your own accounts
2. **Terminal output may contain sensitive info** - be aware of screen sharing
3. **Disable when not needed** to avoid unnecessary interception
4. **Press Ctrl+C to stop** and restore normal network settings

## 🔍 Troubleshooting

### Certificate Issues

```bash
# Manually install certificate
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain \
  ~/.mitmproxy/mitmproxy-ca-cert.pem
```

### Proxy Not Working

```bash
# Check proxy settings
networksetup -getwebproxy "Wi-Fi"
networksetup -getsecurewebproxy "Wi-Fi"

# Reset proxy settings
networksetup -setwebproxystate "Wi-Fi" off
networksetup -setsecurewebproxystate "Wi-Fi" off
```

### No Output Showing

```bash
# Check if mitmproxy is working
ps aux | grep mitmproxy

# Check proxy settings
networksetup -getwebproxy "Wi-Fi"
```

### Application Not Detected

1. Check if Windsurf is using the system proxy
2. Verify the AI API endpoints in the configuration
3. Look for custom User-Agent patterns
4. Check certificate trust settings

## 🔮 Future Enhancements

If you want more features later:

- [ ] **Database storage** (re-enable the database code)
- [ ] **Web dashboard** (re-enable the Flask server)
- [ ] **Export functionality** (JSON, CSV, markdown)
- [ ] **Advanced analytics** (prompt patterns, usage statistics)
- [ ] **Cross-platform support** (Windows, Linux)

### AI Provider Support

- [x] OpenAI (GPT-3.5, GPT-4)
- [x] Anthropic (Claude)  
- [x] Codeium
- [ ] GitHub Copilot
- [ ] Google Bard/Gemini
- [ ] Mistral AI
- [ ] Local LLMs (Ollama, LM Studio)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Legal Notice

This tool is for educational and debugging purposes only. Users must:

- Only use on their own accounts and data
- Comply with AI service Terms of Service
- Respect privacy and data protection laws
- Not use for unauthorized data collection

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 🆘 Support

For questions, issues, or feature requests:

- **GitHub Issues**: [Create an issue](https://github.com/your-repo/issues)
- **Documentation**: Check this README and inline code comments
- **Community**: Join discussions in GitHub Discussions

---

**Happy prompt intercepting! 🔍✨**

*Simple, lightweight, and effective network monitoring for your AI workflows.*