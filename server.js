#!/usr/bin/env node

/**
 * Simple Node.js server for fetching Windsurf prompts
 * 
 * Focused on retrieving and serving prompt data from MongoDB/files.
 * 
 * Usage:
 *   node server.js                    # Start on default port 8000
 *   PORT=3000 node server.js         # Start on custom port
 *   MONGO_URI=... node server.js     # Custom MongoDB connection
 */

const express = require('express');
const { MongoClient } = require('mongodb');
const fs = require('fs');
const path = require('path');
const cors = require('cors');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 8000;
const MONGO_URI = process.env.MONGO_URI || 'mongodb+srv://windsurf_prompt:Ug7vl28TQok7yJkQ@cluster0.fqpyy.mongodb.net/?appName=Cluster0';
const DB_NAME = 'windsurf_prompts';
const COLLECTION_NAME = 'prompts';

// Middleware
app.use(cors());
app.use(express.json());

// Global DB connection
let mongoClient = null;
let db = null;
let collection = null;
let isConnected = false;

// MongoDB connection
async function connectToMongoDB() {
    try {
        mongoClient = new MongoClient(MONGO_URI, {
            serverSelectionTimeoutMS: 3000,
            connectTimeoutMS: 3000
        });
        
        await mongoClient.connect();
        await mongoClient.db('admin').command({ ping: 1 });
        
        db = mongoClient.db(DB_NAME);
        collection = db.collection(COLLECTION_NAME);
        isConnected = true;
        
        console.log(`✓ Connected to MongoDB: ${DB_NAME}`);
        return true;
    } catch (error) {
        console.log(`⚠ MongoDB connection failed: ${error.message}`);
        isConnected = false;
        return false;
    }
}

// Fallback: Read from JSONL files
function readPromptsFromFiles() {
    const prompts = [];
    const logsDir = path.join(__dirname, 'logs');
    
    if (!fs.existsSync(logsDir)) {
        return prompts;
    }
    
    try {
        const files = fs.readdirSync(logsDir)
            .filter(file => file.startsWith('prompts_') && file.endsWith('.jsonl'))
            .sort()
            .reverse(); // Newest first
        
        for (const file of files) {
            const filePath = path.join(logsDir, file);
            const content = fs.readFileSync(filePath, 'utf-8');
            
            const lines = content.split('\n').filter(line => line.trim());
            for (const line of lines) {
                try {
                    const entry = JSON.parse(line);
                    prompts.push(entry);
                } catch (e) {
                    // Skip invalid JSON lines
                }
            }
        }
    } catch (error) {
        console.error('Error reading JSONL files:', error.message);
    }
    
    return prompts;
}

// Root endpoint - Basic info
app.get('/', (req, res) => {
    res.json({
        name: 'Windsurf Prompts Fetcher',
        version: '1.0.0',
        platform: 'Node.js',
        endpoints: {
            'GET /prompts': 'Fetch captured prompts',
            'GET /prompts/latest': 'Get latest prompts',
            'GET /health': 'Health check'
        }
    });
});

// Health check
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        mongodb_connected: isConnected
    });
});

// Get prompts (main endpoint)
app.get('/prompts', async (req, res) => {
    try {
        const limit = Math.min(parseInt(req.query.limit) || 50, 500);
        const skip = parseInt(req.query.skip) || 0;
        
        if (isConnected && collection) {
            // Fetch from MongoDB
            const prompts = await collection
                .find({})
                .sort({ timestamp: -1 })
                .skip(skip)
                .limit(limit)
                .project({
                    timestamp: 1,
                    prompt: 1,
                    'metadata.model': 1,
                    'metadata.cascade_id': 1,
                    'metadata.planner_mode': 1,
                    'metadata.brain_enabled': 1,
                    source: 1
                })
                .toArray();
            
            const total = await collection.countDocuments({});
            
            res.json({
                success: true,
                prompts,
                total,
                limit,
                skip,
                returned: prompts.length,
                source: 'mongodb'
            });
        } else {
            // Fallback to files
            const allPrompts = readPromptsFromFiles();
            const total = allPrompts.length;
            const prompts = allPrompts
                .slice(skip, skip + limit)
                .map(p => ({
                    timestamp: p.timestamp,
                    prompt: p.prompt,
                    metadata: {
                        model: p.metadata?.model,
                        cascade_id: p.metadata?.cascade_id,
                        planner_mode: p.metadata?.planner_mode,
                        brain_enabled: p.metadata?.brain_enabled
                    },
                    source: p.source
                }));
            
            res.json({
                success: true,
                prompts,
                total,
                limit,
                skip,
                returned: prompts.length,
                source: 'files'
            });
        }
    } catch (error) {
        console.error('Error fetching prompts:', error);
        res.status(500).json({
            success: false,
            error: 'Failed to fetch prompts',
            message: error.message
        });
    }
});

// Get latest prompts (quick endpoint)
app.get('/prompts/latest', async (req, res) => {
    try {
        const limit = Math.min(parseInt(req.query.limit) || 10, 50);
        
        if (isConnected && collection) {
            const prompts = await collection
                .find({})
                .sort({ timestamp: -1 })
                .limit(limit)
                .project({
                    timestamp: 1,
                    prompt: 1,
                    'metadata.model': 1,
                    'metadata.cascade_id': 1
                })
                .toArray();
            
            res.json({
                success: true,
                prompts,
                count: prompts.length,
                source: 'mongodb'
            });
        } else {
            const allPrompts = readPromptsFromFiles();
            const prompts = allPrompts
                .slice(0, limit)
                .map(p => ({
                    timestamp: p.timestamp,
                    prompt: p.prompt,
                    metadata: {
                        model: p.metadata?.model,
                        cascade_id: p.metadata?.cascade_id
                    }
                }));
            
            res.json({
                success: true,
                prompts,
                count: prompts.length,
                source: 'files'
            });
        }
    } catch (error) {
        console.error('Error fetching latest prompts:', error);
        res.status(500).json({
            success: false,
            error: 'Failed to fetch latest prompts',
            message: error.message
        });
    }
});

// 404 handler
app.use('*', (req, res) => {
    res.status(404).json({
        error: 'Not found',
        message: `Endpoint ${req.method} ${req.originalUrl} not found`
    });
});

// Error handler
app.use((error, req, res, next) => {
    console.error('Unhandled error:', error);
    res.status(500).json({
        error: 'Internal server error',
        message: error.message
    });
});

// Graceful shutdown
process.on('SIGINT', async () => {
    console.log('\n⚠ Received SIGINT, shutting down gracefully...');
    
    if (mongoClient) {
        await mongoClient.close();
        console.log('✓ MongoDB connection closed');
    }
    
    process.exit(0);
});

process.on('SIGTERM', async () => {
    console.log('\n⚠ Received SIGTERM, shutting down gracefully...');
    
    if (mongoClient) {
        await mongoClient.close();
        console.log('✓ MongoDB connection closed');
    }
    
    process.exit(0);
});

// Start server
async function startServer() {
    console.log('🚀 Starting Windsurf Prompts Fetcher (Node.js)...\n');
    
    // Try to connect to MongoDB
    await connectToMongoDB();
    
    app.listen(PORT, '0.0.0.0', () => {
        console.log('\n' + '='.repeat(60));
        console.log('📥 Windsurf Prompts Fetcher (Node.js)');
        console.log('='.repeat(60));
        console.log(`📡 Server: http://0.0.0.0:${PORT}`);
        console.log(`📋 Endpoints:`);
        console.log(`   • GET /prompts - Fetch prompts (paginated)`);
        console.log(`   • GET /prompts/latest - Get latest prompts`);
        console.log(`   • GET /health - Health check`);
        console.log(`\n📁 Data sources:`);
        console.log(`   • MongoDB: ${isConnected ? '✅ Connected' : '❌ Disconnected'}`);
        console.log(`   • JSONL files: ✅ Available (fallback)`);
        console.log(`\n🌐 Access from network:`);
        console.log(`   curl http://localhost:${PORT}/prompts/latest`);
        console.log('\nPress Ctrl+C to stop');
        console.log('='.repeat(60) + '\n');
    });
}

// Handle unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

startServer().catch(console.error);