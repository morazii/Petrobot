"""
backend/db/mongo_client.py
--------------------------
Singleton MongoDB client for the PetroBot project.

Usage:
    from backend.db.mongo_client import get_wells_collection

    wells = get_wells_collection()
    doc = wells.find_one({"data.Name": "Delta-15"})
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise EnvironmentError(
        "MONGO_URI is not set. Create a .env file with your MongoDB Atlas connection string.\n"
        "Example: MONGO_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/petrobot?retryWrites=true&w=majority"
    )

# Extract database name from URI — works for both Atlas (mongodb+srv://) and local (mongodb://)
# e.g. "mongodb+srv://user:pass@cluster.mongodb.net/petrobot?..." -> "petrobot"
_uri_path = MONGO_URI.split("/")
DB_NAME = _uri_path[-1].split("?")[0] if len(_uri_path) >= 4 else "petrobot"


@lru_cache(maxsize=1)
def _get_client() -> MongoClient:
    """Return a cached MongoClient instance (one per process)."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5_000)
    # Trigger a connection check immediately so failures are caught early
    client.admin.command("ping")
    return client


def get_db():
    """Return the petrobot database handle."""
    return _get_client()[DB_NAME]


def get_wells_collection() -> Collection:
    """Return the `wells` collection inside the petrobot database."""
    return get_db()["wells"]


def get_wells_flat_collection() -> Collection:
    """Return the `wells_flat` collection inside the petrobot database."""
    return get_db()["wells_flat"]


def ping() -> bool:
    """Return True if MongoDB is reachable, False otherwise."""
    try:
        _get_client().admin.command("ping")
        return True
    except Exception:
        return False
