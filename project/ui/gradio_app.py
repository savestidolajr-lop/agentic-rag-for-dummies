import re
import gradio as gr
import config
from pathlib import Path
from core.chat_interface import ChatInterface
from core.document_manager import DocumentManager
from core.rag_system import RAGSystem
from core import admin_config
from rag_agent.prompts import (
    get_orchestrator_prompt,
    get_aggregation_prompt,
    get_fallback_response_prompt,
)

_OPTIONS_RE = re.compile(r'\[OPTIONS:\s*([^\]]+)\]', re.IGNORECASE)
_CITED_RE   = re.compile(r'\[CITED_DOCUMENTS\](.*?)\[/CITED_DOCUMENTS\]', re.DOTALL)

_THINKING_HTML = (
    "<span class='thinking-container'>"
    "<span class='thinking-word-display'>Thinking</span>"
    "<span class='thinking-dot'>.</span>"
    "<span class='thinking-dot'>.</span>"
    "<span class='thinking-dot'>.</span>"
    "</span>"
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


def _fix_list_newlines(text: str) -> str:
    """Ensure numbered/lettered/dash list items each start on their own line."""
    # Numbered lists: "1. " "2. " etc.
    text = re.sub(r'(?<!\n)[ \t]+(\d+[.)]\s)', r'\n\1', text)
    # Lettered lists: "a. " "b) " etc.
    text = re.sub(r'(?<!\n)[ \t]+([a-zA-Z][.)]\s)', r'\n\1', text)
    # Dash / bullet items
    text = re.sub(r'(?<!\n)[ \t]+([-•]\s)', r'\n\1', text)
    return text


def _clean_message(text: str) -> str:
    text = _OPTIONS_RE.sub("", text)
    text = _CITED_RE.sub("", text)
    text = _fix_list_newlines(text)
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

_enter_js = """
() => {
    /* ── Enter to send ── */
    function attachEnterHandler() {
        const ta = document.querySelector('#user-input textarea');
        if (!ta || ta._enterBound) return;
        ta._enterBound = true;
        ta.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const btn = document.querySelector('#send-btn button');
                if (btn && !btn.disabled) btn.click();
            }
        });
    }

    /* ── Random thinking word cycler (single global interval) ── */
    const _words = [
        'Thinking','Searching','Analysing','Reading','Processing',
        'Reasoning','Reviewing','Stewing','Herding','Deciphering',
        'Wandering','Channeling','Considering','Ruminating','Sussing'
    ];
    let _lastWord = '';
    function _rand() {
        let w; do { w = _words[Math.floor(Math.random() * _words.length)]; } while (w === _lastWord);
        return _lastWord = w;
    }

    setInterval(() => {
        const el = document.querySelector('.thinking-word-display');
        if (!el) return;
        el.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        el.style.opacity = '0';
        el.style.transform = 'translateY(-5px)';
        setTimeout(() => {
            const el2 = document.querySelector('.thinking-word-display');
            if (!el2) return;
            el2.textContent = _rand();
            el2.style.transition = 'none';
            el2.style.transform = 'translateY(5px)';
            el2.style.opacity = '0';
            requestAnimationFrame(() => requestAnimationFrame(() => {
                el2.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                el2.style.opacity = '1';
                el2.style.transform = 'translateY(0)';
            }));
        }, 320);
    }, 4000);

    /* ── Auto-scroll activity steps to bottom on each update ── */
    function scrollActivityToBottom() {
        requestAnimationFrame(() => {
            document.querySelectorAll('.activity-steps').forEach(el => {
                el.scrollTop = el.scrollHeight;
            });
        });
    }

    /* ── Attach enter handler + activity scroller after any re-render ── */
    attachEnterHandler();
    const _obs = new MutationObserver(() => {
        attachEnterHandler();
        scrollActivityToBottom();
    });
    _obs.observe(document.body, { childList: true, subtree: true });
}
"""


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

    PAGE_SIZE = 15

    def render_file_table(state_filter="All States", search_query="", page=0):
        files = doc_manager.get_files_structured()
        if state_filter and state_filter.lower() not in ("all states", "all"):
            files = [f for f in files if f["state"] == state_filter]
        if search_query and search_query.strip():
            q = search_query.strip().lower()
            files = [f for f in files if q in f["filename"].lower() or q in f["state"].lower()]

        if not files:
            return '<div style="padding:16px;color:#888;text-align:center;">No documents found.</div>'

        total = len(files)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        page_files = files[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

        state_counts = {}
        for f in files:
            state_counts[f["state"]] = state_counts.get(f["state"], 0) + 1

        rows = ""
        for f in page_files:
            safe = f["filename"].replace('"', "")
            rows += f"""
            <tr>
                <td><span class="state-badge">{f["state"]}</span></td>
                <td class="filename-cell">📄 {f["filename"]}</td>
                <td><a href="/files/{safe}" download="{safe}" class="dl-btn">↓ Download</a></td>
            </tr>"""

        stats = " · ".join(f'<b>{s}</b>: {c}' for s, c in sorted(state_counts.items()))

        return f"""
        <div class="file-table-wrap">
            <div class="file-stats">{stats}</div>
            <table class="file-table">
                <thead><tr><th>State</th><th>File</th><th></th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        <style>
            .file-table-wrap {{ border:1px solid #2d2d2d; border-radius:8px; overflow:hidden; }}
            .file-stats {{ padding:8px 14px; font-size:12px; color:#888; background:#161616; border-bottom:1px solid #2d2d2d; }}
            .file-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
            .file-table thead tr {{ background:#1a1a1a; }}
            .file-table th {{ padding:8px 12px; text-align:left; color:#aaa; font-weight:500; border-bottom:1px solid #2d2d2d; }}
            .file-table tbody tr {{ border-bottom:1px solid #1e1e1e; transition:background .15s; }}
            .file-table tbody tr:hover {{ background:#1c1c1c; }}
            .file-table td {{ padding:7px 12px; color:#ddd; vertical-align:middle; }}
            .filename-cell {{ font-family:monospace; font-size:12px; }}
            .state-badge {{ background:#232323; border:1px solid #333; border-radius:4px; padding:2px 7px; font-size:11px; color:#10a37f; white-space:nowrap; }}
            .dl-btn {{ color:#10a37f; text-decoration:none; font-size:12px; padding:3px 8px; border:1px solid #10a37f33; border-radius:4px; white-space:nowrap; }}
            .dl-btn:hover {{ background:#10a37f22; }}
            .pagination {{ display:flex; align-items:center; justify-content:center; gap:12px; padding:10px; background:#161616; border-top:1px solid #2d2d2d; }}
            .pg-btn {{ background:#232323; border:1px solid #333; color:#ccc; padding:4px 12px; border-radius:4px; cursor:pointer; font-size:12px; }}
            .pg-btn:hover:not([disabled]) {{ background:#2d2d2d; }}
            .pg-info {{ font-size:12px; color:#888; }}
        </style>"""

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
            return None, render_file_table(), gr.update(choices=get_state_choices())
        added, skipped = doc_manager.add_documents(
            files,
            state=state if state and state.lower() not in ["all", "all states"] else None,
            progress_callback=lambda p, desc: progress(p, desc=desc),
        )
        gr.Info(f"Added: {added} | Skipped: {skipped}")
        return None, render_file_table(), gr.update(choices=get_state_choices())

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

                toggle_sidebar_btn = gr.Button("☰", elem_id="toggle-sidebar-btn")

                with gr.Column(elem_id="sidebar-body"):
                    gr.HTML('<div class="sidebar-header">Case Agent</div>')

                    new_session_btn = gr.Button("＋  New chat", elem_id="new-chat-btn")

                    gr.HTML('<div class="sidebar-label">Recent chats</div>')

                    session_list_html = gr.HTML("", elem_id="session-list")
                    active_session_id = gr.State(None)
                    # These stay in DOM (visible=True) but are hidden via CSS:
                    session_click_txt = gr.Textbox(value="", label="", elem_id="session-click-txt")
                    session_del_txt   = gr.Textbox(value="", label="", elem_id="session-del-txt")

                    gr.HTML('<div class="sidebar-divider"></div>')

                    admin_btn        = gr.Button("⚙  Admin Panel", elem_id="admin-btn")
                    history_nav_btn  = gr.Button("🕐  History",    elem_id="history-btn")

                    health_md = gr.Markdown(format_health_status(), elem_id="health-md")

            # ── Main area ─────────────────────────────────────────────────
            with gr.Column(scale=4, elem_id="main-area"):

                with gr.Row(elem_id="main-topbar"):
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

                    agent_activity = gr.HTML("", visible=False, elem_id="agent-activity")
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

                    with gr.Row(elem_id="input-meta-row"):
                        model_dropdown = gr.Dropdown(
                            choices=list(config.AVAILABLE_MODELS.keys()),
                            value="Claude Haiku 4.5",
                            container=False, show_label=False,
                            elem_id="model-picker-inline", interactive=True,
                            scale=0, min_width=180,
                        )

                # ── Admin Panel ────────────────────────────────────────
                with gr.Column(visible=False) as docs_view:

                    gr.HTML('<div class="view-title">Admin Panel</div>')

                    with gr.Tabs(elem_id="admin-tabs"):

                        # ── Tab 1: Documents ───────────────────────────
                        with gr.TabItem("📄 Documents"):

                            with gr.Row():
                                state_dropdown = gr.Dropdown(
                                    label="Upload to State", choices=get_state_choices(),
                                    value="All States", allow_custom_value=True, interactive=True,
                                )
                            files_input = gr.File(file_count="multiple", type="filepath", height=140, show_label=False)
                            add_btn = gr.Button("Add Documents", variant="primary")

                            gr.HTML('<div style="margin-top:20px;margin-bottom:8px;font-weight:600;color:#ccc;">Indexed Documents</div>')

                            with gr.Row():
                                file_search = gr.Textbox(
                                    placeholder="Search by filename...",
                                    show_label=False, scale=3, elem_id="file-search"
                                )
                                file_state_filter = gr.Dropdown(
                                    choices=["All States"] + DEFAULT_STATE_CHOICES,
                                    value="All States", show_label=False, scale=1,
                                    elem_id="file-state-filter"
                                )
                                refresh_docs_btn = gr.Button("↻ Refresh", scale=0, min_width=90)

                            file_table = gr.HTML(value=render_file_table())
                            file_page = gr.State(0)
                            with gr.Row(elem_id="pagination-row"):
                                prev_btn = gr.Button("← Prev", size="sm", scale=0, min_width=80)
                                page_info = gr.Markdown("Page 1", elem_id="page-info")
                                next_btn = gr.Button("Next →", size="sm", scale=0, min_width=80)

                            # ── Danger zone ───────────────────────────
                            with gr.Accordion("Danger Zone", open=False, elem_id="danger-zone-accordion"):
                                reindex_btn    = gr.Button("🔄 Re-index All Documents", elem_id="reindex-btn")
                                reindex_status = gr.Markdown("", elem_id="reindex-status")
                                clear_docs_btn = gr.Button("🗑 Clear All Documents", elem_id="clear-all-btn")

                            with gr.Column(visible=False, elem_id="confirm-delete-panel") as confirm_panel:
                                gr.HTML("""
                                <div style="background:#2a0a0a;border:1px solid #8b2020;border-radius:10px;padding:16px 18px;margin-top:12px;">
                                    <div style="color:#ff6b6b;font-size:15px;font-weight:700;margin-bottom:6px;">⚠️ Danger Zone</div>
                                    <div style="color:#ccc;font-size:13px;line-height:1.5;">
                                        This will permanently delete <strong style="color:#fff;">all uploaded documents</strong>,
                                        all indexed vectors in the database, and all stored chunks.<br>
                                        <span style="color:#ff9999;">This action cannot be undone.</span>
                                    </div>
                                </div>
                                """)
                                confirm_input = gr.Textbox(
                                    placeholder='Type  DELETE  to confirm',
                                    show_label=False,
                                    elem_id="confirm-delete-input",
                                    max_lines=1,
                                )
                                with gr.Row():
                                    confirm_delete_btn = gr.Button("Confirm Delete", variant="stop", scale=1, elem_id="confirm-delete-confirm-btn")
                                    cancel_delete_btn  = gr.Button("Cancel", scale=1, elem_id="confirm-delete-cancel-btn")

                        # ── Tab 2: AI Settings ─────────────────────────
                        with gr.TabItem("🤖 AI Settings"):

                            gr.HTML('<div style="color:#888;font-size:12px;margin-bottom:16px;">Changes apply immediately to the next query. Leave a prompt field empty to use the system default.</div>')

                            with gr.Row():
                                ai_temperature = gr.Slider(
                                    minimum=0.0, maximum=1.0, step=0.05,
                                    value=admin_config.get("temperature", config.LLM_TEMPERATURE),
                                    label="Temperature",
                                    info="0 = precise / deterministic   ·   1 = creative / varied",
                                )
                                ai_max_tools = gr.Slider(
                                    minimum=1, maximum=15, step=1,
                                    value=admin_config.get("max_tool_calls", config.MAX_TOOL_CALLS),
                                    label="Max Tool Calls",
                                    info="Max search attempts per query before fallback",
                                )

                            ai_orchestrator_prompt = gr.Textbox(
                                label="Orchestrator Prompt  (core AI personality & rules)",
                                value=get_orchestrator_prompt(),
                                lines=18, max_lines=40,
                                placeholder="Leave empty to use system default...",
                            )
                            ai_aggregation_prompt = gr.Textbox(
                                label="Aggregation Prompt  (how multiple answers are combined)",
                                value=get_aggregation_prompt(),
                                lines=12, max_lines=30,
                                placeholder="Leave empty to use system default...",
                            )
                            ai_fallback_prompt = gr.Textbox(
                                label="Fallback Response Prompt  (when max searches are reached)",
                                value=get_fallback_response_prompt(),
                                lines=10, max_lines=20,
                                placeholder="Leave empty to use system default...",
                            )

                            ai_settings_status = gr.Markdown("", elem_id="ai-settings-status")

                            with gr.Row():
                                ai_save_btn    = gr.Button("💾 Save Settings", variant="primary", scale=2)
                                ai_reset_btn   = gr.Button("↺ Reset to Defaults", scale=1)

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

                gr.HTML('<div id="input-disclaimer">AI can make mistakes. Please double-check responses.</div>')

        # ── Timer — polls active session every 2 s for background responses ──
        # Starts inactive; activated only when a message is in-flight
        timer = gr.Timer(value=2.0, active=False)

        # ── Event wiring ─────────────────────────────────────────────────────

        views = [chat_view, docs_view, history_view]

        _ANIMATED_DOTS = (
            "<span class='thinking-dot'>.</span>"
            "<span class='thinking-dot'>.</span>"
            "<span class='thinking-dot'>.</span>"
        )

        def _render_activity(steps: list, done: bool = False) -> tuple:
            if not steps or done:
                return gr.update(visible=False, value="")
            items = []
            for i, step in enumerate(steps):
                is_last = (i == len(steps) - 1)
                # Strip trailing static "..." so we can control them ourselves
                text = step[:-3] if step.endswith("...") else step
                if is_last:
                    items.append(f'<div class="activity-step">{text}{_ANIMATED_DOTS}</div>')
                else:
                    items.append(f'<div class="activity-step activity-step-done">{text}</div>')
            html = f"""
            <details open class="activity-panel">
                <summary class="activity-summary">
                    ⟳ Agent working…
                    <span class="activity-count">{len(steps)}</span>
                </summary>
                <div class="activity-steps">{"".join(items)}</div>
            </details>"""
            return gr.update(visible=True, value=html)

        # chat_outputs: chatbot, input, session_list_html, active_session_id, sugg_row,
        #               btns×4, texts×4, agent_activity, files, was_pending, timer, send_btn, stop_btn
        chat_outputs = (
            [chatbot, user_input, session_list_html, active_session_id, sugg_row]
            + sugg_btns + sugg_texts
            + [agent_activity, cited_files, was_pending, timer, send_btn, stop_btn]
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
            admin_config.load()
            return (
                gr.update(visible=False), gr.update(visible=True), gr.update(visible=False),
                admin_config.get("temperature", config.LLM_TEMPERATURE),
                admin_config.get("max_tool_calls", config.MAX_TOOL_CALLS),
                get_orchestrator_prompt(),
                get_aggregation_prompt(),
                get_fallback_response_prompt(),
            )
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
            no_activity = gr.update(visible=False, value="")

            if not message or not message.strip():
                yield chat_history, "", gr.update(), session_id, row_upd, *btn_upds, *text_upds, no_activity, no_files, False, gr.update(), gr.update(), gr.update()
                return

            # Apply state filter
            if selected_state and selected_state.lower() not in ["all", "all states"]:
                rag_system.set_state_filter(selected_state)
            else:
                rag_system.set_state_filter(None)

            streamer = chat_interface.stream_response(message, session_id=session_id, state_filter=selected_state)
            _, new_session_id, _ = next(streamer)  # saves user message, returns session_id immediately

            sessions = chat_interface.get_sessions()
            html = _render_sessions_html(sessions, active_id=new_session_id)
            base_display = list(chat_history or []) + [{"role": "user", "content": message.strip()}]

            def _final_yield(partial_response, new_session_id, activity_steps):
                _, options = _parse_options(partial_response)
                row_upd2, btn_upds2, text_upds2 = _sugg_updates(options)
                cited_html = _get_cited_html(partial_response)
                files_upd = gr.update(visible=bool(cited_html), value=cited_html)
                activity_upd = _render_activity(activity_steps, done=True)
                sessions = chat_interface.get_sessions()
                html = _render_sessions_html(sessions, active_id=new_session_id)
                final_display = base_display + [{"role": "assistant", "content": _clean_message(partial_response or "No response generated.")}]
                return (final_display, "", gr.update(value=html), new_session_id,
                        row_upd2, *btn_upds2, *text_upds2, activity_upd, files_upd, False,
                        gr.update(active=False), _send_show, _stop_hide)

            # Show thinking indicator while agent is working
            yield (base_display + [{"role": "assistant", "content": _THINKING_HTML}],
                   "", gr.update(value=html), new_session_id,
                   row_upd, *btn_upds, *text_upds, no_activity, no_files, False,
                   gr.update(active=False), gr.update(visible=False), gr.update(visible=True))

            # Stream tokens and activity steps as they arrive
            partial_response = ""
            activity_steps = []
            try:
                for partial_response, _, activity_steps in streamer:
                    activity_upd = _render_activity(activity_steps)
                    if partial_response:
                        display = base_display + [{"role": "assistant", "content": _clean_message(partial_response)}]
                        yield (display, "", gr.update(), new_session_id,
                               row_upd, *btn_upds, *text_upds, gr.update(), no_files, False,
                               gr.update(active=False), gr.update(visible=False), gr.update(visible=True))
                    else:
                        # Leave chatbot untouched (gr.update()) so the thinking word
                        # element stays in the DOM and the JS cycler can update it
                        yield (gr.update(), "", gr.update(), new_session_id,
                               row_upd, *btn_upds, *text_upds, activity_upd, no_files, False,
                               gr.update(active=False), gr.update(visible=False), gr.update(visible=True))
            except Exception as e:
                partial_response = f"❌ Error: {str(e)}"

            yield _final_yield(partial_response, new_session_id, activity_steps)

        send_btn.click(chat_handler_ui, [user_input, chatbot, active_session_id, state_dropdown_chat], chat_outputs)

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
            + [agent_activity, cited_files, timer, send_btn, stop_btn]
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
                    row_upd, *btn_upds, *text_upds, gr.update(), files_upd, gr.update(active=False),
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

        # Nav
        admin_btn.click(
            show_docs, None,
            views + [ai_temperature, ai_max_tools, ai_orchestrator_prompt, ai_aggregation_prompt, ai_fallback_prompt],
        )
        history_nav_btn.click(show_history, None, views)

        # Documents
        add_btn.click(upload_handler, [files_input, state_dropdown],
                      [files_input, file_table, state_dropdown], show_progress="corner")

        def refresh_docs(state_filter, search_query):
            return render_file_table(state_filter, search_query, 0), gr.update(choices=["All States"] + doc_manager.get_states()), 0, _page_info(0, state_filter, search_query)

        refresh_docs_btn.click(refresh_docs, [file_state_filter, file_search], [file_table, file_state_filter, file_page, page_info])

        def _page_info(page, state_filter, search_query):
            files = doc_manager.get_files_structured()
            if state_filter and state_filter.lower() not in ("all states", "all"):
                files = [f for f in files if f["state"] == state_filter]
            if search_query and search_query.strip():
                q = search_query.strip().lower()
                files = [f for f in files if q in f["filename"].lower() or q in f["state"].lower()]
            total_pages = max(1, (len(files) + PAGE_SIZE - 1) // PAGE_SIZE)
            return f"Page {page + 1} of {total_pages}"

        def go_prev(page, state_filter, search_query):
            new_page = max(0, page - 1)
            return render_file_table(state_filter, search_query, new_page), new_page, _page_info(new_page, state_filter, search_query)

        def go_next(page, state_filter, search_query):
            files = doc_manager.get_files_structured()
            if state_filter and state_filter.lower() not in ("all states", "all"):
                files = [f for f in files if f["state"] == state_filter]
            total_pages = max(1, (len(files) + PAGE_SIZE - 1) // PAGE_SIZE)
            new_page = min(total_pages - 1, page + 1)
            return render_file_table(state_filter, search_query, new_page), new_page, _page_info(new_page, state_filter, search_query)

        def reset_page(state_filter, search_query):
            return render_file_table(state_filter, search_query, 0), 0, _page_info(0, state_filter, search_query)

        prev_btn.click(go_prev, [file_page, file_state_filter, file_search], [file_table, file_page, page_info])
        next_btn.click(go_next, [file_page, file_state_filter, file_search], [file_table, file_page, page_info])
        file_search.change(reset_page, [file_state_filter, file_search], [file_table, file_page, page_info])
        file_state_filter.change(reset_page, [file_state_filter, file_search], [file_table, file_page, page_info])

        # Show confirmation panel when Clear All is clicked
        clear_docs_btn.click(
            lambda: gr.update(visible=True),
            None, confirm_panel
        )

        # Cancel — hide panel and clear input
        cancel_delete_btn.click(
            lambda: (gr.update(visible=False), ""),
            None, [confirm_panel, confirm_input]
        )

        # Confirm — only execute if input is exactly "DELETE"
        def clear_handler_full(confirm_text):
            if confirm_text.strip() != "DELETE":
                gr.Warning('Type  DELETE  (all caps) to confirm.')
                return gr.update(), gr.update(choices=get_state_choices()), gr.update(visible=True), ""
            doc_manager.clear_all()
            gr.Info("All documents and vectors have been removed.")
            return render_file_table(), gr.update(choices=get_state_choices()), gr.update(visible=False), ""

        confirm_delete_btn.click(
            clear_handler_full,
            [confirm_input],
            [file_table, state_dropdown, confirm_panel, confirm_input]
        )

        # ── Re-index ──────────────────────────────────────────────────────────

        def reindex_handler(progress=gr.Progress()):
            total_md = len(list(doc_manager.markdown_dir.rglob("*.md")))
            if total_md == 0:
                return "⚠️ No documents found to re-index.", gr.update()
            indexed = doc_manager.reindex_all(progress_callback=progress)
            return f"✅ Re-indexed {indexed} of {total_md} documents successfully.", render_file_table()

        reindex_btn.click(
            reindex_handler,
            None,
            [reindex_status, file_table],
        )

        # ── AI Settings ───────────────────────────────────────────────────────

        def save_ai_settings(temperature, max_tool_calls, orch_prompt, agg_prompt, fallback_prompt):
            admin_config.save({
                "temperature":              temperature,
                "max_tool_calls":           int(max_tool_calls),
                "orchestrator_prompt":      orch_prompt.strip(),
                "aggregation_prompt":       agg_prompt.strip(),
                "fallback_response_prompt": fallback_prompt.strip(),
            })
            rag_system.apply_settings()
            ts = admin_config.get_all().get("last_updated", "")
            return f"✅ Settings saved at {ts[:19].replace('T', ' ')} UTC"

        def reset_ai_settings():
            admin_config.reset()
            rag_system.apply_settings()
            return (
                config.LLM_TEMPERATURE,
                config.MAX_TOOL_CALLS,
                get_orchestrator_prompt(),
                get_aggregation_prompt(),
                get_fallback_response_prompt(),
                "↺ Reset to system defaults.",
            )

        ai_save_btn.click(
            save_ai_settings,
            [ai_temperature, ai_max_tools, ai_orchestrator_prompt, ai_aggregation_prompt, ai_fallback_prompt],
            [ai_settings_status],
        )
        ai_reset_btn.click(
            reset_ai_settings,
            None,
            [ai_temperature, ai_max_tools, ai_orchestrator_prompt, ai_aggregation_prompt, ai_fallback_prompt, ai_settings_status],
        )

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
