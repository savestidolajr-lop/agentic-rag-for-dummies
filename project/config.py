import os

# --- Directory Configuration ---
_BASE_DIR = os.path.dirname(__file__)

# DATA_DIR allows persistent storage to be mounted externally (e.g. EFS on ECS).
# Defaults to the project directory for local development.
_DATA_DIR = os.environ.get("DATA_DIR", _BASE_DIR)

MARKDOWN_DIR = os.path.join(_BASE_DIR, "markdown_docs")
PARENT_STORE_PATH = os.path.join(_DATA_DIR, "parent_store")
QDRANT_DB_PATH = os.path.join(_DATA_DIR, "qdrant_db")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
DOCUMENTS_DIR = os.path.join(_DATA_DIR, "documents")
CHECKPOINTS_DB_PATH = os.path.join(_DATA_DIR, "langgraph_checkpoints.db")

# --- Qdrant Configuration ---
CHILD_COLLECTION = "document_child_chunks"
SPARSE_VECTOR_NAME = "sparse"

# --- Model Configuration ---
DENSE_MODEL = "sentence-transformers/all-mpnet-base-v2"
SPARSE_MODEL = "Qdrant/bm25"

# LLM provider configuration
# Supported values: "ollama", "openai", or "anthropic"
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai").lower()

# Ollama defaults
LLM_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct-2507-q4_K_M")

# OpenAI defaults
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Anthropic / Claude defaults
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0"))

# Available models for the UI picker
AVAILABLE_MODELS = {
    "GPT-5 Nano":        ("openai",    "gpt-5-nano"),
    "GPT-5 Mini":        ("openai",    "gpt-5-mini"),
    "GPT-5.4":           ("openai",    "gpt-5.4"),
    "Claude Sonnet 4.6": ("anthropic", "claude-sonnet-4-6"),
    "Claude Haiku 4.5":  ("anthropic", "claude-haiku-4-5-20251001"),
    "Claude Opus 4.6":   ("anthropic", "claude-opus-4-6"),
}

# --- Agent Configuration ---
MAX_TOOL_CALLS = 8
MAX_ITERATIONS = 10
GRAPH_RECURSION_LIMIT = 50
BASE_TOKEN_THRESHOLD = 10000
TOKEN_GROWTH_FACTOR = 0.9

# --- Text Splitter Configuration ---
CHILD_CHUNK_SIZE = 500
CHILD_CHUNK_OVERLAP = 100
MIN_PARENT_SIZE = 2000
MAX_PARENT_SIZE = 12000
HEADERS_TO_SPLIT_ON = [
    ("#", "H1"),
    ("##", "H2"),
    ("###", "H3")
]

# --- Langfuse Observability ---
LANGFUSE_ENABLED = os.environ.get("LANGFUSE_ENABLED", "false").lower() == "true"
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")
LANGFUSE_BASE_URL = os.environ.get("LANGFUSE_BASE_URL", "http://localhost:3000")
