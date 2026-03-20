"""
Standalone Admin Panel — mounted at /admin by main.py.
Shares rag_system and doc_manager instances with the main chat app.
"""
import gradio as gr
import config
from core import admin_config
from rag_agent.prompts import (
    get_orchestrator_prompt,
    get_aggregation_prompt,
    get_fallback_response_prompt,
)
from urllib.parse import quote

DEFAULT_STATE_CHOICES = ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]
PAGE_SIZE = 15

_admin_css = """
footer, .footer, [class*="footer"] { display: none !important; }
html, body {
    background: #1a1a1a !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
}
.gradio-container {
    max-width: 100vw !important;
    width: 100vw !important;
    padding: 0 !important;
    margin: 0 !important;
    background: #1a1a1a !important;
}
.gradio-container > *, .contain, .main, .app, .fillable {
    max-width: 100% !important;
    width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
    box-sizing: border-box !important;
}

/* ── Top back-bar ── */
#admin-back-bar {
    position: sticky;
    top: 0;
    z-index: 100;
    background: #111111;
    border-bottom: 1px solid #1e1e1e;
    padding: 10px 24px;
    display: flex;
    align-items: center;
}
.admin-back-link {
    color: #555;
    text-decoration: none !important;
    font-size: 13px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    transition: color 0.15s;
    min-width: 100px;
}
.admin-back-link:hover { color: #aaa !important; }
.admin-page-title {
    font-size: 14px;
    font-weight: 600;
    color: #ccc;
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
}

/* ── Content area ── */
#admin-content {
    max-width: 960px;
    margin: 0 auto;
    padding: 24px 24px 40px;
    box-sizing: border-box;
}
#admin-content > *,
#admin-content .block {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}

/* ── Tabs ── */
#admin-tabs > .tab-nav { border-bottom: 1px solid #2a2a2a !important; }
#admin-tabs .tab-nav button { color: #888 !important; font-size: 13px !important; }
#admin-tabs .tab-nav button.selected { color: #ececec !important; border-bottom-color: #10a37f !important; }
#admin-tabs .tabitem {
    background: #141414 !important;
    border: 1px solid #1e1e1e !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
    padding: 16px !important;
}

/* ── Inputs ── */
input, textarea {
    background: #1a1a1a !important;
    border: 1px solid #2e2e2e !important;
    border-radius: 8px !important;
    color: #ececec !important;
}
input:focus, textarea:focus { border-color: #444 !important; outline: none !important; }
.wrap-inner, select {
    background: #1a1a1a !important;
    border: 1px solid #2e2e2e !important;
    border-radius: 8px !important;
    color: #ececec !important;
}
button { border-radius: 8px !important; }
h1, h2, h3, h4, h5, h6, p, span, div { color: inherit; }

/* ── Namespace status ── */
#ns-status-row { align-items: center !important; gap: 6px !important; margin-bottom: 12px !important; }
#ns-refresh-btn button {
    background: transparent !important; border: 1px solid #2a2a2a !important;
    color: #555 !important; border-radius: 6px !important; font-size: 13px !important;
    padding: 2px 8px !important; min-width: 32px !important; height: 28px !important;
}
#ns-refresh-btn button:hover { border-color: #444 !important; color: #aaa !important; }
.ns-overview { width: 100%; }
.ns-indexing-banner {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    background: #1a2a1a; border: 1px solid #2a4a2a; border-radius: 8px;
    padding: 8px 12px; font-size: 12px; color: #7ec87e; margin-bottom: 10px;
}
.ns-pct { margin-left: auto; color: #5cb85c; font-weight: 600; white-space: nowrap; }
.ns-progress-bar { width: 100%; height: 3px; background: #1e3a1e; border-radius: 2px; margin-top: 4px; }
.ns-progress-fill { height: 100%; background: #10a37f; border-radius: 2px; transition: width 0.4s; }
.ns-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
.ns-pill {
    display: flex; align-items: center; gap: 8px;
    background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px;
    padding: 6px 12px; font-size: 12px;
}
.ns-pill-active { border-color: #2a5a3a; background: #141e18; }
.ns-pill-name { color: #aaa; font-weight: 500; letter-spacing: 0.02em; }
.ns-pill-count {
    background: #252525; color: #666; border-radius: 5px;
    padding: 2px 8px; font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums;
    min-width: 28px; text-align: center;
}
.ns-pill-active .ns-pill-count { background: #1a3028; color: #10a37f; }
.ns-empty { font-size: 12px; color: #444; padding: 4px 2px; }

/* ── File upload ── */
.file-preview, [data-testid="file-upload"] {
    background: #1e1e1e !important;
    border: 1px dashed #2e2e2e !important;
    border-radius: 10px !important;
}
.file-preview *, [data-testid="file-upload"] * { color: #aaa !important; }

/* ── Pagination ── */
#pagination-row { margin-top: 8px !important; justify-content: center !important; gap: 12px !important; }
#pagination-row button {
    background: transparent !important; border: 1px solid #2a2a2a !important;
    color: #666 !important; font-size: 12px !important;
    padding: 4px 12px !important; border-radius: 6px !important;
}
#pagination-row button:hover { border-color: #444 !important; color: #aaa !important; }
#page-info p { font-size: 12px !important; color: #555 !important; }

/* ── Danger zone ── */
#danger-zone-accordion {
    margin-top: 16px !important;
    border: 1px solid #3a1a1a !important;
    border-radius: 8px !important;
    background: #1a1010 !important;
}
#danger-zone-accordion > .label-wrap span { color: #a04040 !important; font-size: 12px !important; }
#clear-all-btn button {
    background-color: #8b2020 !important; border-color: #a32828 !important; color: #fff !important;
}
#clear-all-btn button:hover { background-color: #a32828 !important; }
#confirm-delete-input textarea {
    background: #1a0808 !important; border-color: #8b2020 !important;
    color: #ffcccc !important; font-size: 15px !important;
    text-align: center !important; letter-spacing: 2px !important;
}
#confirm-delete-confirm-btn button {
    background-color: #8b2020 !important; border-color: #a32828 !important; color: #fff !important;
}
#confirm-delete-confirm-btn button:hover { background-color: #c0392b !important; }

/* ── Reindex btn ── */
#reindex-btn button {
    background-color: #1a3a2a !important; border-color: #2a5a3a !important; color: #5cb88a !important;
}
#reindex-btn button:hover { background-color: #1f4a34 !important; border-color: #3a7a50 !important; }
#reindex-status p { font-size: 12px !important; color: #5cb88a !important; margin: 4px 0 !important; }

/* ── AI settings ── */
#ai-settings-status p { font-size: 12px !important; color: #10a37f !important; margin: 4px 0 !important; }
.progress-text { display: none !important; }
.progress-bar { background: #10a37f !important; }
"""


def create_admin_ui(rag_system, doc_manager):

    def get_state_choices():
        all_states = ["All States"] + DEFAULT_STATE_CHOICES
        all_states += [s for s in doc_manager.get_states() if s not in all_states]
        return all_states

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
            rows += (
                f'<tr>'
                f'<td><span class="state-badge">{f["state"]}</span></td>'
                f'<td class="filename-cell">📄 {f["filename"]}</td>'
                f'<td><a href="/download/{quote(safe)}" download="{safe}" class="dl-btn">↓ Download</a></td>'
                f'</tr>'
            )

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
        </style>"""

    def render_namespace_status():
        summary  = doc_manager.get_namespace_summary()
        statuses = doc_manager.get_indexing_status()

        html = '<div class="ns-overview">'
        active_namespaces = set()
        if statuses:
            for status in statuses:
                op    = status.get("operation", "indexing").capitalize()
                ns    = status.get("namespace") or "—"
                fname = status.get("filename") or ""
                done  = status.get("done", 0)
                total = status.get("total", 0)
                pct   = int(status.get("progress", 0) * 100)
                bar   = f'<div class="ns-progress-bar"><div class="ns-progress-fill" style="width:{pct}%"></div></div>'
                html += (
                    f'<div class="ns-indexing-banner">'
                    f'⏳ {op} in progress &nbsp;·&nbsp; <strong>[{ns}]</strong> {fname}'
                    f'<span class="ns-pct">{done}/{total} &nbsp; {pct}%</span>'
                    f'{bar}</div>'
                )
                active_namespaces.add(ns)

        if not summary:
            html += '<div class="ns-empty">No namespaces indexed yet.</div>'
        else:
            html += '<div class="ns-grid">'
            for ns, count in summary.items():
                cls = "ns-pill ns-pill-active" if ns in active_namespaces else "ns-pill"
                html += f'<div class="{cls}"><span class="ns-pill-name">{ns}</span><span class="ns-pill-count">{count}</span></div>'
            html += '</div>'
        html += '</div>'
        return html

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

    def _page_info(page, state_filter, search_query):
        files = doc_manager.get_files_structured()
        if state_filter and state_filter.lower() not in ("all states", "all"):
            files = [f for f in files if f["state"] == state_filter]
        if search_query and search_query.strip():
            q = search_query.strip().lower()
            files = [f for f in files if q in f["filename"].lower() or q in f["state"].lower()]
        total_pages = max(1, (len(files) + PAGE_SIZE - 1) // PAGE_SIZE)
        return f"Page {page + 1} of {total_pages}"

    # ── Build UI ──────────────────────────────────────────────────────────────

    with gr.Blocks(title="Admin — Case Agent", css=_admin_css) as demo:

        gr.HTML(
            '<div id="admin-back-bar">'
            '<a href="/" class="admin-back-link">← Back to Chat</a>'
            '<span class="admin-page-title">Admin Panel</span>'
            '</div>'
        )

        with gr.Column(elem_id="admin-content"):

            with gr.Tabs(elem_id="admin-tabs"):

                # ── Tab 1: Documents ──────────────────────────────────────────
                with gr.TabItem("📄 Documents"):

                    with gr.Row(elem_id="ns-status-row"):
                        ns_status_html = gr.HTML(value=render_namespace_status(), elem_id="ns-status")
                        ns_refresh_btn = gr.Button("↻", size="sm", scale=0, min_width=32, elem_id="ns-refresh-btn")

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
                        prev_btn  = gr.Button("← Prev", size="sm", scale=0, min_width=80)
                        page_info = gr.Markdown("Page 1", elem_id="page-info")
                        next_btn  = gr.Button("Next →", size="sm", scale=0, min_width=80)

                    with gr.Accordion("Danger Zone", open=False, elem_id="danger-zone-accordion"):
                        reindex_btn    = gr.Button("🔄 Re-index All Documents", elem_id="reindex-btn")
                        reindex_status = gr.Markdown("", elem_id="reindex-status")

                    with gr.Column(visible=False, elem_id="confirm-reindex-panel") as confirm_reindex_panel:
                        gr.HTML("""
                        <div style="background:#1a1a0a;border:1px solid #7a6a00;border-radius:10px;padding:16px 18px;margin-top:12px;">
                            <div style="color:#ffd700;font-size:15px;font-weight:700;margin-bottom:6px;">⚠️ Re-index All Documents</div>
                            <div style="color:#ccc;font-size:13px;line-height:1.5;">
                                This will <strong style="color:#fff;">clear all vectors and parent chunks</strong> then rebuild the index from scratch.<br>
                                Original PDFs and markdown files are preserved.<br>
                                <span style="color:#ffcc00;">This may take a long time for large document sets.</span>
                            </div>
                        </div>
                        """)
                        confirm_reindex_input = gr.Textbox(
                            placeholder='Type  REINDEX  to confirm',
                            show_label=False, elem_id="confirm-reindex-input", max_lines=1,
                        )
                        with gr.Row():
                            confirm_reindex_btn = gr.Button("Confirm Re-index", variant="stop", scale=1, elem_id="confirm-reindex-confirm-btn")
                            cancel_reindex_btn  = gr.Button("Cancel", scale=1, elem_id="confirm-reindex-cancel-btn")

                        gr.HTML('<div style="margin-top:12px;margin-bottom:6px;font-size:12px;color:#aaa;">Delete by State</div>')
                        with gr.Row():
                            del_state_dropdown = gr.Dropdown(
                                choices=get_state_choices(), value=None,
                                label="Select state to delete", scale=3, elem_id="del-state-dropdown",
                            )
                            del_state_btn = gr.Button("🗑 Delete State", variant="stop", scale=1, elem_id="del-state-btn")
                        del_state_status = gr.Markdown("", elem_id="del-state-status")

                        clear_docs_btn = gr.Button("🗑 Clear All Documents", elem_id="clear-all-btn")

                    with gr.Column(visible=False, elem_id="confirm-del-state-panel") as confirm_del_state_panel:
                        confirm_del_state_html  = gr.HTML("")
                        confirm_del_state_input = gr.Textbox(
                            placeholder="Type  DELETE  to confirm",
                            show_label=False, elem_id="confirm-del-state-input", max_lines=1,
                        )
                        with gr.Row():
                            confirm_del_state_btn  = gr.Button("Confirm Delete", variant="stop", scale=1, elem_id="confirm-del-state-confirm-btn")
                            cancel_del_state_btn   = gr.Button("Cancel", scale=1, elem_id="confirm-del-state-cancel-btn")

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
                            show_label=False, elem_id="confirm-delete-input", max_lines=1,
                        )
                        with gr.Row():
                            confirm_delete_btn = gr.Button("Confirm Delete", variant="stop", scale=1, elem_id="confirm-delete-confirm-btn")
                            cancel_delete_btn  = gr.Button("Cancel", scale=1, elem_id="confirm-delete-cancel-btn")

                # ── Tab 2: AI Settings ────────────────────────────────────────
                with gr.TabItem("🤖 AI Settings"):

                    gr.HTML('<div style="color:#888;font-size:12px;margin-bottom:16px;">Changes apply immediately to the next query. Leave a prompt field empty to use the system default.</div>')

                    admin_config.load()
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
                        ai_save_btn  = gr.Button("💾 Save Settings", variant="primary", scale=2)
                        ai_reset_btn = gr.Button("↺ Reset to Defaults", scale=1)

        # ── Polling timer for indexing progress ──────────────────────────────
        admin_timer = gr.Timer(value=4.0, active=True)

        # ── Event wiring ─────────────────────────────────────────────────────

        add_btn.click(
            upload_handler, [files_input, state_dropdown],
            [files_input, file_table, state_dropdown], show_progress="corner",
            concurrency_limit=None,
        ).then(render_namespace_status, None, ns_status_html)

        def refresh_docs(state_filter, search_query):
            return (
                render_file_table(state_filter, search_query, 0),
                gr.update(choices=["All States"] + doc_manager.get_states()),
                0,
                _page_info(0, state_filter, search_query),
            )

        refresh_docs_btn.click(refresh_docs, [file_state_filter, file_search], [file_table, file_state_filter, file_page, page_info])

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

        # Delete by state
        def del_state_click(state):
            if not state or state.lower() in ("all states", "all", ""):
                gr.Warning("Please select a specific state to delete.")
                return gr.update(visible=False), gr.update(), ""
            warn_html = (
                f'<div style="background:#2a0a0a;border:1px solid #8b2020;border-radius:10px;padding:14px 16px;margin-top:8px;">'
                f'<div style="color:#ff6b6b;font-size:14px;font-weight:700;margin-bottom:4px;">⚠️ Delete state: {state}</div>'
                f'<div style="color:#ccc;font-size:13px;line-height:1.5;">'
                f'This will permanently delete <strong style="color:#fff;">all {state} documents</strong>, '
                f'their vectors and stored chunks.<br>'
                f'<span style="color:#ff9999;">This action cannot be undone.</span>'
                f'</div></div>'
            )
            return gr.update(visible=True), gr.update(value=warn_html), ""

        del_state_btn.click(del_state_click, [del_state_dropdown], [confirm_del_state_panel, confirm_del_state_html, confirm_del_state_input])
        cancel_del_state_btn.click(lambda: (gr.update(visible=False), ""), None, [confirm_del_state_panel, confirm_del_state_input])

        def confirm_del_state_handler(state, confirm_text):
            if confirm_text.strip() != "DELETE":
                gr.Warning("Type  DELETE  (all caps) to confirm.")
                return gr.update(), gr.update(choices=get_state_choices()), gr.update(visible=True), "", ""
            if not state or state.lower() in ("all states", "all", ""):
                gr.Warning("No state selected.")
                return gr.update(), gr.update(choices=get_state_choices()), gr.update(visible=False), "", ""
            summary = doc_manager.delete_namespace(state)
            msg = (
                f"✅ Deleted **{state}**: "
                f"{summary['original_files']} files, "
                f"{summary['markdown_files']} markdown, "
                f"{summary['parent_chunks']} chunks, "
                f"{summary['vectors']} vectors removed."
            )
            gr.Info(f"State '{state}' deleted.")
            return render_file_table(), gr.update(choices=get_state_choices(), value=None), gr.update(visible=False), "", msg

        confirm_del_state_btn.click(
            confirm_del_state_handler,
            [del_state_dropdown, confirm_del_state_input],
            [file_table, del_state_dropdown, confirm_del_state_panel, confirm_del_state_input, del_state_status],
        )

        # Clear all
        clear_docs_btn.click(lambda: gr.update(visible=True), None, confirm_panel)
        cancel_delete_btn.click(lambda: (gr.update(visible=False), ""), None, [confirm_panel, confirm_input])

        def clear_handler_full(confirm_text):
            if confirm_text.strip() != "DELETE":
                gr.Warning("Type  DELETE  (all caps) to confirm.")
                return gr.update(), gr.update(choices=get_state_choices()), gr.update(visible=True), ""
            doc_manager.clear_all()
            gr.Info("All documents and vectors have been removed.")
            return render_file_table(), gr.update(choices=get_state_choices()), gr.update(visible=False), ""

        confirm_delete_btn.click(clear_handler_full, [confirm_input], [file_table, state_dropdown, confirm_panel, confirm_input])

        # Re-index
        reindex_btn.click(lambda: gr.update(visible=True), None, confirm_reindex_panel)
        cancel_reindex_btn.click(lambda: (gr.update(visible=False), ""), None, [confirm_reindex_panel, confirm_reindex_input])

        def reindex_handler(confirm_text, progress=gr.Progress()):
            if confirm_text.strip() != "REINDEX":
                gr.Warning("Type  REINDEX  (all caps) to confirm.")
                return "", gr.update(), gr.update(visible=True), ""
            total_md = len(list(doc_manager.markdown_dir.rglob("*.md")))
            if total_md == 0:
                return "⚠️ No documents found to re-index.", gr.update(), gr.update(visible=False), ""
            indexed = doc_manager.reindex_all(progress_callback=progress)
            return (
                f"✅ Re-indexed {indexed} of {total_md} documents successfully.",
                render_file_table(),
                gr.update(visible=False),
                "",
            )

        confirm_reindex_btn.click(
            reindex_handler,
            [confirm_reindex_input],
            [reindex_status, file_table, confirm_reindex_panel, confirm_reindex_input],
        ).then(render_namespace_status, None, ns_status_html)

        ns_refresh_btn.click(render_namespace_status, None, ns_status_html)
        admin_timer.tick(render_namespace_status, None, ns_status_html, show_progress=False)

        # AI Settings
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

    demo._rag_system  = rag_system
    demo._doc_manager = doc_manager
    return demo
