"""Inspire endpoints - generate content from tweet URLs."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from twitter_agent.api.schemas import (
    InspireRequest,
    InspireResponse,
    RegenerateRequest,
    RegenerateResponse,
)
from twitter_agent.api.services import (
    inspire_from_tweet,
    inspire_from_tweet_with_progress,
    regenerate_from_research,
)

router = APIRouter(prefix="/inspire", tags=["inspire"])


@router.post("", response_model=InspireResponse)
async def inspire(request: InspireRequest):
    """Generate content from a tweet URL or a topic/prompt."""
    # Validation
    if request.content_type != "tweet" and not request.tweet_url:
        raise HTTPException(
            status_code=400, 
            detail=f"Tweet URL is required for content type '{request.content_type}'"
        )

    try:
        original_tweet_dict, proposals_dict, research_id = inspire_from_tweet(
            username=request.username,
            tweet_url=request.tweet_url,
            content_type=request.content_type,
            profile_file=request.profile_file,
            thread_count=request.thread_count,
            vibe=request.vibe,
            deep_research=request.deep_research,
            use_full_content=request.use_full_content,
            context=request.context,
            topic=request.topic,
        )

        # Save to history (non-blocking, don't fail if history save fails)
        try:
            from twitter_agent.api.history import add_history_entry

            add_history_entry(
                tweet_url=request.tweet_url,
                username=request.username,
                original_tweet=original_tweet_dict,
                proposals=proposals_dict,
                research_id=research_id,
                prompt=request.topic,
            )
        except Exception as e:
            logger.warning(f"Failed to save to history: {e}")

        return InspireResponse(
            original_tweet=original_tweet_dict,
            proposals=proposals_dict,
            research_id=research_id,
            prompt=request.topic,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error generating inspired content")
        raise HTTPException(
            status_code=500, detail=f"Error generating inspired content: {str(e)}"
        )


@router.post("/stream")
async def inspire_stream(request: InspireRequest):
    """Generate content from a tweet URL with streaming progress updates."""

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events for progress updates."""
        import queue as std_queue

        event_queue = std_queue.Queue()
        exception_holder: dict[str, Any] = {"error": None}

        def run_generator():
            """Run the synchronous generator in a thread."""
            try:
                for event in inspire_from_tweet_with_progress(
                    username=request.username,
                    tweet_url=request.tweet_url,
                    content_type=request.content_type,
                    profile_file=request.profile_file,
                    thread_count=request.thread_count,
                    vibe=request.vibe,
                    deep_research=request.deep_research,
                    use_full_content=request.use_full_content,
                    context=request.context,
                    topic=request.topic,
                ):
                    event_queue.put(event)
                event_queue.put(None)  # Signal completion
            except Exception as e:
                exception_holder["error"] = e
                event_queue.put(None)  # Signal completion

        # Run the synchronous generator in a thread pool
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(run_generator)

        try:
            while True:
                try:
                    # Poll the queue with a small timeout to allow other coroutines to run
                    try:
                        event = event_queue.get(timeout=0.1)
                    except std_queue.Empty:
                        await asyncio.sleep(0.01)  # Yield control to event loop
                        continue

                    # Check if there was an exception
                    if exception_holder["error"]:
                        error = exception_holder["error"]
                        if isinstance(error, ValueError):
                            yield f"data: {json.dumps({'step': 'error', 'message': str(error)})}\n\n"
                        else:
                            yield f"data: {json.dumps({'step': 'error', 'message': f'Error: {str(error)}'})}\n\n"
                        break

                    # None means generator is done
                    if event is None:
                        break

                    # Yield SSE formatted event
                    yield f"data: {json.dumps(event)}\n\n"

                    # If this is the complete event, save to history
                    if event.get("step") == "complete" and event.get("data"):
                        try:
                            from twitter_agent.api.history import add_history_entry

                            data = event["data"]
                            add_history_entry(
                                tweet_url=request.tweet_url,
                                username=request.username,
                                original_tweet=data.get("original_tweet"),
                                proposals=data.get("proposals", {}),
                                research_id=data.get("research_id"),
                                prompt=request.topic,
                            )
                        except Exception as e:
                            logger.warning(f"Failed to save to history: {e}")
                except Exception as e:
                    logger.error(f"Error in event generator: {e}")
                    yield f"data: {json.dumps({'step': 'error', 'message': f'Error: {str(e)}'})}\n\n"
                    break
        finally:
            executor.shutdown(wait=False)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/regenerate", response_model=RegenerateResponse)
async def regenerate(request: RegenerateRequest):
    """Regenerate content using stored research (no need to research again)."""
    try:
        proposals_dict = regenerate_from_research(
            research_id=request.research_id,
            content_type=request.content_type,
            thread_count=request.thread_count,
            vibe=request.vibe,
            context=request.context,
            suggestions=request.suggestions,
        )
        return RegenerateResponse(proposals=proposals_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error regenerating content")
        raise HTTPException(
            status_code=500, detail=f"Error regenerating content: {str(e)}"
        )
