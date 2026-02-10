# 🚀 App-Specific Proxy Setup Guide

## ✅ **What This Fixes**
- ✅ Your internet works normally
- ✅ Only Windsurf traffic goes through proxy  
- ✅ No system-wide proxy conflicts
- ✅ Easy to start/stop

## 🎯 **How to Use**

### **1. Start the Proxy**
```bash
# In first terminal - start the interceptor
source venv/bin/activate
python src/main.py
```

### **2. Start Windsurf with Proxy**
```bash
# In second terminal - launch Windsurf
./launch_windsurf.sh
```

### **3. Use Windsurf AI**
- Open Windsurf (should be running from step 2)
- Use AI chat features normally
- Watch first terminal for captured prompts!

## 🔧 **Troubleshooting**

### **Windsurf Not Found**
```bash
# Find Windsurf location
find /Applications -name "*indsurf*" -type f

# Update the path in launch_windsurf.sh
nano launch_windsurf.sh
```

### **No Traffic Captured**
Try alternative launch methods:

```bash
# Method 1: Environment variable
HTTP_PROXY=127.0.0.1:8080 HTTPS_PROXY=127.0.0.1:8080 /Applications/Windsurf.app/Contents/MacOS/Windsurf

# Method 2: Different proxy flags
/Applications/Windsurf.app/Contents/MacOS/Windsurf --proxy-pac-url="data:application/x-ns-proxy-autoconfig;charset=utf-8,function FindProxyForURL(url, host) { return 'PROXY 127.0.0.1:8080'; }"

# Method 3: System proxy (temporary)
networksetup -setwebproxy "Wi-Fi" 127.0.0.1 8080
networksetup -setsecurewebproxy "Wi-Fi" 127.0.0.1 8080
# Remember to reset: ./reset_proxy.sh
```

## 🎉 **Benefits**
- **Safe**: No system internet disruption
- **Targeted**: Only intercepts Windsurf 
- **Clean**: Easy reset and cleanup
- **Flexible**: Multiple launch options