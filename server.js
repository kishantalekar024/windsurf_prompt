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
            'GET /prompts': 'Fetch captured prompts (paginated)',
            'GET /prompts/latest': 'Get latest prompts',
            'GET /prompts/count': 'Get total prompt count',
            'GET /prompts/stats': 'Get aggregated statistics',
            'GET /prompts/models': 'Get available models',
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
        
        // Build filter object
        const filters = {};
        const { user, model, prompt: promptText, from, to } = req.query;
        
        if (user) filters.user = { $regex: user, $options: 'i' };
        if (model) filters['metadata.model'] = model;
        if (promptText) filters.prompt = { $regex: promptText, $options: 'i' };
        
        // Date range filtering
        if (from || to) {
            filters.timestamp = {};
            if (from) filters.timestamp.$gte = new Date(from);
            if (to) filters.timestamp.$lte = new Date(to);
        }

        if (isConnected && collection) {
            // Fetch from MongoDB
            const prompts = await collection
                .find(filters)
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
                    source: 1,
                    user: 1
                })
                .toArray();

            const total = await collection.countDocuments(filters);

            res.json({
                success: true,
                prompts,
                total,
                limit,
                skip,
                returned: prompts.length,
                source: 'mongodb',
                filters: filters
            });
        } else {
            // Fallback to files with filtering
            let allPrompts = readPromptsFromFiles();
            
            // Apply filters to file data
            if (user) {
                const userRegex = new RegExp(user, 'i');
                allPrompts = allPrompts.filter(p => userRegex.test(p.user));
            }
            if (model) {
                allPrompts = allPrompts.filter(p => p.metadata?.model === model);
            }
            if (promptText) {
                const regex = new RegExp(promptText, 'i');
                allPrompts = allPrompts.filter(p => regex.test(p.prompt));
            }
            if (from || to) {
                allPrompts = allPrompts.filter(p => {
                    const timestamp = new Date(p.timestamp);
                    if (from && timestamp < new Date(from)) return false;
                    if (to && timestamp > new Date(to)) return false;
                    return true;
                });
            }
            
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
                    source: p.source,
                    user: p.user
                }));

            res.json({
                success: true,
                prompts,
                total,
                limit,
                skip,
                returned: prompts.length,
                source: 'files',
                filters: { user, model, prompt: promptText, from, to }
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
                    'metadata.cascade_id': 1,
                    user: 1
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
                    },
                    user: p.user
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

// Get prompt count
app.get('/prompts/count', async (req, res) => {
    try {
        if (isConnected && collection) {
            const count = await collection.countDocuments({});
            res.json({
                success: true,
                count,
                source: 'mongodb'
            });
        } else {
            const prompts = readPromptsFromFiles();
            res.json({
                success: true,
                count: prompts.length,
                source: 'files'
            });
        }
    } catch (error) {
        console.error('Error counting prompts:', error);
        res.status(500).json({
            success: false,
            error: 'Failed to count prompts',
            message: error.message
        });
    }
});

// Get available models
app.get('/prompts/models', async (req, res) => {
    try {
        if (isConnected && collection) {
            // Fetch from MongoDB
            const models = await collection.distinct('metadata.model');
            const modelStats = await collection.aggregate([
                {
                    $group: {
                        _id: '$metadata.model',
                        count: { $sum: 1 },
                        last_used: { $max: '$timestamp' }
                    }
                },
                {
                    $project: {
                        _id: 0,
                        model: '$_id',
                        count: 1,
                        last_used: 1
                    }
                },
                { $sort: { count: -1 } }
            ]).toArray();

            res.json({
                success: true,
                models: models.filter(m => m), // Filter out null/undefined
                model_stats: modelStats,
                total_models: models.filter(m => m).length,
                source: 'mongodb'
            });
        } else {
            // Fallback to files
            const allPrompts = readPromptsFromFiles();
            const modelCounts = {};
            const modelLastUsed = {};
            
            allPrompts.forEach(prompt => {
                const model = prompt.metadata?.model;
                if (model) {
                    modelCounts[model] = (modelCounts[model] || 0) + 1;
                    const timestamp = new Date(prompt.timestamp);
                    if (!modelLastUsed[model] || timestamp > modelLastUsed[model]) {
                        modelLastUsed[model] = timestamp;
                    }
                }
            });
            
            const models = Object.keys(modelCounts);
            const modelStats = models.map(model => ({
                model,
                count: modelCounts[model],
                last_used: modelLastUsed[model]
            })).sort((a, b) => b.count - a.count);

            res.json({
                success: true,
                models,
                model_stats: modelStats,
                total_models: models.length,
                source: 'files'
            });
        }
    } catch (error) {
        console.error('Error fetching models:', error);
        res.status(500).json({
            success: false,
            error: 'Failed to fetch models',
            message: error.message
        });
    }
});

// Get aggregated statistics
app.get('/prompts/stats', async (req, res) => {
    try {
        if (isConnected && collection) {
            // MongoDB aggregation
            const pipeline = [
                {
                    $group: {
                        _id: null,
                        total_prompts: { $sum: 1 },
                        unique_models: { $addToSet: '$metadata.model' },
                        unique_sources: { $addToSet: '$source' },
                        avg_prompt_length: { $avg: { $strLenCP: '$prompt' } },
                        brain_enabled_count: {
                            $sum: {
                                $cond: [{ $eq: ['$metadata.brain_enabled', true] }, 1, 0]
                            }
                        },
                        models: { $push: '$metadata.model' },
                        planners: { $push: '$metadata.planner_mode' },
                        hours: { $push: { $hour: '$timestamp' } }
                    }
                }
            ];

            const result = await collection.aggregate(pipeline).toArray();
            const stats = result[0] || {};

            // Process model usage
            const modelUsage = {};
            if (stats.models) {
                stats.models.forEach(model => {
                    if (model) {
                        modelUsage[model] = (modelUsage[model] || 0) + 1;
                    }
                });
            }

            // Process planner usage  
            const plannerUsage = {};
            if (stats.planners) {
                stats.planners.forEach(planner => {
                    if (planner) {
                        plannerUsage[planner] = (plannerUsage[planner] || 0) + 1;
                    }
                });
            }

            // Process hourly distribution
            const hourlyDistribution = Array(24).fill(0);
            if (stats.hours) {
                stats.hours.forEach(hour => {
                    if (typeof hour === 'number' && hour >= 0 && hour < 24) {
                        hourlyDistribution[hour]++;
                    }
                });
            }

            const responseStats = {
                total_prompts: stats.total_prompts || 0,
                unique_models: stats.unique_models ? stats.unique_models.length : 0,
                unique_sources: stats.unique_sources ? stats.unique_sources.length : 0,
                avg_prompt_length: Math.round(stats.avg_prompt_length || 0),
                brain_enabled_percentage: stats.total_prompts > 0
                    ? Math.round((stats.brain_enabled_count / stats.total_prompts) * 100)
                    : 0,
                model_usage: modelUsage,
                planner_usage: plannerUsage,
                hourly_distribution: hourlyDistribution
            };

            res.json({
                success: true,
                stats: responseStats,
                source: 'mongodb'
            });

        } else {
            // Fallback to files
            const prompts = readPromptsFromFiles();

            const modelUsage = {};
            const plannerUsage = {};
            const hourlyDistribution = Array(24).fill(0);
            let brainEnabledCount = 0;
            let totalPromptLength = 0;

            prompts.forEach(prompt => {
                // Model usage
                const model = prompt.metadata?.model;
                if (model) {
                    modelUsage[model] = (modelUsage[model] || 0) + 1;
                }

                // Planner usage
                const planner = prompt.metadata?.planner_mode;
                if (planner) {
                    plannerUsage[planner] = (plannerUsage[planner] || 0) + 1;
                }

                // Brain enabled
                if (prompt.metadata?.brain_enabled) {
                    brainEnabledCount++;
                }

                // Prompt length
                if (prompt.prompt) {
                    totalPromptLength += prompt.prompt.length;
                }

                // Hourly distribution
                if (prompt.timestamp) {
                    const hour = new Date(prompt.timestamp).getHours();
                    if (hour >= 0 && hour < 24) {
                        hourlyDistribution[hour]++;
                    }
                }
            });

            const responseStats = {
                total_prompts: prompts.length,
                unique_models: Object.keys(modelUsage).length,
                unique_sources: [...new Set(prompts.map(p => p.source))].length,
                avg_prompt_length: prompts.length > 0 ? Math.round(totalPromptLength / prompts.length) : 0,
                brain_enabled_percentage: prompts.length > 0
                    ? Math.round((brainEnabledCount / prompts.length) * 100)
                    : 0,
                model_usage: modelUsage,
                planner_usage: plannerUsage,
                hourly_distribution: hourlyDistribution
            };

            res.json({
                success: true,
                stats: responseStats,
                source: 'files'
            });
        }
    } catch (error) {
        console.error('Error generating stats:', error);
        res.status(500).json({
            success: false,
            error: 'Failed to generate stats',
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
        console.log(`   • GET /prompts/count - Get total count`);
        console.log(`   • GET /prompts/stats - Get statistics`);
        console.log(`   • GET /prompts/models - Get available models`);
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
