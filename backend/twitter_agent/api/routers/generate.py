"""Content generation endpoints."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from twitter_agent.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    GenerateRequest,
    GenerateResponse,
    ProposeRequest,
    ProposeResponse,
    CheckResponse,
)
from twitter_agent.api.services import (
    analyze_voice,
    check_configuration,
    generate_content,
    propose_content,
)

router = APIRouter(tags=["generate"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """Analyze a Twitter user's voice."""
    try:
        profile_dict, saved_path = analyze_voice(
            username=request.username,
            max_tweets=request.max_tweets,
            save_profile=request.save_profile,
        )
        return AnalyzeResponse(profile=profile_dict, saved_path=saved_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error analyzing voice")
        raise HTTPException(status_code=500, detail=f"Error analyzing voice: {str(e)}")


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """Generate content proposals."""
    try:
        proposals = generate_content(
            username=request.username,
            content_type=request.content_type,
            count=request.count,
            content_dir=request.content_dir,
            calendar_file=request.calendar_file,
            use_analytics=request.use_analytics,
            use_calendar=request.use_calendar,
            profile_file=request.profile_file,
            topic=request.topic,
            thread_count=request.thread_count,
        )
        return GenerateResponse(proposals=proposals)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error generating content")
        raise HTTPException(status_code=500, detail=f"Error generating content: {str(e)}")


@router.post("/propose", response_model=ProposeResponse)
async def propose(request: ProposeRequest):
    """Propose content based on criteria."""
    try:
        proposals = propose_content(
            username=request.username,
            based_on=request.based_on,
            content_dir=request.content_dir,
            calendar_file=request.calendar_file,
            count=request.count,
        )
        return ProposeResponse(proposals=proposals)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error proposing content")
        raise HTTPException(status_code=500, detail=f"Error proposing content: {str(e)}")


@router.get("/check", response_model=CheckResponse)
async def check():
    """Check configuration and dependencies."""
    try:
        result = check_configuration()
        return CheckResponse(**result)
    except Exception as e:
        logger.exception("Error checking configuration")
        raise HTTPException(
            status_code=500, detail=f"Error checking configuration: {str(e)}"
        )

