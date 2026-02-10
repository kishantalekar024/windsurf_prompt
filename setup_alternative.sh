#!/bin/bash

echo "🚀 Alternative Simple Setup (if quick_setup.sh fails)"
echo ""

# Install latest Python and pip via Homebrew (recommended for Mac)
echo "📦 Installing latest Python via Homebrew..."
echo "This will install Python 3.11+ with latest pip"

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo ""
    echo "❌ Homebrew not found. Please install it first:"
    echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo ""
    echo "Or use manual setup:"
    echo "1. Install Python 3.11+ from https://www.python.org/downloads/"
    echo "2. pip install mitmproxy requests flask rich colorama python-dotenv flask-cors"
    echo "3. python src/main.py"
    exit 1
fi

# Install Python 3.11
brew install python@3.11

# Use Homebrew Python
export PATH="/opt/homebrew/bin:$PATH"
PYTHON_BIN="/opt/homebrew/bin/python3.11"

echo "✅ Using: $($PYTHON_BIN --version)"

# Create fresh virtual environment
echo "📦 Creating virtual environment..."
rm -rf venv
$PYTHON_BIN -m venv venv
source venv/bin/activate

# Install packages one by one to avoid conflicts
echo "📥 Installing mitmproxy..."
pip install mitmproxy==9.0.1

echo "📥 Installing web framework..."
pip install flask==2.2.5 flask-cors==4.0.0

echo "📥 Installing utilities..."
pip install requests==2.28.2 python-dotenv==1.0.0 rich==13.7.0 colorama==0.4.6

echo ""
echo "✅ Alternative setup complete!"
echo ""
echo "🚀 Now run:"
echo "   source venv/bin/activate"
echo "   python src/main.py"