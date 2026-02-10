# Database Schema & API Reference

## MongoDB Database: `windsurf_prompts`

### Collection: `prompts`

Each document in the `prompts` collection represents a single captured prompt from a Windsurf user.

### Document Schema

| Field | Type | Description | Example |
|---|---|---|---|
| `_id` | ObjectId | MongoDB auto-generated ID | `"67a9f3..."` |
| **prompt** | String | The actual prompt text sent by the user | `"Refactor this function"` |
| **user** | String | Employee/user identifier | `"default_user"` |
| **source** | String | Source application | `"windsurf"` |
| **timestamp** | DateTime | When the prompt was captured (UTC) | `2026-02-10T06:29:44Z` |
| **model** | String | AI model used for the request | `"MODEL_SWE_1_5_SLOW"`, `"MODEL_GPT_5_2_LOW"` |
| **planner_mode** | String | Windsurf planner mode | `"CONVERSATIONAL_PLANNER_MODE_DEFAULT"` |
| **brain_enabled** | Boolean | Whether Windsurf Brain is active | `true` |
| **cascade_id** | String | Conversation thread ID (groups related prompts) | `"2f7069f5-b5e1-..."` |
| **ide_name** | String | IDE name | `"windsurf"` |
| **ide_version** | String | IDE version | `"1.9544.35"` |
| **extension_version** | String | Codeium extension version | `"1.48.2"` |
| **prompt_length** | Integer | Character count of the prompt | `42` |
| **word_count** | Integer | Word count of the prompt | `7` |
| **hour_of_day** | Integer | Hour (0–23) when the prompt was sent | `14` |
| **day_of_week** | String | Day name | `"Monday"` |
| **date** | String | Date string | `"2026-02-10"` |
| **metadata** | Object | Raw metadata from the intercepted request | `{...}` |

### Indexes

| Index | Fields | Purpose |
|---|---|---|
| Timestamp | `timestamp` (DESC) | Sort by newest first |
| User | `user` | Filter by employee |
| Model | `model` | Filter/group by AI model |
| Cascade | `cascade_id` | Group conversation threads |
| Planner Mode | `planner_mode` | Filter by planner mode |
| Source | `source` | Filter by source app |

---

## REST API

**Base URL:** `http://localhost:8000`

### `GET /`

Returns API info and available endpoints.

**Response:**
```json
{
  "name": "Windsurf Prompt Interceptor API",
  "version": "1.0.0",
  "endpoints": {
    "GET /prompts": "Get all captured prompts (paginated)",
    "GET /prompts/count": "Get total prompt count",
    "GET /prompts/stats": "Get aggregated analytics/statistics",
    "GET /health": "API + DB health check"
  }
}
```

---

### `GET /health`

Health check showing MongoDB connection status.

**Response:**
```json
{
  "status": "healthy",
  "mongodb_connected": true
}
```

---

### `GET /prompts`

Get captured prompts with pagination. Falls back to JSONL files if MongoDB is unavailable.

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 100 | Number of prompts to return (1–1000) |
| `skip` | int | 0 | Number of prompts to skip (pagination) |
| `user` | string | null | Filter by user |

**Example:**
```bash
# Get latest 10 prompts
curl "http://localhost:8000/prompts?limit=10"

# Get prompts for a specific user
curl "http://localhost:8000/prompts?user=default_user"

# Pagination: skip first 20, get next 10
curl "http://localhost:8000/prompts?skip=20&limit=10"
```

**Response:**
```json
{
  "prompts": [
    {
      "_id": "67a9f3a1b2c3d4e5f6a7b8c9",
      "prompt": "hello",
      "user": "default_user",
      "source": "windsurf",
      "timestamp": "2026-02-10T06:29:44",
      "model": "MODEL_SWE_1_5_SLOW",
      "planner_mode": "CONVERSATIONAL_PLANNER_MODE_DEFAULT",
      "brain_enabled": true,
      "cascade_id": "2f7069f5-b5e1-4ca9-974c-d08075f5a024",
      "ide_name": "windsurf",
      "ide_version": "1.9544.35",
      "extension_version": "1.48.2",
      "prompt_length": 5,
      "word_count": 1,
      "hour_of_day": 11,
      "day_of_week": "Monday",
      "date": "2026-02-10",
      "metadata": { ... }
    }
  ],
  "total": 42,
  "limit": 100,
  "skip": 0,
  "returned": 42,
  "source": "mongodb"
}
```

---

### `GET /prompts/count`

Get total number of captured prompts.

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `user` | string | null | Filter by user |

**Example:**
```bash
curl "http://localhost:8000/prompts/count"
```

**Response:**
```json
{
  "count": 42,
  "user": null,
  "source": "mongodb"
}
```

---

### `GET /prompts/stats`

Get aggregated analytics for the prompt dashboard. **Requires MongoDB.**

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `user` | string | null | Filter stats by user |

**Example:**
```bash
curl "http://localhost:8000/prompts/stats"
```

**Response:**
```json
{
  "stats": {
    "total_prompts": 42,
    "unique_users": 3,
    "unique_models": ["MODEL_SWE_1_5_SLOW", "MODEL_GPT_5_2_LOW"],
    "unique_cascades": 12,
    "avg_prompt_length": 87.3,
    "avg_word_count": 14.2,
    "total_words": 597,
    "brain_enabled_count": 38,
    "first_prompt": "2026-02-10T06:00:00",
    "last_prompt": "2026-02-10T12:08:00",
    "model_usage": {
      "MODEL_SWE_1_5_SLOW": 30,
      "MODEL_GPT_5_2_LOW": 12
    },
    "hourly_distribution": {
      "6": 2,
      "7": 5,
      "8": 8,
      "9": 10,
      "10": 7,
      "11": 6,
      "12": 4
    }
  },
  "user": null
}
```

### Stats Fields Explained

| Field | Description | Dashboard Use |
|---|---|---|
| `total_prompts` | Total number of prompts captured | KPI card |
| `unique_users` | Number of distinct employees | KPI card |
| `unique_models` | List of AI models used | Model selector / filter |
| `unique_cascades` | Number of distinct conversations | Conversation count |
| `avg_prompt_length` | Average characters per prompt | Prompt complexity metric |
| `avg_word_count` | Average words per prompt | Prompt complexity metric |
| `total_words` | Total words across all prompts | Usage volume |
| `brain_enabled_count` | Prompts with Brain feature on | Feature adoption |
| `first_prompt` | Timestamp of earliest prompt | Date range |
| `last_prompt` | Timestamp of latest prompt | Date range |
| `model_usage` | Breakdown of prompts per model | Pie/bar chart |
| `hourly_distribution` | Prompts per hour of day | Activity heatmap |

---

## Dashboard Query Ideas

Here are useful MongoDB queries for building an analytics dashboard:

### Prompts per user (leaderboard)
```javascript
db.prompts.aggregate([
  { $group: { _id: "$user", count: { $sum: 1 } } },
  { $sort: { count: -1 } }
])
```

### Most used models
```javascript
db.prompts.aggregate([
  { $group: { _id: "$model", count: { $sum: 1 } } },
  { $sort: { count: -1 } }
])
```

### Prompts per day (trend)
```javascript
db.prompts.aggregate([
  { $group: { _id: "$date", count: { $sum: 1 } } },
  { $sort: { _id: 1 } }
])
```

### Longest prompts
```javascript
db.prompts.find().sort({ prompt_length: -1 }).limit(10)
```

### Brain adoption rate
```javascript
db.prompts.aggregate([
  { $group: {
    _id: null,
    total: { $sum: 1 },
    brain_on: { $sum: { $cond: ["$brain_enabled", 1, 0] } }
  }},
  { $project: {
    adoption_rate: { $multiply: [{ $divide: ["$brain_on", "$total"] }, 100] }
  }}
])
```
