"""Profile health endpoints."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from twitter_agent.api.schemas import HealthRequest, HealthResponse
from twitter_agent.api.services import analyze_profile_health

router = APIRouter(tags=["health"])


@router.post("/health", response_model=HealthResponse)
async def health(request: HealthRequest):
    """Analyze profile health and provide recommendations."""
    try:
        result = analyze_profile_health(
            username=request.username,
            profile_file=request.profile_file,
            max_tweets=request.max_tweets,
            prefer_cache_only=request.prefer_cache_only,
        )
        return HealthResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error analyzing profile health")
        raise HTTPException(
            status_code=500, detail=f"Error analyzing profile health: {str(e)}"
        )
