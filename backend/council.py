"""3-stage LLM Council orchestration."""

from typing import List, Dict, Any, Tuple, Optional
from .openrouter import query_models_parallel, query_model
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL, DOMAIN_KEYWORDS, DOMAIN_COUNCILS


def detect_domain(query: str) -> str:
    """Detect the domain of a query for dynamic council selection."""
    query_lower = query.lower()
    scores = {domain: 0 for domain in DOMAIN_KEYWORDS}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query_lower:
                scores[domain] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def get_council_for_query(query: str) -> List[str]:
    """Return the appropriate council models for a given query domain."""
    domain = detect_domain(query)
    return DOMAIN_COUNCILS.get(domain, COUNCIL_MODELS)


async def stage1_collect_responses(
    user_query: str,
) -> tuple[List[Dict[str, Any]], Dict[str, Any], List[str]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (results list, tokens metadata, council models used)
    """
    council = get_council_for_query(user_query)
    messages = [{"role": "user", "content": user_query}]

    # Query all models in parallel
    responses = await query_models_parallel(council, messages)

    # Format results and aggregate tokens
    stage1_results = []
    total_tokens = 0
    total_cost = 0.0

    for model, response in responses.items():
        if response is not None:  # Only include successful responses
            tokens = response.get("tokens", {}).get("total", 0)
            cost = response.get("cost", 0.0)
            total_tokens += tokens
            total_cost += cost

            stage1_results.append(
                {
                    "model": model,
                    "response": response.get("content", ""),
                    "tokens": response.get("tokens", {}),
                    "cost": cost,
                }
            )

    tokens_metadata = {
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 6),
        "model_count": len(stage1_results),
    }

    return stage1_results, tokens_metadata, council


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    council: Optional[List[str]] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, Any]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_model mapping, tokens metadata)
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result["model"]
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join(
        [
            f"Response {label}:\n{result['response']}"
            for label, result in zip(labels, stage1_results)
        ]
    )

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all council models in parallel
    rankers = council if council is not None else COUNCIL_MODELS
    responses = await query_models_parallel(rankers, messages)

    # Format results and aggregate tokens
    stage2_results = []
    total_tokens = 0
    total_cost = 0.0

    for model, response in responses.items():
        if response is not None:
            full_text = response.get("content", "")
            parsed = parse_ranking_from_text(full_text)
            tokens = response.get("tokens", {}).get("total", 0)
            cost = response.get("cost", 0.0)
            total_tokens += tokens
            total_cost += cost

            stage2_results.append(
                {
                    "model": model,
                    "ranking": full_text,
                    "parsed_ranking": parsed,
                    "tokens": response.get("tokens", {}),
                    "cost": cost,
                }
            )

    tokens_metadata = {
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 6),
        "model_count": len(stage2_results),
    }

    return stage2_results, label_to_model, tokens_metadata


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2

    Returns:
        Tuple of (response dict, tokens metadata)
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join(
        [
            f"Model: {result['model']}\nResponse: {result['response']}"
            for result in stage1_results
        ]
    )

    stage2_text = "\n\n".join(
        [
            f"Model: {result['model']}\nRanking: {result['ranking']}"
            for result in stage2_results
        ]
    )

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    response = await query_model(CHAIRMAN_MODEL, messages)

    if response is None:
        # Fallback if chairman fails
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis.",
        }, {"total_tokens": 0, "total_cost": 0.0}

    tokens = response.get("tokens", {}).get("total", 0)
    cost = response.get("cost", 0.0)

    return {
        "model": CHAIRMAN_MODEL,
        "response": response.get("content", ""),
        "tokens": response.get("tokens", {}),
        "cost": cost,
    }, {"total_tokens": tokens, "total_cost": round(cost, 6)}


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r"\d+\.\s*Response [A-Z]", ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [
                    re.search(r"Response [A-Z]", m).group() for m in numbered_matches
                ]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r"Response [A-Z]", ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r"Response [A-Z]", ranking_text)
    return matches


def calculate_consensus(
    stage2_results: List[Dict[str, Any]], label_to_model: Dict[str, str]
) -> Dict[str, Any]:
    """
    Calculate consensus metrics and identify dissenting views.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        Dict with consensus percentage, confidence, and dissenting views
    """
    from collections import defaultdict

    if not stage2_results:
        return {
            "consensus_percentage": 0,
            "confidence": 0.0,
            "dissenting_views": [],
            "top_choice": None,
        }

    # Extract top choice (rank 1) from each model
    top_choices = defaultdict(list)

    for ranking in stage2_results:
        parsed_ranking = ranking.get("parsed_ranking", [])
        if parsed_ranking:
            top_label = parsed_ranking[0]  # First item is rank 1
            model_name = ranking["model"]
            if top_label in label_to_model:
                top_response_model = label_to_model[top_label]
                top_choices[top_response_model].append(model_name)

    if not top_choices:
        return {
            "consensus_percentage": 0,
            "confidence": 0.0,
            "dissenting_views": [],
            "top_choice": None,
        }

    # Find most agreed upon top choice
    max_votes = max(len(voters) for voters in top_choices.values())
    consensus_response = [
        resp for resp, voters in top_choices.items() if len(voters) == max_votes
    ][0]
    consensus_percentage = (max_votes / len(stage2_results)) * 100

    # Confidence: 50% base + (consensus_percentage / 100) * 50%
    confidence = 0.5 + (consensus_percentage / 100) * 0.5

    # Find dissenting views (alternatives with significant support)
    dissenting_views = []
    for response, voters in top_choices.items():
        if response != consensus_response:
            vote_count = len(voters)
            if vote_count >= 1:  # If even 1 model voted differently
                dissenting_views.append(
                    {
                        "response_model": response,
                        "vote_count": vote_count,
                        "voter_models": voters,
                        "percentage": (vote_count / len(stage2_results)) * 100,
                    }
                )

    # Sort dissenting views by vote count descending
    dissenting_views.sort(key=lambda x: x["vote_count"], reverse=True)

    return {
        "consensus_percentage": round(consensus_percentage, 1),
        "confidence": round(confidence, 2),
        "top_choice": consensus_response,
        "dissenting_views": dissenting_views,
        "total_voters": len(stage2_results),
    }


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]], label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking["ranking"]

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append(
                {
                    "model": model,
                    "average_rank": round(avg_rank, 2),
                    "rankings_count": len(positions),
                }
            )

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x["average_rank"])

    return aggregate


def calculate_weighted_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
    ranker_weights: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Weighted version of calculate_aggregate_rankings.
    Rankers with higher historical accuracy get more influence.
    Falls back to equal weights if ranker_weights is None or empty.
    """
    from collections import defaultdict

    model_weighted_sum: Dict[str, float] = defaultdict(float)
    model_total_weight: Dict[str, float] = defaultdict(float)
    model_counts: Dict[str, int] = defaultdict(int)

    for ranking in stage2_results:
        ranker = ranking["model"]
        weight = (ranker_weights or {}).get(ranker, 1.0)
        parsed = parse_ranking_from_text(ranking["ranking"])

        for position, label in enumerate(parsed, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_weighted_sum[model_name] += position * weight
                model_total_weight[model_name] += weight
                model_counts[model_name] += 1

    aggregate = []
    for model_name, total_weight in model_total_weight.items():
        if total_weight > 0:
            aggregate.append(
                {
                    "model": model_name,
                    "average_rank": round(
                        model_weighted_sum[model_name] / total_weight, 2
                    ),
                    "rankings_count": model_counts[model_name],
                }
            )

    aggregate.sort(key=lambda x: x["average_rank"])
    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use gemini-2.5-flash for title generation (fast and cheap)
    response = await query_model(
        "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
        messages,
        timeout=30.0,
    )

    if response is None:
        # Fallback to a generic title
        return "New Conversation"

    title = response.get("content", "New Conversation").strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip("\"'")

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(user_query: str) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    from . import storage as _storage

    # Stage 1: Collect individual responses (domain-aware council selection)
    stage1_results, stage1_tokens, council = await stage1_collect_responses(user_query)

    # If no models responded successfully, return error
    if not stage1_results:
        return (
            [],
            [],
            {
                "model": "error",
                "response": "All models failed to respond. Please try again.",
            },
            {},
        )

    # Stage 2: Collect rankings using the same council
    stage2_results, label_to_model, stage2_tokens = await stage2_collect_rankings(
        user_query, stage1_results, council
    )

    # Load historical ranker weights for weighted aggregate rankings
    try:
        ranker_weights = _storage.get_ranker_weights()
    except Exception:
        ranker_weights = {}

    # Calculate aggregate rankings (weighted by historical accuracy)
    aggregate_rankings = calculate_weighted_aggregate_rankings(
        stage2_results, label_to_model, ranker_weights
    )

    # Calculate consensus and dissenting views
    consensus_info = calculate_consensus(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result, stage3_tokens = await stage3_synthesize_final(
        user_query, stage1_results, stage2_results
    )

    # Prepare metadata with token tracking
    total_cost = (
        stage1_tokens["total_cost"]
        + stage2_tokens["total_cost"]
        + stage3_tokens["total_cost"]
    )

    total_tokens = (
        stage1_tokens["total_tokens"]
        + stage2_tokens["total_tokens"]
        + stage3_tokens["total_tokens"]
    )

    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "consensus": consensus_info,
        "domain": detect_domain(user_query),
        "tokens": {
            "stage1": stage1_tokens,
            "stage2": stage2_tokens,
            "stage3": stage3_tokens,
            "total": total_tokens,
        },
        "cost": {
            "stage1": stage1_tokens["total_cost"],
            "stage2": stage2_tokens["total_cost"],
            "stage3": stage3_tokens["total_cost"],
            "total": round(total_cost, 6),
        },
    }

    return stage1_results, stage2_results, stage3_result, metadata
