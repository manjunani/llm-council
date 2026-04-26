"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of OpenRouter model identifiers
COUNCIL_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-120b:free",
    "tencent/hy3-preview:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

# Domain detection keywords
DOMAIN_KEYWORDS = {
    "code": [
        "code",
        "python",
        "javascript",
        "typescript",
        "function",
        "debug",
        "error",
        "api",
        "sql",
        "algorithm",
        "bug",
        "class",
        "programming",
        "react",
        "css",
        "html",
        "git",
        "bash",
        "script",
        "compile",
        "runtime",
        "refactor",
        "test",
        "unittest",
        "async",
        "database",
        "query",
    ],
    "science": [
        "research",
        "study",
        "experiment",
        "hypothesis",
        "data",
        "analysis",
        "paper",
        "journal",
        "science",
        "biology",
        "chemistry",
        "physics",
        "math",
        "statistics",
        "machine learning",
        "neural",
        "model",
        "dataset",
        "proof",
        "theorem",
        "equation",
    ],
    "creative": [
        "write",
        "story",
        "poem",
        "creative",
        "fiction",
        "character",
        "plot",
        "essay",
        "blog",
        "script",
        "narrative",
        "novel",
        "dialogue",
        "lyrics",
        "brainstorm",
        "idea",
        "imagine",
    ],
}

# Domain-specific council configurations (can be customized per domain)
DOMAIN_COUNCILS = {
    "code": COUNCIL_MODELS,
    "science": COUNCIL_MODELS,
    "creative": COUNCIL_MODELS,
    "general": COUNCIL_MODELS,
}
