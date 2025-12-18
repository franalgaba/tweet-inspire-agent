"""History storage for tweet generations."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

# History storage file
HISTORY_FILE = Path.home() / ".twitter-agent" / "history.json"


def ensure_history_dir():
    """Ensure the history directory exists."""
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create history directory: {e}")
        raise


def load_history() -> list[dict]:
    """Load history from file."""
    ensure_history_dir()
    if not HISTORY_FILE.exists():
        return []
    
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure all entries have IDs
            for i, entry in enumerate(data):
                if 'id' not in entry:
                    entry['id'] = i
            return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse history file: {e}")
        # Backup corrupted file and return empty list
        if HISTORY_FILE.exists():
            backup_file = HISTORY_FILE.with_suffix('.json.bak')
            try:
                HISTORY_FILE.rename(backup_file)
                logger.warning(f"History file corrupted, backed up to {backup_file}")
            except Exception:
                pass
        return []
    except Exception as e:
        logger.error(f"Failed to load history: {e}")
        return []


def save_history(history: list[dict]):
    """Save history to file."""
    ensure_history_dir()
    try:
        # Write to temp file first, then rename (atomic operation)
        temp_file = HISTORY_FILE.with_suffix('.json.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, default=str, ensure_ascii=False)
        temp_file.replace(HISTORY_FILE)
        logger.debug(f"History saved to {HISTORY_FILE}")
    except Exception as e:
        logger.error(f"Failed to save history: {e}")
        raise


def add_history_entry(
    tweet_url: Optional[str],
    username: str,
    original_tweet: Optional[dict],
    proposals: dict,
    research_id: Optional[str] = None,
    prompt: Optional[str] = None,
) -> dict:
    """
    Add a new entry to history.
    
    Returns:
        The created history entry
    """
    try:
        history = load_history()
        
        # Generate unique ID based on timestamp (milliseconds since epoch)
        # Add a small random component to ensure uniqueness if called multiple times quickly
        import time
        entry_id = int(time.time() * 1000000)  # microseconds for better uniqueness
        
        entry = {
            "id": entry_id,
            "tweet_url": tweet_url,
            "username": username,
            "original_tweet": original_tweet,
            "proposals": proposals,
            "research_id": research_id,
            "created_at": datetime.now().isoformat(),
            "preview": _generate_preview(proposals),
            "prompt": prompt,
        }
        
        history.insert(0, entry)  # Add to beginning
        
        # Keep only last 100 entries
        if len(history) > 100:
            history = history[:100]
        
        save_history(history)
        logger.info(f"History entry added: {entry_id} for @{username} (saved to {HISTORY_FILE})")
        return entry
    except Exception as e:
        logger.error(f"Failed to add history entry: {e}", exc_info=True)
        # Don't raise - history is optional, don't break the main flow
        return {}


def _generate_preview(proposals: dict) -> str:
    """Generate a preview text from proposals."""
    previews = []
    
    if proposals.get("quote") and len(proposals["quote"]) > 0:
        content = proposals["quote"][0].get("content", "")
        if isinstance(content, list):
            preview = content[0][:100] if content else ""
        else:
            preview = content[:100]
        if preview:
            previews.append(f"QT: {preview}...")
    
    if proposals.get("tweet") and len(proposals["tweet"]) > 0:
        content = proposals["tweet"][0].get("content", "")
        if isinstance(content, list):
            preview = content[0][:100] if content else ""
        else:
            preview = content[:100]
        if preview:
            previews.append(f"Tweet: {preview}...")
    
    if proposals.get("reply") and len(proposals["reply"]) > 0:
        content = proposals["reply"][0].get("content", "")
        if isinstance(content, list):
            preview = content[0][:100] if content else ""
        else:
            preview = content[:100]
        if preview:
            previews.append(f"Reply: {preview}...")
    
    if proposals.get("thread") and len(proposals["thread"]) > 0:
        content = proposals["thread"][0].get("content", "")
        if isinstance(content, list) and len(content) > 0:
            preview = content[0][:100]
        else:
            preview = str(content)[:100]
        if preview:
            previews.append(f"Thread: {preview}...")
    
    return " | ".join(previews) if previews else "No content generated"


def get_history(limit: Optional[int] = None) -> list[dict]:
    """Get history entries, optionally limited."""
    history = load_history()
    if limit:
        return history[:limit]
    return history


def get_history_entry(entry_id: int) -> Optional[dict]:
    """Get a specific history entry by ID."""
    try:
        history = load_history()
        for entry in history:
            if entry.get("id") == entry_id:
                return entry
        logger.warning(f"History entry {entry_id} not found")
        return None
    except Exception as e:
        logger.error(f"Failed to get history entry: {e}")
        return None


def clear_history() -> bool:
    """Clear all history."""
    try:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
        return True
    except Exception:
        return False

