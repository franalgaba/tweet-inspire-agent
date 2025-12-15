"""History management endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from twitter_agent.api.history import (
    clear_history as clear_history_entries,
    get_history as get_history_entries,
    get_history_entry,
)
from twitter_agent.api.schemas import (
    CacheClearResponse,
    HistoryEntryResponse,
    HistoryResponse,
)

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=HistoryResponse)
async def get_history(limit: Optional[int] = Query(None)):
    """Get history of tweet generations."""
    try:
        entries = get_history_entries(limit=limit)
        return HistoryResponse(entries=entries)
    except Exception as e:
        logger.exception("Error getting history")
        raise HTTPException(status_code=500, detail=f"Error getting history: {str(e)}")


@router.get("/{entry_id}", response_model=HistoryEntryResponse)
async def get_history_entry_by_id(entry_id: int):
    """Get a specific history entry."""
    try:
        entry = get_history_entry(entry_id)
        if not entry:
            raise HTTPException(
                status_code=404, detail=f"History entry {entry_id} not found"
            )
        return HistoryEntryResponse(entry=entry)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting history entry")
        raise HTTPException(
            status_code=500, detail=f"Error getting history entry: {str(e)}"
        )


@router.delete("", response_model=CacheClearResponse)
async def clear_history():
    """Clear all history."""
    try:
        success = clear_history_entries()
        if success:
            return CacheClearResponse(success=True, message="History cleared")
        else:
            raise HTTPException(status_code=500, detail="Failed to clear history")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error clearing history")
        raise HTTPException(status_code=500, detail=f"Error clearing history: {str(e)}")

