#!/bin/bash

# Node.js Prompts Fetcher for Windsurf

echo "📥 Starting Windsurf Prompts Fetcher (Node.js)..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js first:"
    echo "   brew install node"
    exit 1
fi

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Start the server
echo "🌐 Starting fetch server on http://0.0.0.0:8000..."
node server.js