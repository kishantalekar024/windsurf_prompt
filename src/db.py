"""
MongoDB database module for storing captured prompts.
"""

import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure
from rich.console import Console

console = Console()


class PromptDB:
    """MongoDB handler for storing and retrieving prompts."""

    def __init__(self, mongo_uri: str = None, db_name: str = "windsurf_prompts"):
        """Initialize MongoDB connection."""
        self.mongo_uri = mongo_uri or os.getenv(
            "MONGO_URI", "mongodb+srv://windsurf_prompt:Ug7vl28TQok7yJkQ@cluster0.fqpyy.mongodb.net/?appName=Cluster0"
        )
        self.db_name = db_name
        self.client: Optional[MongoClient] = None
        self.db = None
        self.prompts_collection = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to MongoDB."""
        try:
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=3000)
            # Test connection
            self.client.admin.command("ping")
            self.db = self.client[self.db_name]
            self.prompts_collection = self.db["prompts"]

            # Create indexes for dashboard queries
            self.prompts_collection.create_index([("timestamp", DESCENDING)])
            self.prompts_collection.create_index("user")
            self.prompts_collection.create_index("model")
            self.prompts_collection.create_index("cascade_id")
            self.prompts_collection.create_index("planner_mode")
            self.prompts_collection.create_index("source")

            self._connected = True
            console.print(f"[green]✓ Connected to MongoDB: {self.db_name}[/green]")
            return True
        except ConnectionFailure as e:
            console.print(f"[yellow]⚠ MongoDB connection failed: {e}[/yellow]")
            console.print("[yellow]  Prompts will only be logged to files[/yellow]")
            self._connected = False
            return False
        except Exception as e:
            console.print(f"[yellow]⚠ MongoDB error: {e}[/yellow]")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        """Check if connected to MongoDB."""
        return self._connected

    def save_prompt(
        self,
        prompt_text: str,
        user: str = "John Doe",
        source: str = "windsurf",
        model: str = "",
        cascade_id: str = "",
        planner_mode: str = "",
        ide_name: str = "",
        ide_version: str = "",
        extension_version: str = "",
        brain_enabled: bool = False,
        prompt_length: int = 0,
        metadata: Dict[str, Any] = None,
        timestamp: datetime = None,
    ) -> Optional[str]:
        """
        Save a captured prompt to MongoDB with all dashboard-relevant fields.

        Args:
            prompt_text: The actual prompt message
            user: Employee/user identifier
            source: Source application (windsurf, cursor, etc.)
            model: AI model used (e.g. MODEL_SWE_1_5_SLOW, MODEL_GPT_5_2_LOW)
            cascade_id: Conversation thread ID
            planner_mode: Planner mode (e.g. CONVERSATIONAL_PLANNER_MODE_DEFAULT)
            ide_name: IDE name (e.g. windsurf)
            ide_version: IDE version (e.g. 1.9544.35)
            extension_version: Extension version (e.g. 1.48.2)
            brain_enabled: Whether Brain feature is enabled
            prompt_length: Character count of the prompt
            metadata: Any additional metadata
            timestamp: When the prompt was captured

        Returns:
            The inserted document ID, or None if save failed
        """
        if not self._connected:
            return None

        try:
            now = timestamp or datetime.utcnow()

            doc = {
                # Core fields
                "prompt": prompt_text,
                "user": user,
                "source": source,
                "timestamp": now,

                # Model & AI config
                "model": model,
                "planner_mode": planner_mode,
                "brain_enabled": brain_enabled,

                # Conversation tracking
                "cascade_id": cascade_id,

                # IDE info
                "ide_name": ide_name,
                "ide_version": ide_version,
                "extension_version": extension_version,

                # Analytics fields
                "prompt_length": prompt_length or len(prompt_text),
                "word_count": len(prompt_text.split()),
                "hour_of_day": now.hour,
                "day_of_week": now.strftime("%A"),
                "date": now.strftime("%Y-%m-%d"),

                # Raw metadata (everything else)
                "metadata": metadata or {},
            }

            result = self.prompts_collection.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            console.print(f"[red]Error saving prompt to MongoDB: {e}[/red]")
            return None

    def get_all_prompts(
        self, limit: int = 100, skip: int = 0, user: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get all prompts from the database.

        Args:
            limit: Maximum number of prompts to return
            skip: Number of prompts to skip (for pagination)
            user: Filter by user (optional)

        Returns:
            List of prompt documents
        """
        if not self._connected:
            return []

        try:
            query = {}
            if user:
                query["user"] = user

            cursor = (
                self.prompts_collection.find(query)
                .sort("timestamp", DESCENDING)
                .skip(skip)
                .limit(limit)
            )

            prompts = []
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
                    doc["timestamp"] = doc["timestamp"].isoformat()
                prompts.append(doc)

            return prompts
        except Exception as e:
            console.print(f"[red]Error fetching prompts from MongoDB: {e}[/red]")
            return []

    def get_prompt_count(self, user: str = None) -> int:
        """Get total count of prompts in the database."""
        if not self._connected:
            return 0

        try:
            query = {}
            if user:
                query["user"] = user
            return self.prompts_collection.count_documents(query)
        except Exception as e:
            console.print(f"[red]Error counting prompts: {e}[/red]")
            return 0

    def get_stats(self, user: str = None) -> Dict[str, Any]:
        """Get aggregated statistics for the dashboard."""
        if not self._connected:
            return {}

        try:
            match_stage = {}
            if user:
                match_stage = {"$match": {"user": user}}

            pipeline = []
            if match_stage:
                pipeline.append(match_stage)

            pipeline.append({
                "$group": {
                    "_id": None,
                    "total_prompts": {"$sum": 1},
                    "unique_users": {"$addToSet": "$user"},
                    "unique_models": {"$addToSet": "$model"},
                    "unique_cascades": {"$addToSet": "$cascade_id"},
                    "avg_prompt_length": {"$avg": "$prompt_length"},
                    "avg_word_count": {"$avg": "$word_count"},
                    "total_words": {"$sum": "$word_count"},
                    "brain_enabled_count": {
                        "$sum": {"$cond": ["$brain_enabled", 1, 0]}
                    },
                    "first_prompt": {"$min": "$timestamp"},
                    "last_prompt": {"$max": "$timestamp"},
                }
            })

            result = list(self.prompts_collection.aggregate(pipeline))

            if not result:
                return {"total_prompts": 0}

            stats = result[0]
            stats.pop("_id", None)
            stats["unique_users"] = len(stats.get("unique_users", []))
            stats["unique_models"] = stats.get("unique_models", [])
            stats["unique_cascades"] = len(stats.get("unique_cascades", []))
            stats["avg_prompt_length"] = round(stats.get("avg_prompt_length", 0), 1)
            stats["avg_word_count"] = round(stats.get("avg_word_count", 0), 1)

            # Convert datetimes
            for key in ["first_prompt", "last_prompt"]:
                if key in stats and isinstance(stats[key], datetime):
                    stats[key] = stats[key].isoformat()

            # Model usage breakdown
            model_pipeline = []
            if match_stage:
                model_pipeline.append(match_stage)
            model_pipeline.append({"$group": {"_id": "$model", "count": {"$sum": 1}}})
            model_pipeline.append({"$sort": {"count": -1}})

            model_usage = {
                doc["_id"]: doc["count"]
                for doc in self.prompts_collection.aggregate(model_pipeline)
                if doc["_id"]
            }
            stats["model_usage"] = model_usage

            # Hourly distribution
            hour_pipeline = []
            if match_stage:
                hour_pipeline.append(match_stage)
            hour_pipeline.append({"$group": {"_id": "$hour_of_day", "count": {"$sum": 1}}})
            hour_pipeline.append({"$sort": {"_id": 1}})

            stats["hourly_distribution"] = {
                str(doc["_id"]): doc["count"]
                for doc in self.prompts_collection.aggregate(hour_pipeline)
                if doc["_id"] is not None
            }

            return stats
        except Exception as e:
            console.print(f"[red]Error getting stats: {e}[/red]")
            return {"error": str(e)}

    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self._connected = False


# Global database instance
_db_instance: Optional[PromptDB] = None


def get_db() -> PromptDB:
    """Get or create the global database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = PromptDB()
        _db_instance.connect()
    return _db_instance
