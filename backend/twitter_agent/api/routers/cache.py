"""Cache management endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from twitter_agent.api.schemas import CacheClearResponse, CacheInfoResponse
from twitter_agent.api.services import clear_cache, get_cache_info

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/info", response_model=CacheInfoResponse)
async def cache_info(username: Optional[str] = Query(None)):
    """Get cache information."""
    try:
        cache_info_dict = get_cache_info(username=username)
        return CacheInfoResponse(cache_info=cache_info_dict)
    except Exception as e:
        logger.exception("Error getting cache info")
        raise HTTPException(status_code=500, detail=f"Error getting cache info: {str(e)}")


@router.delete("/clear", response_model=CacheClearResponse)
async def cache_clear(username: Optional[str] = Query(None)):
    """Clear cache."""
    try:
        result = clear_cache(username=username)
        return CacheClearResponse(**result)
    except Exception as e:
        logger.exception("Error clearing cache")
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")

