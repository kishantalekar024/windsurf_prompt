# Windsurf AI Prompt Interceptor

A lightweight local traffic interceptor for capturing and analyzing AI chat prompts from Windsurf IDE in real-time. Features MongoDB storage, REST API access, and web dashboard integration.

**Focus**: Local traffic capture only (no MITM proxy) - specifically designed for Windsurf's d.localhost communication pattern.

## 🌐  links

**Frontend Dashboard**: [Prompt Explorer](https://lovable.dev/projects/4a5d0f69-a5a2-422c-886f-939fe2f7e005?magic_link=mc_4d1bb855-3c58-4a1e-9973-f397f87bf127)  
**Backend API**: [https://windsurf-prompt.onrender.com](https://windsurf-prompt.onrender.com)  
**Source Code**: [Frontend Repository](https://github.com/kishantalekar024/prompt-explorer)


## 🚀 Quick Start


### Installation & Setup

```bash
# 1. Set up Python environment
python -m venv venv
source venv/bin/activate  # On macOS/Linux
pip install -r requirements.txt

# 2. Install Node.js dependencies  
npm install

# 3. Start the interceptor (REQUIRED: sudo for traffic capture)
sudo ./venv/bin/python src/main.py

# 4. (Optional) Start the API server for web access
node server.js
```

## 📊 What You'll See

### Console Output
```
🔍 Windsurf Prompt Interceptor

✓ Connected to MongoDB: windsurf_prompts
✓ Proxy started on port 8080
✓ Loopback sniffer started (capturing d.localhost traffic)

Database: ✅ MongoDB Connected
Loopback Sniffer: ✅ Active (capturing local Windsurf traffic)

================================================================================
🎯 WINDSURF PROMPT CAPTURED  [14:58:41]  (local loopback)
================================================================================
  Model:          MODEL_SWE_1_5
  Cascade ID:     52d2c626-dc2f-43b4-a1bf-8823623388f4
  Planner Mode:   CONVERSATIONAL_PLANNER_MODE_DEFAULT
  IDE:            Windsurf 1.9544.35
  Extension:      v1.48.2
  Brain:          ✅ Enabled

  📝 PROMPT:
  Create a React component for user authentication
================================================================================
```

### API Access (Optional)
If running the Node.js server:
```bash
# Get recent prompts
curl http://localhost:8000/prompts/latest?limit=5

# Get statistics  
curl http://localhost:8000/prompts/stats

# Check health
curl http://localhost:8000/health
```

## 🔍 Features

The interceptor captures and stores:

- **Windsurf Prompts**: Real-time capture of all AI chat interactions
- **Complete Metadata**: Model, cascade ID, planner mode, IDE version, Brain status
- **MongoDB Storage**: Persistent storage with fallback to JSON files
- **REST API**: Access captured data via HTTP endpoints
- **Web Dashboard**: Compatible with external dashboard applications
- **Real-time Display**: Live console output with rich formatting

## 🗄️ Data Storage

### MongoDB (Recommended)
- Automatic connection to configured MongoDB instance
- Indexed for fast queries and analytics
- Supports aggregation for statistics

### File Fallback
- JSONL files stored in `./logs/` directory
- One file per day: `prompts_YYYY-MM-DD.jsonl`
- Used when MongoDB is unavailable

## 🌐 API Endpoints

### Local Development
When running `node server.js` locally:

| Endpoint | Description |
|----------|-------------|
| `GET /prompts` | Get captured prompts (paginated) |
| `GET /prompts/latest` | Get most recent prompts |
| `GET /prompts/count` | Get total prompt count |
| `GET /prompts/stats` | Get aggregated statistics |
| `GET /health` | Server and database health check |

### Production API
The live API is deployed at: **https://windsurf-prompt.onrender.com**

**Example API calls:**
```bash
# Get latest prompts from production
curl https://windsurf-prompt.onrender.com/prompts/latest?limit=5

# Get statistics
curl https://windsurf-prompt.onrender.com/prompts/stats

# Check API health
curl https://windsurf-prompt.onrender.com/health
```

### Dashboard Integration
The [Prompt Explorer Dashboard](https://lovable.dev/projects/4a5d0f69-a5a2-422c-886f-939fe2f7e005?magic_link=mc_4d1bb855-3c58-4a1e-9973-f397f87bf127) automatically connects to the production API to display your captured prompts in a beautiful, interactive interface.

## ⚙️ Configuration

### Environment Variables
- `MONGO_URI`: MongoDB connection string (shared between interceptor and API)
- `PORT`: API server port (default: 8000)

### Dashboard Configuration
The [frontend dashboard](https://github.com/kishantalekar024/prompt-explorer) is pre-configured to connect to:
- **Production API**: `https://windsurf-prompt.onrender.com`
- **Local API**: `http://localhost:8000` (when developing locally)



### Troubleshooting

**Permission Issues:**
```bash
# Interceptor requires sudo for packet capture
sudo ./venv/bin/python src/main.py
```

**Proxy Not Working:**
```bash
# Check proxy settings
networksetup -getwebproxy "Wi-Fi"
networksetup -getsecurewebproxy "Wi-Fi"

# Reset proxy settings  
networksetup -setwebproxystate "Wi-Fi" off
networksetup -setsecurewebproxystate "Wi-Fi" off
```

**MongoDB Connection Issues:**
- Check your `MONGO_URI` environment variable
- Verify network connectivity
- Interceptor will fall back to file logging automatically

## 🏗️ Project Structure

```
windsurf-prompt/
├── src/                    # Python interceptor core
│   ├── main.py            # Main entry point  
│   ├── proxy_interceptor.py  # MITM proxy server
│   ├── local_sniffer.py   # Loopback traffic capture
│   ├── db.py              # MongoDB interface
│   └── api.py             # Database helpers
├── server.js              # Node.js API server
├── package.json           # Node.js dependencies
├── requirements.txt       # Python dependencies
└── logs/                  # JSON file storage (fallback)
```




---

