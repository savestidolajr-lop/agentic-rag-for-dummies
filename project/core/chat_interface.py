import json
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage

_PENDING = "__PENDING__"
_INTERRUPTED = "⚠️ Response interrupted — please resend your message."


class ChatInterface:
    def __init__(self, rag_system):
        self.rag_system = rag_system
        self.history_path = Path(__file__).resolve().parents[1] / "chat_history.json"
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="ai_worker")
        self._cancelled: set = set()
        self._ensure_history_file()
        self.cleanup_stale_pending()   # convert orphaned PENDING from prior crashes/restarts

    def _ensure_history_file(self):
        if not self.history_path.exists():
            self.history_path.write_text("[]", encoding="utf-8")

    # ── File I/O (always call under self._lock) ───────────────────────────────

    def _load_history(self):
        if not self.history_path.exists():
            return []
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        # Legacy flat-list format
        if data and isinstance(data, list) and isinstance(data[0], dict) and "role" in data[0]:
            return [{
                "session_id": str(uuid.uuid4()),
                "created_at": datetime.utcnow().isoformat() + "Z",
                "title": "Legacy Chat",
                "messages": data,
            }]
        return data

    def _save_history(self, sessions):
        try:
            self.history_path.write_text(json.dumps(sessions, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ── Public read methods ───────────────────────────────────────────────────

    def get_history(self, user_id: str | None = None):
        with self._lock:
            sessions = self._load_history()
        if user_id:
            sessions = [s for s in sessions if s.get("user_id") == user_id]
        if not sessions:
            return []
        return sessions[-1].get("messages", [])

    def get_sessions(self, user_id: str | None = None):
        with self._lock:
            sessions = self._load_history()
        if user_id:
            sessions = [s for s in sessions if s.get("user_id") == user_id]
        formatted = []
        for s in sessions:
            messages = s.get("messages", [])
            title = s.get("title") or (messages[0].get("message")[:32] + "...") if messages else "(empty)"
            formatted.append({
                "session_id": s.get("session_id"),
                "created_at": s.get("created_at"),
                "title": title,
            })
        return formatted

    def get_session_messages(self, session_id: str):
        with self._lock:
            sessions = self._load_history()
        for s in sessions:
            if s.get("session_id") == session_id:
                return [
                    {"role": msg.get("role", "user"), "content": msg.get("message", "")}
                    for msg in s.get("messages", [])
                ]
        return []

    def is_session_pending(self, session_id: str) -> bool:
        msgs = self.get_session_messages(session_id)
        return any(m["content"] == _PENDING for m in msgs)

    # ── Write helpers ─────────────────────────────────────────────────────────

    def _append_history(self, role: str, message: str, session_id: str | None = None, user_id: str | None = None):
        with self._lock:
            sessions, session = self._ensure_session_unlocked(session_id, user_id=user_id)
            if role == "user" and not session.get("messages"):
                session["title"] = (message or "New Chat").strip()[:60]
            if user_id and not session.get("user_id"):
                session["user_id"] = user_id
            session.get("messages", []).append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "role": role,
                "message": message,
            })
            self._save_history(sessions)
            return session.get("session_id")

    def _update_pending(self, session_id: str, response: str):
        """Replace the __PENDING__ placeholder with the real AI response."""
        with self._lock:
            sessions = self._load_history()
            for s in sessions:
                if s.get("session_id") == session_id:
                    for msg in reversed(s.get("messages", [])):
                        if msg.get("message") == _PENDING:
                            msg["message"] = response
                            msg["timestamp"] = datetime.utcnow().isoformat() + "Z"
                            break
                    break
            self._save_history(sessions)

    def cleanup_stale_pending(self):
        """Convert any leftover PENDING messages (from crashed/restarted server)."""
        with self._lock:
            sessions = self._load_history()
            changed = False
            for s in sessions:
                for msg in s.get("messages", []):
                    if msg.get("message") == _PENDING:
                        msg["message"] = _INTERRUPTED
                        changed = True
            if changed:
                self._save_history(sessions)

    def _ensure_session_unlocked(self, session_id: str | None = None, user_id: str | None = None):
        """Like _ensure_session but assumes lock is already held."""
        sessions = self._load_history()
        if not sessions:
            sessions = [{
                "session_id": str(uuid.uuid4()),
                "created_at": datetime.utcnow().isoformat() + "Z",
                "title": "New Chat",
                "user_id": user_id,
                "messages": [],
            }]
        if session_id:
            for s in sessions:
                if s.get("session_id") == session_id:
                    return sessions, s
        # Fall back to last session for this user (or global last)
        user_sessions = [s for s in sessions if s.get("user_id") == user_id] if user_id else sessions
        return sessions, (user_sessions[-1] if user_sessions else sessions[-1])

    def delete_session(self, session_id: str):
        with self._lock:
            sessions = self._load_history()
            sessions = [s for s in sessions if s.get("session_id") != session_id]
            self._save_history(sessions)

    def clear_history(self):
        with self._lock:
            self.history_path.write_text("[]", encoding="utf-8")

    def create_new_session(self, title: str | None = None, user_id: str | None = None):
        with self._lock:
            sessions = self._load_history()
            session = {
                "session_id": str(uuid.uuid4()),
                "created_at": datetime.utcnow().isoformat() + "Z",
                "title": title or "New Chat",
                "user_id": user_id,
                "messages": [],
            }
            sessions.append(session)
            self._save_history(sessions)
            return session["session_id"]

    # ── Chat submission ───────────────────────────────────────────────────────

    def submit_async(self, message: str, session_id: str | None = None, user_id: str | None = None) -> str:
        """Store user message + PENDING marker, start AI call in background thread.
        Returns session_id immediately — never blocks."""
        if not self.rag_system.agent_graph:
            session_id = self._append_history("user", message.strip(), session_id=session_id, user_id=user_id)
            self._append_history("assistant", "⚠️ System not initialized!", session_id=session_id, user_id=user_id)
            return session_id

        session_id = self._append_history("user", message.strip(), session_id=session_id, user_id=user_id)
        self._append_history("assistant", _PENDING, session_id=session_id, user_id=user_id)
        self._executor.submit(self._invoke_and_update, message.strip(), session_id)
        return session_id

    def stop_session(self, session_id: str):
        """Immediately cancel a pending session (marks it stopped; background thread discards result)."""
        self._cancelled.add(session_id)
        self._update_pending(session_id, "⏹ Response stopped.")

    def _invoke_and_update(self, message: str, session_id: str):
        """Background worker: run the agent and replace __PENDING__ with the response."""
        try:
            result = self.rag_system.agent_graph.invoke(
                {"messages": [HumanMessage(content=message)]},
                self.rag_system.get_config(thread_id=session_id),
            )
            response = result["messages"][-1].content
        except Exception as e:
            response = f"❌ Error: {str(e)}"
        finally:
            try:
                self.rag_system.observability.flush()
            except Exception:
                pass
        if session_id in self._cancelled:
            self._cancelled.discard(session_id)
        else:
            self._update_pending(session_id, response)

    @staticmethod
    def _format_tool_step(tool_acc: dict) -> str | None:
        """Build a human-readable activity string from accumulated tool_call_chunks."""
        import json
        for tc_info in tool_acc.values():
            name = tc_info.get("name", "")
            try:
                args = json.loads(tc_info.get("args", "{}"))
            except Exception:
                args = {}
            if name == "search_child_chunks":
                query = args.get("query", "")
                return f'🔍 Searched & reranked: <em>"{query[:100]}"</em>' if query else "🔍 Search & rerank completed"
            if name == "retrieve_parent_chunks":
                return "📄 Retrieved document chunk"
            if name == "retrieve_parent_chunks_batch":
                raw = args.get("parent_ids") or []
                count = len(raw) if isinstance(raw, list) else 1
                return f"📄 Retrieved {count} document chunk{'s' if count != 1 else ''}"
        return None

    def stream_response(self, message: str, session_id: str | None = None, state_filter: str | None = None, user_id: str | None = None, user_name: str | None = None):
        """Stream response tokens. Yields (partial_text, session_id, activity_steps) tuples."""
        if not self.rag_system.agent_graph:
            session_id = self._append_history("user", message.strip(), session_id=session_id, user_id=user_id)
            self._append_history("assistant", "⚠️ System not initialized!", session_id=session_id, user_id=user_id)
            yield "⚠️ System not initialized!", session_id, [], False
            return

        session_id = self._append_history("user", message.strip(), session_id=session_id, user_id=user_id)
        activity_steps: list[str] = ["💬 Reading your question..."]
        yield "", session_id, activity_steps, True  # Show first step immediately before graph starts

        full_response = ""
        last_state = None
        active_filter = (state_filter or "").strip()
        active_filter = "" if active_filter.lower() in ("all states", "all", "") else active_filter
        graph_input = {"messages": [HumanMessage(content=message.strip())]}
        if active_filter:
            graph_input["state_filter"] = active_filter
        if user_name:
            graph_input["user_name"] = user_name

        _tool_acc: dict = {}   # accumulates tool_call_chunks by index
        _prev_node: str = ""
        _orchestrator_visits: int = 0
        _is_multi_question: bool = False   # True once we see >1 rewrittenQuestions
        _agg_output: str = ""              # tracks aggregate_answers streaming separately
        _is_narration: bool = True         # True until first tool completes → marks pre-answer text
        try:
            for namespace, mode, data in self.rag_system.agent_graph.stream(
                graph_input,
                self.rag_system.get_config(thread_id=session_id),
                stream_mode=["messages", "values"],
                subgraphs=True,
            ):
                if mode == "messages":
                    chunk, metadata = data
                    node = metadata.get("langgraph_node", "")

                    # Fire activity step once per node *entry* (when node changes)
                    if node and node != _prev_node:
                        if node == "summarize_history":
                            activity_steps = activity_steps + ["🗂 Reviewing conversation history..."]
                            yield "", session_id, activity_steps, True
                        elif node == "rewrite_query":
                            activity_steps = activity_steps + ["🧠 Analysing your question..."]
                            yield "", session_id, activity_steps, True
                        elif node == "orchestrator":
                            _orchestrator_visits += 1
                            if _orchestrator_visits == 1:
                                activity_steps = activity_steps + ["📋 Planning search strategy..."]
                            else:
                                activity_steps = activity_steps + ["🔄 Reviewing findings, refining search..."]
                            yield "", session_id, activity_steps, True
                        elif node == "compress_context":
                            activity_steps = activity_steps + ["🗜 Consolidating research context..."]
                            yield "", session_id, activity_steps, True
                        elif node == "aggregate_answers":
                            activity_steps = activity_steps + ["✍️ Writing response..."]
                            yield "", session_id, activity_steps, True
                        _prev_node = node

                    # Accumulate streaming tool-call argument fragments
                    if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                        for tc in chunk.tool_call_chunks:
                            idx = tc.get("index", 0)
                            if tc.get("name"):
                                _tool_acc[idx] = {"name": tc["name"], "args": ""}
                            if idx in _tool_acc and tc.get("args"):
                                _tool_acc[idx]["args"] += tc["args"]

                    # ToolMessage = tool finished → build activity step from accumulated call
                    if isinstance(chunk, ToolMessage):
                        step = self._format_tool_step(_tool_acc)
                        _tool_acc.clear()
                        if step:
                            activity_steps = activity_steps + [step]
                            yield "", session_id, activity_steps, True
                        # Reset accumulated response — any text before this tool result
                        # was orchestrator narration ("I'll search for..."), not the final answer
                        full_response = ""
                        _is_narration = False  # after first tool completes, next text = final answer

                    # Final answer streaming.
                    # For multi-question queries each orchestrator runs in parallel — capturing all
                    # of them concatenates/interleaves their outputs.  Instead, for multi-question
                    # we only capture the aggregate_answers synthesis; for single-question we capture
                    # the orchestrator's direct final answer (aggregate_answers is a pass-through).
                    if (isinstance(chunk, AIMessageChunk)
                            and chunk.content
                            and not chunk.tool_call_chunks):
                        # chunk.content may be a list of content parts (structured Claude output)
                        chunk_text = chunk.content
                        if isinstance(chunk_text, list):
                            chunk_text = "".join(
                                part.get("text", "") if isinstance(part, dict) else str(part)
                                for part in chunk_text
                            )
                        if node == "aggregate_answers":
                            # aggregate_answers streamed token (multi-question synthesis)
                            _agg_output += chunk_text
                            full_response = _agg_output
                            yield full_response, session_id, activity_steps, False
                        elif node in ("orchestrator", "fallback_response") and not _is_multi_question:
                            # single-question: orchestrator streams its final answer directly
                            full_response += chunk_text
                            yield full_response, session_id, activity_steps, _is_narration

                elif mode == "values":
                    if not namespace:  # root state only — used for fallback extraction
                        last_state = data
                        # Detect multi-question mode as soon as rewrite_query resolves
                        if not _is_multi_question:
                            _is_multi_question = len(data.get("rewrittenQuestions", [])) > 1

            # Fallback: if token streaming produced nothing, extract from final root state
            if not full_response and last_state:
                msgs = last_state.get("messages", [])
                for msg in reversed(msgs):
                    content = msg.content if hasattr(msg, "content") else None
                    if isinstance(content, list):  # convert structured content to plain text
                        content = " ".join(
                            part.get("text", "") if isinstance(part, dict) else str(part)
                            for part in content
                        ).strip()
                    if (content
                            and not getattr(msg, "tool_calls", None)
                            and not isinstance(msg, HumanMessage)
                            and not isinstance(msg, AIMessageChunk)):
                        full_response = content
                        yield full_response, session_id, activity_steps, False
                        break
            # Secondary fallback: reconstruct from agent_answers in last state
            if not full_response and last_state:
                answers = last_state.get("agent_answers", [])
                if answers:
                    sorted_answers = sorted(answers, key=lambda x: x.get("index", 0))
                    combined = "\n\n".join(
                        a.get("answer", "") for a in sorted_answers if a.get("answer")
                    )
                    if combined:
                        full_response = combined
                        yield full_response, session_id, activity_steps, False

        except Exception as e:
            full_response = f"❌ Error: {str(e)}"
            yield full_response, session_id, activity_steps, False
        finally:
            self._append_history(
                "assistant", full_response or "No response generated.", session_id=session_id, user_id=user_id
            )
            try:
                self.rag_system.observability.flush()
            except Exception:
                pass

    # ── Legacy synchronous chat (kept for compatibility) ──────────────────────

    def chat(self, message, history, session_id: str | None = None):
        if not self.rag_system.agent_graph:
            return "⚠️ System not initialized!", session_id
        session_id = self._append_history("user", message.strip(), session_id=session_id)
        try:
            result = self.rag_system.agent_graph.invoke(
                {"messages": [HumanMessage(content=message.strip())]},
                self.rag_system.get_config(thread_id=session_id),
            )
            response = result["messages"][-1].content
            self._append_history("assistant", response, session_id=session_id)
            return response, session_id
        except Exception as e:
            return f"❌ Error: {str(e)}", session_id
        finally:
            self.rag_system.observability.flush()

    def evaluate_response(self, question: str, answer: str) -> str:
        """Evaluate an AI answer using Claude Haiku as judge. Returns a markdown quality report."""
        try:
            import config
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import SystemMessage, HumanMessage

            judge_llm = ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                api_key=config.ANTHROPIC_API_KEY,
                temperature=0.1,
                max_tokens=600,
            )

            system_prompt = """You are an expert legal quality assessor evaluating an AI assistant's response to an Australian law question.

Score each dimension from 1–10 and give a brief explanation (1–2 sentences).

Output this exact markdown format with no extra text before or after:

## Answer Quality Assessment

**Relevance**: X/10
*[Did the answer directly address what was asked?]*

**Legal Accuracy**: X/10
*[Are the legal principles, rules, and case holdings stated correctly?]*

**Citation Plausibility**: X/10
*[Do the cited cases/legislation look plausible and relevant? Note: actual source documents cannot be verified.]*

**Completeness**: X/10
*[Did the answer cover all important aspects of the question?]*

---
**Overall**: X.X/10 — [one sentence verdict]"""

            response = judge_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"**QUESTION:**\n{question}\n\n**ANSWER:**\n{answer}"),
            ])
            return response.content
        except Exception as e:
            return f"⚠️ Evaluation failed: {str(e)}"

    def clear_session(self, session_id: str | None = None):
        self.rag_system.reset_thread(thread_id=session_id)
