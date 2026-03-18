import os
import uuid
import shutil
import sqlite3
import subprocess
import time

import requests

import config
from langgraph.checkpoint.sqlite import SqliteSaver
from db.vector_db_manager import VectorDbManager
from db.parent_store_manager import ParentStoreManager
from document_chunker import DocumentChuncker
from rag_agent.tools import ToolFactory
from rag_agent.graph import create_agent_graph
from core.observability import Observability


def _create_llm(provider: str | None = None, model: str | None = None, temperature: float | None = None):
    """Create an LLM instance for the given provider/model (or from config defaults)."""
    from core.admin_config import get as _cfg_get
    provider = (provider or config.LLM_PROVIDER).lower()
    temp = temperature if temperature is not None else _cfg_get("temperature", config.LLM_TEMPERATURE)

    if provider == "anthropic":
        api_key = config.ANTHROPIC_API_KEY
        model = model or config.ANTHROPIC_MODEL
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured. Set it in your .env file.")
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise ImportError("langchain-anthropic is required. Install it with `pip install langchain-anthropic`.") from exc
        return ChatAnthropic(model=model, temperature=temp, api_key=api_key)

    if provider == "openai":
        model = model or config.OPENAI_MODEL
        if not config.OPENAI_API_KEY:
            class _MissingKeyLLM:
                def bind_tools(self, tools): return self
                def with_config(self, **kwargs): return self
                def with_structured_output(self, schema): return self
                def invoke(self, *args, **kwargs):
                    class Resp:
                        content = "OPENAI_API_KEY is not configured. Set it in your .env file."
                        tool_calls = []; questions = []; is_clear = True; clarification_needed = ""
                    return Resp()
            return _MissingKeyLLM()
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise ImportError("langchain-openai is required. Install it with `pip install langchain-openai`.") from exc
        return ChatOpenAI(model=model, temperature=temp, api_key=config.OPENAI_API_KEY)

    # Ollama
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:
        raise ImportError("langchain-ollama is required. Install it with `pip install langchain-ollama`.") from exc
    return ChatOllama(model=model or config.LLM_MODEL, temperature=temp)


def _is_qdrant_running(url: str | None = None) -> bool:
    # Allow overriding via config (e.g. when Qdrant is running as a separate service).
    if url is None:
        url = f"{config.QDRANT_URL.rstrip('/')}/collections"
    try:
        resp = requests.get(url, timeout=1)
        return resp.status_code == 200
    except Exception:
        return False


def _attempt_start_qdrant(config_path: str, timeout: int = 15) -> bool:
    """Try to start a local Qdrant server if it's not already running."""
    if _is_qdrant_running():
        return True

    if not shutil.which("qdrant"):
        print("⚠️  'qdrant' binary not found in PATH. Please install Qdrant or run it separately.")
        return False

    print("⛏️  Starting local Qdrant server...")
    try:
        subprocess.Popen(
            ["qdrant", "--config-path", config_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"⚠️  Unable to start Qdrant process: {e}")
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_qdrant_running():
            print("✅ Qdrant is running.")
            return True
        time.sleep(0.5)

    print("⚠️  Qdrant did not become available within the timeout period.")
    return False


class RAGSystem:
    
    def __init__(self, collection_name=config.CHILD_COLLECTION):
        self.collection_name = collection_name
        self.vector_db = VectorDbManager()
        self.parent_store = ParentStoreManager()
        self.chunker = DocumentChuncker()
        self.observability = Observability()
        self.agent_graph = None
        self.thread_id = str(uuid.uuid4())
        self.recursion_limit = config.GRAPH_RECURSION_LIMIT

        # Persistent SQLite checkpointer — survives restarts and model switches
        _conn = sqlite3.connect(config.CHECKPOINTS_DB_PATH, check_same_thread=False)
        self._checkpointer = SqliteSaver(_conn)

        # Auto-start local Qdrant when the system is initialized (if not already running)
        self._qdrant_started = False
        self._qdrant_config_path = os.path.join(os.path.dirname(__file__), "..", "qdrant_config.yaml")
        self._state_filter = None
        self._health_cache = None
        
    def initialize(self):
        # Only attempt to start a local Qdrant process when no remote URL is configured.
        is_remote = not config.QDRANT_URL.startswith("http://localhost") and not config.QDRANT_URL.startswith("http://127.0.0.1")
        if not self._qdrant_started and not is_remote:
            self._qdrant_started = _attempt_start_qdrant(self._qdrant_config_path)
        elif is_remote:
            self._qdrant_started = True

        self.vector_db.create_collection(self.collection_name)
        collection = self.vector_db.get_collection(self.collection_name)

        llm = _create_llm()
        self.tool_factory = ToolFactory(collection)
        tools = self.tool_factory.create_tools()
        self.agent_graph = create_agent_graph(llm, tools, self._checkpointer)
        self._active_provider = config.LLM_PROVIDER
        self._active_model = config.OPENAI_MODEL if config.LLM_PROVIDER == "openai" else (
            config.ANTHROPIC_MODEL if config.LLM_PROVIDER == "anthropic" else config.LLM_MODEL
        )

    def switch_model(self, provider: str, model: str):
        """Hot-swap the LLM without restarting. Rebuilds the agent graph with the new model."""
        llm = _create_llm(provider, model)
        tools = self.tool_factory.create_tools()
        self.agent_graph = create_agent_graph(llm, tools, self._checkpointer)
        self._active_provider = provider
        self._active_model = model
        self._health_cache = None  # invalidate health cache
        
    def apply_settings(self):
        """Rebuild the LLM graph picking up new temperature from admin_config."""
        print("⚙️  Applying admin settings — rebuilding LLM...")
        llm = _create_llm(self._active_provider, self._active_model)
        tools = self.tool_factory.create_tools()
        self.agent_graph = create_agent_graph(llm, tools, self._checkpointer)
        self._health_cache = None
        print("✓ LLM rebuilt with updated settings.")

    def set_state_filter(self, state: str | None):
        """Set a namespace/state filter used during document retrieval."""
        self._state_filter = state
        if hasattr(self, "tool_factory") and self.tool_factory:
            self.tool_factory.set_state_filter(state)

    def get_state_filter(self) -> str | None:
        return self._state_filter

    def get_health(self, refresh: bool = False):
        """Return a dict representing system health checks.

        Includes Qdrant reachability and, if using OpenAI, whether the API key is present and works.
        """
        if self._health_cache and not refresh:
            return self._health_cache

        active_provider = getattr(self, "_active_provider", config.LLM_PROVIDER)
        active_model = getattr(self, "_active_model", "")

        health = {
            "qdrant": _is_qdrant_running(),
            "llm": False,
            "llm_error": None,
            "api_key_present": bool(config.OPENAI_API_KEY or config.ANTHROPIC_API_KEY),
            "active_provider": active_provider,
            "active_model": active_model,
        }

        if active_provider == "openai":
            if not config.OPENAI_API_KEY:
                health["llm_error"] = "OPENAI_API_KEY is not set."
            else:
                try:
                    from openai import OpenAI
                    OpenAI(api_key=config.OPENAI_API_KEY).models.list()
                    health["llm"] = True
                except Exception as e:
                    health["llm_error"] = str(e)
        elif active_provider == "anthropic":
            if not config.ANTHROPIC_API_KEY:
                health["llm_error"] = "ANTHROPIC_API_KEY is not set."
            else:
                health["llm"] = True  # key present; skip a live call to avoid latency
        else:
            health["llm"] = True

        self._health_cache = health
        return health

    def get_config(self, thread_id: str | None = None):
        cfg = {
            "configurable": {"thread_id": thread_id or self.thread_id},
            "recursion_limit": self.recursion_limit,
        }
        handler = self.observability.get_handler()
        if handler:
            cfg["callbacks"] = [handler]
        return cfg
    
    def reset_thread(self, thread_id: str | None = None):
        target = thread_id or self.thread_id
        try:
            self.agent_graph.checkpointer.delete_thread(target)
        except Exception as e:
            print(f"Warning: Could not delete thread {target}: {e}")
        if not thread_id:
            self.thread_id = str(uuid.uuid4())