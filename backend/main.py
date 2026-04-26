"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid
import json
import asyncio

from . import storage
from .council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
    calculate_weighted_aggregate_rankings,
    calculate_consensus,
    detect_domain,
)

app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""

    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""

    content: str


class FeedbackRequest(BaseModel):
    """User feedback for an assistant message."""

    rating: int  # 1 = thumbs up, -1 = thumbs down
    comment: str = ""


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""

    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""

    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.get("/api/conversations/search")
async def search_conversations(q: str = ""):
    """Search conversations by title or message content."""
    if len(q.strip()) < 2:
        return []
    return storage.search_conversations(q.strip())


@app.get("/api/analytics/leaderboard")
async def get_leaderboard():
    """Model performance leaderboard based on peer rankings and user feedback."""
    from collections import defaultdict

    all_convs = storage.get_all_conversations_data()
    model_stats: Dict[str, Any] = defaultdict(
        lambda: {
            "appearances": 0,
            "rank_positions": [],
            "wins": 0,
            "thumbs_up": 0,
            "thumbs_down": 0,
        }
    )

    for conv in all_convs:
        for msg in conv["messages"]:
            if msg["role"] != "assistant":
                continue
            feedback_rating = msg.get("feedback", {}).get("rating", 0)
            aggregate = msg.get("aggregate_rankings", [])
            stage1 = msg.get("stage1", [])

            for item in stage1:
                m = item["model"]
                model_stats[m]["appearances"] += 1
                if feedback_rating == 1:
                    model_stats[m]["thumbs_up"] += 1
                elif feedback_rating == -1:
                    model_stats[m]["thumbs_down"] += 1

            for i, rank_item in enumerate(aggregate):
                m = rank_item["model"]
                model_stats[m]["rank_positions"].append(rank_item["average_rank"])
                if i == 0:
                    model_stats[m]["wins"] += 1

    result = []
    for model, stats in model_stats.items():
        positions = stats["rank_positions"]
        avg_rank = round(sum(positions) / len(positions), 2) if positions else None
        win_rate = round(stats["wins"] / len(positions) * 100, 1) if positions else 0.0
        short_name = model.split("/")[1] if "/" in model else model
        result.append(
            {
                "model": model,
                "short_name": short_name,
                "appearances": stats["appearances"],
                "wins": stats["wins"],
                "avg_rank": avg_rank,
                "win_rate": win_rate,
                "thumbs_up": stats["thumbs_up"],
                "thumbs_down": stats["thumbs_down"],
            }
        )

    result.sort(key=lambda x: (-(x["win_rate"]), x["avg_rank"] or 99))
    return result


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/messages/{message_index}/feedback")
async def submit_feedback(
    conversation_id: str, message_index: int, request: FeedbackRequest
):
    """Submit thumbs up/down feedback for an assistant message."""
    if request.rating not in (1, -1):
        raise HTTPException(status_code=400, detail="Rating must be 1 or -1")
    try:
        storage.save_feedback(
            conversation_id, message_index, request.rating, request.comment
        )
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content
    )

    # Add assistant message with all stages (persist metadata for leaderboard)
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result,
        metadata=metadata,
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata,
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(
                    generate_conversation_title(request.content)
                )

            # Stage 1: Collect responses (domain-aware council selection)
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results, stage1_tokens, council = await stage1_collect_responses(
                request.content
            )
            domain = detect_domain(request.content)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results, 'tokens': stage1_tokens, 'domain': domain})}\n\n"

            # Stage 2: Collect rankings using same council
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            (
                stage2_results,
                label_to_model,
                stage2_tokens,
            ) = await stage2_collect_rankings(request.content, stage1_results, council)
            ranker_weights = storage.get_ranker_weights()
            aggregate_rankings = calculate_weighted_aggregate_rankings(
                stage2_results, label_to_model, ranker_weights
            )
            consensus_info = calculate_consensus(stage2_results, label_to_model)

            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings, 'consensus': consensus_info}, 'tokens': stage2_tokens})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result, stage3_tokens = await stage3_synthesize_final(
                request.content, stage1_results, stage2_results
            )

            # Calculate full summary
            total_cost = (
                stage1_tokens["total_cost"]
                + stage2_tokens["total_cost"]
                + stage3_tokens["total_cost"]
            )
            total_tokens_sum = (
                stage1_tokens["total_tokens"]
                + stage2_tokens["total_tokens"]
                + stage3_tokens["total_tokens"]
            )

            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result, 'tokens': stage3_tokens})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message with metadata for leaderboard
            metadata = {
                "label_to_model": label_to_model,
                "aggregate_rankings": aggregate_rankings,
            }
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result,
                metadata=metadata,
            )

            # Send final summary with total costs
            yield f"data: {json.dumps({'type': 'summary', 'data': {'total_tokens': total_tokens_sum, 'total_cost': round(total_cost, 6), 'consensus': consensus_info}})}\n\n"

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
