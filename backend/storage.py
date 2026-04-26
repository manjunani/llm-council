"""JSON-based storage for conversations."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR

FEEDBACK_FILE = "data/feedback_stats.json"


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """Get the file path for a conversation."""
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Create a new conversation.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        New conversation dict
    """
    ensure_data_dir()

    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "messages": []
    }

    # Save to file
    path = get_conversation_path(conversation_id)
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)

    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    path = get_conversation_path(conversation_id)

    if not os.path.exists(path):
        return None

    with open(path, 'r') as f:
        return json.load(f)


def save_conversation(conversation: Dict[str, Any]):
    """
    Save a conversation to storage.

    Args:
        conversation: Conversation dict to save
    """
    ensure_data_dir()

    path = get_conversation_path(conversation['id'])
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)


def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts
    """
    ensure_data_dir()

    conversations = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
            path = os.path.join(DATA_DIR, filename)
            with open(path, 'r') as f:
                data = json.load(f)
                # Return metadata only
                conversations.append({
                    "id": data["id"],
                    "created_at": data["created_at"],
                    "title": data.get("title", "New Conversation"),
                    "message_count": len(data["messages"])
                })

    # Sort by creation time, newest first
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

    return conversations


def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "user",
        "content": content
    })

    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
        metadata: Optional metadata including label_to_model and aggregate_rankings
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    msg: Dict[str, Any] = {
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3,
    }

    if metadata:
        msg["label_to_model"] = metadata.get("label_to_model")
        msg["aggregate_rankings"] = metadata.get("aggregate_rankings")

    conversation["messages"].append(msg)
    save_conversation(conversation)


def save_feedback(conversation_id: str, message_index: int, rating: int, comment: str = ""):
    """
    Save user feedback (thumbs up/down) for an assistant message.

    Args:
        conversation_id: Conversation identifier
        message_index: Index of the message in the conversation
        rating: 1 for thumbs up, -1 for thumbs down
        comment: Optional text feedback
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    if message_index >= len(conversation["messages"]):
        raise ValueError(f"Message index {message_index} out of range")
    msg = conversation["messages"][message_index]
    if msg["role"] != "assistant":
        raise ValueError("Can only rate assistant messages")

    msg["feedback"] = {
        "rating": rating,
        "comment": comment,
        "created_at": datetime.utcnow().isoformat(),
    }

    save_conversation(conversation)


def search_conversations(query: str) -> List[Dict[str, Any]]:
    """
    Search conversations by title or user message content.

    Args:
        query: Search string

    Returns:
        List of matching conversation metadata dicts
    """
    ensure_data_dir()
    q = query.lower()
    results = []
    seen: set = set()

    for filename in os.listdir(DATA_DIR):
        if not filename.endswith('.json'):
            continue
        path = os.path.join(DATA_DIR, filename)
        with open(path, 'r') as f:
            data = json.load(f)

        matched = q in data.get("title", "").lower()
        if not matched:
            for msg in data["messages"]:
                if msg["role"] == "user" and q in msg.get("content", "").lower():
                    matched = True
                    break

        if matched and data["id"] not in seen:
            seen.add(data["id"])
            results.append({
                "id": data["id"],
                "created_at": data["created_at"],
                "title": data.get("title", "New Conversation"),
                "message_count": len(data["messages"]),
            })

    results.sort(key=lambda x: x["created_at"], reverse=True)
    return results


def get_all_conversations_data() -> List[Dict[str, Any]]:
    """
    Load full data for all conversations (for analytics/leaderboard).

    Returns:
        List of full conversation dicts
    """
    ensure_data_dir()
    result = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
            path = os.path.join(DATA_DIR, filename)
            with open(path, 'r') as f:
                result.append(json.load(f))
    return result


def get_ranker_weights() -> Dict[str, float]:
    """
    Compute per-model ranker weights from historical feedback.
    A model whose #1 picks correlate with thumbs-up gets higher weight.

    Returns:
        Dict mapping model name to weight (default 1.0)
    """
    all_convs = get_all_conversations_data()
    model_correct: Dict[str, int] = {}
    model_total: Dict[str, int] = {}

    for conv in all_convs:
        for msg in conv["messages"]:
            if msg["role"] != "assistant":
                continue
            rating = msg.get("feedback", {}).get("rating", 0)
            if rating == 0:
                continue
            aggregate = msg.get("aggregate_rankings", [])
            stage2 = msg.get("stage2", [])

            for ranker in stage2:
                ranker_model = ranker["model"]
                parsed = ranker.get("parsed_ranking", [])
                if not parsed:
                    continue
                top_label = parsed[0]
                label_to_model = msg.get("label_to_model", {})
                top_model = label_to_model.get(top_label)

                # Check if ranker's #1 pick matches aggregate winner
                if aggregate and top_model == aggregate[0]["model"]:
                    model_correct[ranker_model] = model_correct.get(ranker_model, 0) + (1 if rating == 1 else 0)
                model_total[ranker_model] = model_total.get(ranker_model, 0) + 1

    weights: Dict[str, float] = {}
    for model, total in model_total.items():
        correct = model_correct.get(model, 0)
        accuracy = correct / total if total > 0 else 0.5
        # Weight range: 0.5 to 1.5 based on accuracy
        weights[model] = 0.5 + accuracy
    return weights


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation)
