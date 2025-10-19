"""User preferences storage management for Sport Agent.

This module handles persistent storage of user sport preferences using JSON files.
Implements simple file-based storage without external database dependencies.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import threading

PREFERENCES_FILE = Path(__file__).parent / "data" / "user_preferences.json"

# Thread lock for file access safety
_file_lock = threading.Lock()


def _ensure_file_exists():
    """Ensure preferences file and directory exist."""
    PREFERENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not PREFERENCES_FILE.exists():
        with open(PREFERENCES_FILE, 'w') as f:
            json.dump({"users": {}}, f, indent=2)


def _load_all_data() -> Dict:
    """Load all data from preferences file."""
    _ensure_file_exists()
    with _file_lock:
        with open(PREFERENCES_FILE, 'r') as f:
            return json.load(f)


def _save_all_data(data: Dict):
    """Save all data to preferences file."""
    _ensure_file_exists()
    with _file_lock:
        with open(PREFERENCES_FILE, 'w') as f:
            json.dump(data, f, indent=2)


def load_preferences(user_id: str) -> Optional[Dict]:
    """Load user preferences from JSON file.
    
    Args:
        user_id: Unique user identifier
        
    Returns:
        Dictionary containing user preferences or None if not found
    """
    data = _load_all_data()
    return data.get("users", {}).get(user_id)


def save_preferences(user_id: str, preferences: Dict) -> bool:
    """Save user preferences to JSON file.
    
    Args:
        user_id: Unique user identifier
        preferences: Dictionary containing user sport preferences
        
    Returns:
        True if save was successful, False otherwise
    """
    try:
        data = _load_all_data()
        if "users" not in data:
            data["users"] = {}
        data["users"][user_id] = preferences
        _save_all_data(data)
        return True
    except Exception as e:
        print(f"Error saving preferences for user {user_id}: {e}")
        return False


def list_all_users() -> List[str]:
    """Get all user IDs with stored preferences.
    
    Returns:
        List of user IDs
    """
    data = _load_all_data()
    return list(data.get("users", {}).keys())


def delete_preferences(user_id: str) -> bool:
    """Delete user preferences.
    
    Args:
        user_id: Unique user identifier
        
    Returns:
        True if deletion was successful, False if user not found
    """
    try:
        data = _load_all_data()
        if user_id in data.get("users", {}):
            del data["users"][user_id]
            _save_all_data(data)
            return True
        return False
    except Exception as e:
        print(f"Error deleting preferences for user {user_id}: {e}")
        return False


def save_digest_history(user_id: str, digest: str, timestamp: str) -> bool:
    """Save generated digest to user's history.
    
    Args:
        user_id: Unique user identifier
        digest: Generated digest content
        timestamp: ISO format timestamp
        
    Returns:
        True if save was successful
    """
    try:
        data = _load_all_data()
        if user_id not in data.get("users", {}):
            return False
            
        if "digest_history" not in data["users"][user_id]:
            data["users"][user_id]["digest_history"] = []
            
        data["users"][user_id]["digest_history"].append({
            "digest": digest,
            "timestamp": timestamp
        })
        
        # Keep only last 30 digests
        data["users"][user_id]["digest_history"] = \
            data["users"][user_id]["digest_history"][-30:]
            
        _save_all_data(data)
        return True
    except Exception as e:
        print(f"Error saving digest history for user {user_id}: {e}")
        return False


def get_digest_history(user_id: str, limit: int = 10) -> List[Dict]:
    """Get user's digest history.
    
    Args:
        user_id: Unique user identifier
        limit: Maximum number of digests to return
        
    Returns:
        List of digest history entries
    """
    data = _load_all_data()
    user_data = data.get("users", {}).get(user_id)
    if not user_data:
        return []
    
    history = user_data.get("digest_history", [])
    return history[-limit:]

