"""
FastAPI server to expose captured prompts via REST API.
"""

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import json
from pathlib import Path
from threading import Thread

import uvicorn

from db import get_db

app = FastAPI(
    title="Windsurf Prompt Interceptor API",
    description="API to retrieve and analyze captured AI prompts from Windsurf",
    version="1.0.0",
)


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Windsurf Prompt Interceptor API",
        "version": "1.0.0",
        "endpoints": {
            "GET /prompts": "Get all captured prompts (paginated)",
            "GET /prompts/count": "Get total prompt count",
            "GET /prompts/stats": "Get aggregated analytics/statistics",
            "GET /health": "API + DB health check",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    db = get_db()
    return {
        "status": "healthy",
        "mongodb_connected": db.is_connected(),
    }


@app.get("/prompts")
async def get_prompts(
    limit: int = Query(100, ge=1, le=1000, description="Number of prompts to return"),
    skip: int = Query(0, ge=0, description="Number of prompts to skip"),
    user: Optional[str] = Query(None, description="Filter by user"),
) -> Dict[str, Any]:
    """
    Get captured prompts with pagination.

    Returns prompt text, model, cascade_id, planner_mode, IDE info,
    brain status, timestamps, and analytics fields.
    """
    db = get_db()

    # Try MongoDB first
    if db.is_connected():
        prompts = db.get_all_prompts(limit=limit, skip=skip, user=user)
        total = db.get_prompt_count(user=user)

        return {
            "prompts": prompts,
            "total": total,
            "limit": limit,
            "skip": skip,
            "returned": len(prompts),
            "source": "mongodb",
        }

    # Fallback: Read from JSONL files
    prompts = _read_prompts_from_files(user=user)
    total = len(prompts)
    prompts = prompts[skip : skip + limit]

    return {
        "prompts": prompts,
        "total": total,
        "limit": limit,
        "skip": skip,
        "returned": len(prompts),
        "source": "files",
    }


@app.get("/prompts/count")
async def get_prompt_count(
    user: Optional[str] = Query(None, description="Filter by user"),
) -> Dict[str, Any]:
    """Get total count of captured prompts."""
    db = get_db()

    if db.is_connected():
        count = db.get_prompt_count(user=user)
        return {"count": count, "user": user, "source": "mongodb"}

    prompts = _read_prompts_from_files(user=user)
    return {"count": len(prompts), "user": user, "source": "files"}


@app.get("/prompts/stats")
async def get_stats(
    user: Optional[str] = Query(None, description="Filter by user"),
) -> Dict[str, Any]:
    """
    Get aggregated statistics for the prompt dashboard.

    Returns: total_prompts, unique_users, unique_models, model_usage breakdown,
    avg_prompt_length, avg_word_count, hourly_distribution, brain usage, etc.
    """
    db = get_db()

    if not db.is_connected():
        return JSONResponse(
            status_code=503,
            content={
                "error": "Stats require MongoDB connection",
                "message": "Connect MongoDB for aggregated analytics",
            },
        )

    stats = db.get_stats(user=user)
    return {"stats": stats, "user": user}


def _read_prompts_from_files(user: str = None):
    """Read prompts from JSONL log files (fallback when MongoDB unavailable)."""
    prompts = []
    logs_dir = Path("logs")

    if not logs_dir.exists():
        return prompts

    log_files = sorted(logs_dir.glob("prompts_*.jsonl"), reverse=True)

    for log_file in log_files:
        try:
            with open(log_file, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        if user and entry.get("metadata", {}).get("user") != user:
                            continue
                        prompts.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue

    return prompts


def start_api_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the FastAPI server (blocking)."""
    uvicorn.run(app, host=host, port=port, log_level="warning")


def start_api_server_background(host: str = "0.0.0.0", port: int = 8000):
    """Start the FastAPI server in a background thread."""
    thread = Thread(target=start_api_server, args=(host, port), daemon=True)
    thread.start()
    return thread
