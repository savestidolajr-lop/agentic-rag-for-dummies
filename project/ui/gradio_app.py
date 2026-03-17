import re
import gradio as gr
import config
from pathlib import Path
from core.chat_interface import ChatInterface
from core.document_manager import DocumentManager
from core.rag_system import RAGSystem

_OPTIONS_RE = re.compile(r'\[OPTIONS:\s*([^\]]+)\]', re.IGNORECASE)
_CITED_RE   = re.compile(r'\[CITED_DOCUMENTS\](.*?)\[/CITED_DOCUMENTS\]', re.DOTALL)

_THINKING_HTML = (
    "Thinking"
    "<span class='thinking-dot'>.</span>"
    "<span class='thinking-dot'>.</span>"
    "<span class='thinking-dot'>.</span>"
)

# ── Auto-highlight patterns for legal content ─────────────────────────────────
_CODE_SPLIT_RE = re.compile(r'(```[\s\S]*?```|`[^`\n]+`)')
_CASE_RE    = re.compile(
    r'(?<!\*)((?:[A-Z][A-Za-z&\',\.]*(?:\s+[A-Za-z&\',\.]+)*)\s+v\s+(?:[A-Z][A-Za-z&\',\.]*(?:\s+[A-Za-z&\',\.]+)*)\s*\[\d{4}\][^\n]*?)(?!\*)')
_ACT_RE     = re.compile(
    r'(?<!\*)((?:[A-Z][a-zA-Z]+(?:\s+[A-Za-z]+)*)\s+(?:Act|Regulation|Rules|Code|Ordinance)\s+\d{4})(?!\*)')
_SECTION_RE = re.compile(
    r'(?<!`)\b((?:ss?|cl|clause|reg(?:ulation)?|section|Part|Division|Schedule)\.?\s*\d+[A-Za-z]*(?:\([^)\n]{1,20}\))*)\b(?!`)',
    re.IGNORECASE)
_AMOUNT_RE  = re.compile(
    r'(?<!\*)(\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?)(?!\*)', re.IGNORECASE)
_DATE_RE    = re.compile(
    r'(?<!\*)(\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|'
    r'September|October|November|December)\s+\d{4}\b)(?!\*)', re.IGNORECASE)


def _auto_highlight(text: str) -> str:
    segments = _CODE_SPLIT_RE.split(text)
    out = []
    for i, seg in enumerate(segments):
        if i % 2 == 1:
            out.append(seg)
            continue
        seg = _CASE_RE.sub(r'**\1**', seg)
        seg = _ACT_RE.sub(r'**\1**', seg)
        seg = _AMOUNT_RE.sub(r'**\1**', seg)
        seg = _DATE_RE.sub(r'**\1**', seg)
        seg = _SECTION_RE.sub(r'`\1`', seg)
        out.append(seg)
    return ''.join(out)


def _parse_options(text: str):
    m = _OPTIONS_RE.search(text)
    if not m:
        return text, []
    opts = [o.strip() for o in m.group(1).split("|") if o.strip()][:4]
    return _OPTIONS_RE.sub("", text).strip(), opts


def _clean_message(text: str) -> str:
    text = _OPTIONS_RE.sub("", text)
    text = _CITED_RE.sub("", text)
    text = _auto_highlight(text)
    return text.strip()


def _get_cited_html(text: str) -> str:
    """Return an HTML block of download links from the CITED_DOCUMENTS tag."""
    m = _CITED_RE.search(text)
    if not m:
        return ""
    filenames = re.findall(r'"([^"]+)"', m.group(1))
    seen, links = set(), []
    for fname in filenames:
        if fname in seen:
            continue
        seen.add(fname)
        safe = fname.replace('"', "")
        links.append(
            f'<a href="/files/{safe}" class="cited-link" download="{safe}">📄 {safe}</a>'
        )
    if not links:
        return ""
    return (
        '<div class="cited-sources">'
        '<div class="cited-label">📎 Sources</div>'
        + "".join(links)
        + "</div>"
    )


def _build_display(raw_msgs: list) -> list:
    """Convert raw session messages to Gradio display format, handling __PENDING__."""
    result = []
    for m in raw_msgs:
        content = m.get("content", "")
        if content == "__PENDING__":
            content = _THINKING_HTML
        else:
            content = _clean_message(content)
        result.append({"role": m["role"], "content": content})
    return result


_SIDEBAR_JS = """
window.grSelectSession = function(sid) {
  var el = document.querySelector('#session-click-txt textarea');
  if (!el) return;
  el.value = sid;
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
};
window.grDeleteSession = function(sid) {
  var el = document.querySelector('#session-del-txt textarea');
  if (!el) return;
  el.value = sid + '::' + Date.now();
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
};
"""

_SIDEBAR_HEAD = f"<script>{_SIDEBAR_JS}</script>"


def create_gradio_ui():
    rag_system = RAGSystem()
    init_error = None
    try:
        rag_system.initialize()
    except Exception as e:
        init_error = str(e)
        print(f"⚠️ RAGSystem initialization failed: {init_error}")

    doc_manager = DocumentManager(rag_system)
    chat_interface = ChatInterface(rag_system)

    DEFAULT_STATE_CHOICES = ["NSW", "VIC", "QLD", "SA", "NT", "WA", "TAS", "ACT"]

    def format_file_list():
        files = doc_manager.get_markdown_files()
        if not files:
            return "No documents in the knowledge base."
        return "\n".join(files)

    def get_state_choices():
        all_states = ["All States"] + DEFAULT_STATE_CHOICES
        all_states += [s for s in doc_manager.get_states() if s not in all_states]
        return all_states

    def format_health_status():
        health = rag_system.get_health(refresh=True)
        parts = ["Qdrant ✓" if health.get("qdrant") else "Qdrant ✗"]
        if config.LLM_PROVIDER == "openai":
            if not health.get("api_key_present"):
                parts.append("⚠ OPENAI_API_KEY missing")
            elif health.get("llm"):
                parts.append(f"OpenAI ✓ ({config.OPENAI_MODEL})")
            else:
                parts.append(f"OpenAI ✗ {health.get('llm_error')}")
        else:
            parts.append(f"{config.LLM_PROVIDER.title()} ✓")
        if init_error:
            parts.append(f"⚠ {init_error}")
        return "  ·  ".join(parts)

    def upload_handler(files, state, progress=gr.Progress()):
        if not files:
            return None, format_file_list(), gr.update(choices=get_state_choices())
        added, skipped = doc_manager.add_documents(
            files,
            state=state if state and state.lower() not in ["all", "all states"] else None,
            progress_callback=lambda p, desc: progress(p, desc=desc),
        )
        gr.Info(f"Added: {added} | Skipped: {skipped}")
        return None, format_file_list(), gr.update(choices=get_state_choices())

    def clear_handler():
        doc_manager.clear_all()
        gr.Info("Removed all documents")
        return format_file_list()

    def render_history():
        history = chat_interface.get_history()
        if not history:
            return "(no history yet)"
        return "\n\n".join(
            f"[{item.get('timestamp')}] {item.get('role')}: {item.get('message')}"
            for item in history
        )

    def clear_history_handler():
        chat_interface.clear_history()
        return "(no history yet)"

    # ── Session helpers ───────────────────────────────────────────────────────

    def _fmt(session):
        title = session.get("title", "New Chat")
        return title[:36] + "…" if len(title) > 36 else title

    def _render_sessions_html(sessions, active_id=None):
        if not sessions:
            return '<div class="session-empty">No recent chats</div>'
        parts = []
        for s in reversed(sessions):
            sid = s.get("session_id", "")
            title = _fmt(s)
            cls = "session-item session-active" if sid == active_id else "session-item"
            parts.append(
                f'<div class="{cls}" onclick="grSelectSession(\'{sid}\')">'
                f'<span class="session-item-title">{title}</span>'
                f'<button class="session-del-btn" onclick="event.stopPropagation();grDeleteSession(\'{sid}\')" title="Delete">✕</button>'
                f'</div>'
            )
        return "".join(parts)

    def _session_display(session_id):
        """Return (display_messages, has_pending) for a session."""
        msgs = chat_interface.get_session_messages(session_id) if session_id else []
        has_pending = any(m["content"] == "__PENDING__" for m in msgs)
        return _build_display(msgs), has_pending

    def _render_sessions(sessions, active_id=None):
        return gr.update(value=_render_sessions_html(sessions, active_id))

    def _refresh_sessions():
        sessions = chat_interface.get_sessions()
        active_id = sessions[-1].get("session_id") if sessions else None
        html_upd = _render_sessions(sessions, active_id)
        display, has_pending = _session_display(active_id)
        return html_upd, display, active_id, has_pending

    def _new_session():
        session_id = chat_interface.create_new_session()
        sessions = chat_interface.get_sessions()
        return _render_sessions(sessions, session_id), session_id, []

    # ── Build UI ──────────────────────────────────────────────────────────────

    with gr.Blocks(title="Case Agent") as demo:

        # Tracks whether the current session is awaiting an AI response
        was_pending = gr.State(False)

        with gr.Row(elem_id="app-root"):

            # ── Sidebar ───────────────────────────────────────────────────
            with gr.Column(scale=1, min_width=240, elem_id="sidebar"):

                gr.HTML('<div class="sidebar-header">Case Agent</div>')

                new_session_btn = gr.Button("＋  New chat", elem_id="new-chat-btn")

                gr.HTML('<div class="sidebar-label">Recent chats</div>')

                session_list_html = gr.HTML("", elem_id="session-list")
                active_session_id = gr.State(None)
                # These stay in DOM (visible=True) but are hidden via CSS:
                session_click_txt = gr.Textbox(value="", label="", elem_id="session-click-txt")
                session_del_txt   = gr.Textbox(value="", label="", elem_id="session-del-txt")

                gr.HTML('<div class="sidebar-divider"></div>')

                model_dropdown = gr.Dropdown(
                    choices=list(config.AVAILABLE_MODELS.keys()),
                    value="Claude Sonnet 4.6", label="Model",
                    elem_id="model-picker", interactive=True,
                )

                gr.HTML('<div class="sidebar-divider"></div>')

                admin_btn        = gr.Button("⚙  Admin Panel", elem_id="admin-btn")
                history_nav_btn  = gr.Button("🕐  History",    elem_id="history-btn")

                health_md = gr.Markdown(format_health_status(), elem_id="health-md")

            # ── Main area ─────────────────────────────────────────────────
            with gr.Column(scale=4, elem_id="main-area"):

                with gr.Row(elem_id="main-topbar"):
                    toggle_sidebar_btn = gr.Button("☰", elem_id="toggle-sidebar-btn", scale=0, min_width=36)
                    state_dropdown_chat = gr.Dropdown(
                        choices=get_state_choices(), value="All States",
                        allow_custom_value=True, label="State filter",
                        elem_id="state-filter", scale=0,
                        container=False,
                    )

                # ── Chat view ─────────────────────────────────────────
                with gr.Column(visible=True) as chat_view:

                    chatbot = gr.Chatbot(
                        height=640, show_label=False,
                        elem_id="chatbot",
                        placeholder="Ask me anything about your documents.",
                    )

                    cited_files = gr.HTML("", visible=False, elem_id="cited-files")

                    with gr.Row(visible=False, elem_id="sugg-row") as sugg_row:
                        sugg_btns = [
                            gr.Button("", visible=False, size="sm", elem_classes=["sugg-btn"])
                            for _ in range(4)
                        ]
                    sugg_texts = [gr.State("") for _ in range(4)]

                    with gr.Row(elem_id="input-row"):
                        user_input = gr.Textbox(
                            placeholder="Ask anything…", show_label=False,
                            scale=10, elem_id="user-input", lines=2, max_lines=12,
                        )
                        send_btn = gr.Button("⬆", variant="primary", scale=0, elem_id="send-btn")
                        stop_btn = gr.Button("⏹", variant="stop",    scale=0, elem_id="stop-btn", visible=False)

                    with gr.Row():
                        clear_chat_btn = gr.Button("Clear chat", size="sm")

                # ── Admin Panel ────────────────────────────────────────
                with gr.Column(visible=False) as docs_view:

                    gr.HTML('<div class="view-title">Admin Panel — Documents</div>')
                    gr.Markdown("Upload PDF or Markdown files. Duplicates are skipped automatically.")

                    state_dropdown = gr.Dropdown(
                        label="Namespace / State (optional)", choices=get_state_choices(),
                        value="All States", allow_custom_value=True, interactive=True,
                    )
                    files_input = gr.File(file_count="multiple", type="filepath", height=160, show_label=False)
                    add_btn = gr.Button("Add Documents", variant="primary")

                    gr.Markdown("#### Indexed Documents")
                    file_list = gr.Textbox(
                        value=format_file_list(), interactive=False,
                        lines=7, max_lines=12, show_label=False,
                    )
                    with gr.Row():
                        refresh_docs_btn = gr.Button("Refresh")
                        clear_docs_btn   = gr.Button("Clear All", variant="stop")

                # ── History view ───────────────────────────────────────
                with gr.Column(visible=False) as history_view:

                    gr.HTML('<div class="view-title">Chat History</div>')
                    history_box = gr.Textbox(
                        value=render_history(), interactive=False,
                        lines=25, max_lines=40, show_label=False,
                    )
                    with gr.Row():
                        refresh_history_btn = gr.Button("Refresh")
                        clear_history_btn   = gr.Button("Clear History", variant="stop")

        # ── Timer — polls active session every 2 s for background responses ──
        # Starts inactive; activated only when a message is in-flight
        timer = gr.Timer(value=2.0, active=False)

        # ── Event wiring ─────────────────────────────────────────────────────

        views = [chat_view, docs_view, history_view]

        # chat_outputs: chatbot, input, session_list_html, active_session_id, sugg_row,
        #               btns×4, texts×4, files, was_pending, timer, send_btn, stop_btn
        # Total: 1+1+1+1+1+4+4+1+1+1+1+1 = 17
        chat_outputs = (
            [chatbot, user_input, session_list_html, active_session_id, sugg_row]
            + sugg_btns + sugg_texts
            + [cited_files, was_pending, timer, send_btn, stop_btn]
        )

        def _sugg_updates(options):
            if options:
                row_upd = gr.update(visible=True)
                btn_upds, text_upds = [], []
                for i in range(4):
                    if i < len(options):
                        btn_upds.append(gr.update(visible=True, value=options[i]))
                        text_upds.append(options[i])
                    else:
                        btn_upds.append(gr.update(visible=False, value=""))
                        text_upds.append("")
            else:
                row_upd = gr.update(visible=False)
                btn_upds = [gr.update(visible=False, value="") for _ in range(4)]
                text_upds = [""] * 4
            return row_upd, btn_upds, text_upds

        _hidden_sugg = (
            gr.update(visible=False),
            [gr.update(visible=False, value="") for _ in range(4)],
            [""] * 4,
        )

        def show_chat():
            return gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
        def show_docs():
            return gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)
        def show_history():
            return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)

        def on_model_change(model_name):
            provider, model_id = config.AVAILABLE_MODELS[model_name]
            try:
                rag_system.switch_model(provider, model_id)
                return f"{model_name} ✓"
            except Exception as e:
                return f"⚠ {e}"

        model_dropdown.change(on_model_change, model_dropdown, health_md)

        toggle_sidebar_btn.click(None, js="() => { document.getElementById('sidebar').classList.toggle('sidebar-collapsed'); }")

        # ── Chat handler — streams tokens directly to UI ──────────────────────
        def chat_handler_ui(message, chat_history, session_id, selected_state):
            row_upd, btn_upds, text_upds = _hidden_sugg
            no_files = gr.update(visible=False, value="")

            if not message or not message.strip():
                yield chat_history, "", gr.update(), session_id, row_upd, *btn_upds, *text_upds, no_files, False, gr.update(), gr.update(), gr.update()
                return

            # Apply state filter
            if selected_state and selected_state.lower() not in ["all", "all states"]:
                rag_system.set_state_filter(selected_state)
            else:
                rag_system.set_state_filter(None)

            streamer = chat_interface.stream_response(message, session_id=session_id)
            _, new_session_id = next(streamer)  # saves user message, returns session_id immediately

            sessions = chat_interface.get_sessions()
            html = _render_sessions_html(sessions, active_id=new_session_id)
            base_display = list(chat_history or []) + [{"role": "user", "content": message.strip()}]

            # Show thinking indicator while agent is working
            yield (base_display + [{"role": "assistant", "content": _THINKING_HTML}],
                   "", gr.update(value=html), new_session_id,
                   row_upd, *btn_upds, *text_upds, no_files, False,
                   gr.update(active=False), gr.update(visible=False), gr.update(visible=True))

            # Stream tokens as they arrive from aggregate_answers
            partial_response = ""
            for partial_response, _ in streamer:
                if partial_response:
                    display = base_display + [{"role": "assistant", "content": _clean_message(partial_response)}]
                    yield (display, "", gr.update(), new_session_id,
                           row_upd, *btn_upds, *text_upds, no_files, False,
                           gr.update(active=False), gr.update(visible=False), gr.update(visible=True))

            # Final yield — restore send button, show suggestions and citations
            _, options = _parse_options(partial_response)
            row_upd2, btn_upds2, text_upds2 = _sugg_updates(options)
            cited_html = _get_cited_html(partial_response)
            files_upd = gr.update(visible=bool(cited_html), value=cited_html)
            sessions = chat_interface.get_sessions()
            html = _render_sessions_html(sessions, active_id=new_session_id)
            final_display = base_display + [{"role": "assistant", "content": _clean_message(partial_response or "No response generated.")}]

            yield (final_display, "", gr.update(value=html), new_session_id,
                   row_upd2, *btn_upds2, *text_upds2, files_upd, False,
                   gr.update(active=False), _send_show, _stop_hide)

        send_btn.click(chat_handler_ui, [user_input, chatbot, active_session_id, state_dropdown_chat], chat_outputs)
        user_input.submit(chat_handler_ui, [user_input, chatbot, active_session_id, state_dropdown_chat], chat_outputs)

        # Suggestion buttons
        def send_suggestion(txt, chat_history, session_id, selected_state):
            yield from chat_handler_ui(txt, chat_history, session_id, selected_state)

        for btn, txt_state in zip(sugg_btns, sugg_texts):
            btn.click(send_suggestion, [txt_state, chatbot, active_session_id, state_dropdown_chat], chat_outputs)

        # ── Timer polling — updates chatbot when background response arrives ──
        # timer_outputs: chatbot, was_pending, session_list_html, active_session_id,
        #                sugg_row, btns×4, texts×4, files, timer, send_btn, stop_btn
        # Total: 1+1+1+1+1+4+4+1+1+1+1 = 17
        timer_outputs = (
            [chatbot, was_pending, session_list_html, active_session_id, sugg_row]
            + sugg_btns + sugg_texts
            + [cited_files, timer, send_btn, stop_btn]
        )

        _send_show = gr.update(visible=True)
        _stop_show = gr.update(visible=True)
        _send_hide = gr.update(visible=False)
        _stop_hide = gr.update(visible=False)

        def poll_session(active_id, is_pending):
            _noop = gr.update()
            no_change = [_noop] * (len(timer_outputs) - 2)

            if not active_id or not is_pending:
                return _noop, False, *no_change[:-3], gr.update(active=False), _send_show, _stop_hide

            msgs = chat_interface.get_session_messages(active_id)
            still_pending = any(m["content"] == "__PENDING__" for m in msgs)

            if still_pending:
                display = _build_display(msgs)
                return gr.update(value=display), True, *no_change[:-3], gr.update(active=True), _send_hide, _stop_show

            # Response arrived — show it, deactivate timer, restore send button
            display = _build_display(msgs)
            last_resp = next((m["content"] for m in reversed(msgs) if m["role"] == "assistant"), "")
            _, options = _parse_options(last_resp)
            row_upd, btn_upds, text_upds = _sugg_updates(options)
            cited_html = _get_cited_html(last_resp)
            files_upd = gr.update(visible=bool(cited_html), value=cited_html)
            sessions = chat_interface.get_sessions()
            html = _render_sessions_html(sessions, active_id)
            return (gr.update(value=display), False,
                    gr.update(value=html), active_id,
                    row_upd, *btn_upds, *text_upds, files_upd, gr.update(active=False),
                    _send_show, _stop_hide)

        timer.tick(poll_session, [active_session_id, was_pending], timer_outputs, show_progress=False)

        # ── Session selection ─────────────────────────────────────────────────
        def on_session_select(sid):
            sid = (sid or "").strip()
            sessions = chat_interface.get_sessions()
            display, has_pending = _session_display(sid)
            html = _render_sessions_html(sessions, active_id=sid)
            row_upd, btn_upds, text_upds = _hidden_sugg
            return (display, gr.update(value=html), sid,
                    gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
                    row_upd, *btn_upds, *text_upds,
                    gr.update(visible=False, value=""), has_pending,
                    gr.update(visible=not has_pending), gr.update(visible=has_pending))

        session_click_txt.change(
            on_session_select, session_click_txt,
            [chatbot, session_list_html, active_session_id] + views + [sugg_row] + sugg_btns + sugg_texts + [cited_files, was_pending, send_btn, stop_btn],
            show_progress=False,
        )

        def new_session_handler():
            html_upd, session_id, history = _new_session()
            row_upd, btn_upds, text_upds = _hidden_sugg
            return ([], html_upd, session_id,
                    gr.update(visible=True), gr.update(visible=False), gr.update(visible=False),
                    row_upd, *btn_upds, *text_upds,
                    gr.update(visible=False, value=""), False,
                    _send_show, _stop_hide)

        new_session_btn.click(
            new_session_handler, None,
            [chatbot, session_list_html, active_session_id] + views + [sugg_row] + sugg_btns + sugg_texts + [cited_files, was_pending, send_btn, stop_btn],
        )

        def _on_del_trigger(value):
            session_id = value.split("::")[0] if "::" in value else value.strip()
            if session_id:
                chat_interface.delete_session(session_id)
            sessions = chat_interface.get_sessions()
            active_id = sessions[-1].get("session_id") if sessions else None
            html = _render_sessions_html(sessions, active_id)
            display, _ = _session_display(active_id)
            return gr.update(value=html), display, active_id

        session_del_txt.change(_on_del_trigger, session_del_txt, [session_list_html, chatbot, active_session_id], show_progress=False)

        def stop_handler(active_id):
            if active_id:
                chat_interface.stop_session(active_id)
            display, _ = _session_display(active_id)
            return display, False, gr.update(active=False), _send_show, _stop_hide

        stop_btn.click(stop_handler, [active_session_id], [chatbot, was_pending, timer, send_btn, stop_btn])

        def clear_chat_handler(active_id):
            chat_interface.clear_session(session_id=active_id)
            row_upd, btn_upds, _ = _hidden_sugg
            return [], row_upd, *btn_upds, gr.update(visible=False, value=""), False, _send_show, _stop_hide

        clear_chat_btn.click(
            clear_chat_handler, [active_session_id],
            [chatbot, sugg_row] + sugg_btns + [cited_files, was_pending, send_btn, stop_btn],
        )

        # Nav
        admin_btn.click(show_docs, None, views)
        history_nav_btn.click(show_history, None, views)

        # Documents
        add_btn.click(upload_handler, [files_input, state_dropdown],
                      [files_input, file_list, state_dropdown], show_progress="corner")
        refresh_docs_btn.click(
            lambda: (format_file_list(), gr.update(choices=get_state_choices())),
            None, [file_list, state_dropdown])
        clear_docs_btn.click(
            lambda: (clear_handler(), gr.update(choices=get_state_choices())),
            None, [file_list, state_dropdown])

        # History
        refresh_history_btn.click(render_history, None, history_box)
        clear_history_btn.click(clear_history_handler, None, history_box)

        # On load — restore pending state if any session was mid-response
        demo.load(_refresh_sessions, None, [session_list_html, chatbot, active_session_id, was_pending])

    def _health_endpoint():
        return rag_system.get_health(refresh=True)

    demo.app.get("/health")(_health_endpoint)

    from fastapi import HTTPException
    from fastapi.responses import FileResponse as _FileResponse

    @demo.app.get("/files/{filename}")
    def serve_document(filename: str):
        # Block path traversal
        if "/" in filename or "\\" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        # PDF first (original uploads)
        docs_dir = Path(config.DOCUMENTS_DIR)
        for p in docs_dir.rglob(filename):
            return _FileResponse(str(p), filename=filename)
        # Fallback: markdown version
        md_dir = Path(config.MARKDOWN_DIR)
        stem = Path(filename).stem
        for p in md_dir.rglob(stem + ".md"):
            return _FileResponse(str(p), media_type="text/plain", filename=stem + ".md")
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    return demo
