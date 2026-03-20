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

STATE_COLORS = {
    "NSW": "#185FA5",
    "QLD": "#3B6D11",
    "VIC": "#854F0B",
    "WA":  "#534AB7",
    "SA":  "#D85A30",
    "TAS": "#0F6E56",
    "ACT": "#D4537E",
    "NT":  "#BA7517",
}

_PILL_BG   = {"NSW":"#163351","QLD":"#1a3410","VIC":"#3a2010","WA":"#252070","SA":"#3a1a10","TAS":"#0e3a28","ACT":"#3a1028","NT":"#3a2a08"}
_PILL_TEXT = {"NSW":"#7DC4F5","QLD":"#8ED468","VIC":"#E8A963","WA":"#BCB6F5","SA":"#F0A080","TAS":"#70DDB8","ACT":"#F0A0C0","NT":"#E8C060"}


def _pill(state: str) -> str:
    bg   = _PILL_BG.get(state, "#2a2a2a")
    text = _PILL_TEXT.get(state, "#888")
    return (
        f'<span style="display:inline-block;padding:2px 10px;font-size:11px;font-weight:600;'
        f'border-radius:20px;background:{bg};color:{text};'
        f'letter-spacing:.02em;white-space:nowrap">{state}</span>'
    )


# ── CSS ───────────────────────────────────────────────────────────────────────
_admin_css = """
footer, .footer, [class*="footer"] { display: none !important; }
html, body { background: #0d0d0d !important; overflow-y: auto !important; overflow-x: hidden !important; }
.gradio-container {
    max-width: 100vw !important; width: 100vw !important;
    padding: 0 32px 32px !important; background: #0d0d0d !important;
    font-family: 'Inter', sans-serif !important;
    box-sizing: border-box !important;
}
.gradio-container > *, .contain, .main, .app, .fillable {
    max-width: 100% !important; box-sizing: border-box !important;
}
.progress-text { display: none !important; }

/* ── Stats card ── */
.stat-cards-row { display: flex; gap: 12px; flex-wrap: wrap; }
.stat-card {
    flex: 1; background: #161616; border-radius: 8px;
    padding: 14px 16px; min-width: 100px;
}
.stat-card .sc-label {
    font-size: 11px; color: #aaa; margin-bottom: 6px;
    display: flex; align-items: center; gap: 6px;
}
.stat-card .sc-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.stat-card .sc-count { font-size: 22px; font-weight: 600; }

/* ── Section card ── */
.section-card {
    background: #111; border: 1px solid #1e1e1e;
    border-radius: 12px; overflow: hidden; margin-bottom: 16px;
}
.section-head {
    padding: 14px 20px; border-bottom: 1px solid #1a1a1a;
    display: flex; align-items: center; justify-content: space-between;
}
.section-head-title { font-size: 14px; font-weight: 600; color: #fff; }
.section-head-sub   { font-size: 12px; color: #666; margin-left: 8px; }
.section-body { padding: 20px; }

/* ── Tabs ── */
#admin-tabs > .tab-nav {
    background: #111 !important; border-bottom: 1px solid #1e1e1e !important;
    padding: 0 !important; margin: 0 0 16px !important;
    display: flex !important; gap: 0 !important;
}
#admin-tabs > .tab-nav button {
    color: #666 !important; font-size: 13px !important;
    padding: 10px 18px !important; border-radius: 0 !important;
    border: none !important; border-bottom: 2px solid transparent !important;
    background: transparent !important; font-weight: 400 !important;
    margin-bottom: -1px !important;
}
#admin-tabs > .tab-nav button.selected {
    color: #fff !important; border-bottom-color: #fff !important; font-weight: 600 !important;
}
#admin-tabs > .tab-nav button:hover:not(.selected) { color: #ccc !important; }
#admin-tabs > .tabitem { background: transparent !important; border: none !important; padding: 0 !important; }

/* ── Filter toolbar ── */
#filter-toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
#adm-search input {
    background: #1a1a1a !important; border: 1px solid #2a2a2a !important;
    border-radius: 8px !important; color: #fff !important; font-size: 13px !important;
}
#adm-search input::placeholder { color: #555 !important; }
#state-filter-dd select, #state-filter-dd .wrap-inner {
    background: #1a1a1a !important; border: 1px solid #2a2a2a !important;
    border-radius: 8px !important; color: #fff !important; font-size: 13px !important;
}
#upload-toggle-btn button {
    padding: 8px 16px !important; font-size: 13px !important; font-weight: 500 !important;
    border-radius: 8px !important; background: #e8e8e8 !important;
    color: #111 !important; border: none !important; white-space: nowrap !important;
}
#upload-toggle-btn button:hover { background: #fff !important; }

/* ── Upload panel ── */
#upload-panel {
    background: #161616; border: 1px solid #1e1e1e;
    border-radius: 10px; padding: 20px; margin-bottom: 16px;
}
#upload-panel .block { background: transparent !important; border: none !important; box-shadow: none !important; }
.upload-panel-label {
    font-size: 11px; font-weight: 600; color: #aaa;
    text-transform: uppercase; letter-spacing: .04em; margin-bottom: 8px;
}
#upload-panel input, #upload-panel textarea,
#upload-panel select, #upload-panel .wrap-inner {
    background: #1e1e1e !important; border: 1px solid #2a2a2a !important;
    border-radius: 8px !important; color: #fff !important; font-size: 13px !important;
}
.file-preview, [data-testid="file-upload"] {
    background: #1e1e1e !important; border: 2px dashed #2a2a2a !important; border-radius: 10px !important;
}
.file-preview *, [data-testid="file-upload"] * { color: #666 !important; }
#add-docs-btn button {
    background: #e8e8e8 !important; color: #111 !important;
    border: none !important; border-radius: 8px !important;
    font-size: 13px !important; font-weight: 500 !important;
}
#add-docs-btn button:hover { background: #fff !important; }

/* ── File table ── */
.adm-table { width: 100%; border-collapse: collapse; font-size: 13px; table-layout: fixed; }
.adm-table thead tr { border-bottom: 1px solid #1e1e1e; }
.adm-table th {
    padding: 10px 12px; text-align: left;
    font-size: 10px; font-weight: 500; color: #666;
    background: #0d0d0d; text-transform: uppercase; letter-spacing: .04em;
}
.adm-table td { padding: 13px 12px; border-bottom: 1px solid #161616; vertical-align: middle; color: #e0e0e0; }
.adm-table tr:last-child td { border-bottom: none; }
.adm-table tr:hover td { background: #161616; }
.adm-table .col-cb { width: 36px; }
.adm-table .col-st { width: 90px; }
.adm-table .col-dt { width: 90px; color: #888; font-size: 12px; }
.adm-table .col-ac { width: 100px; text-align: right; }
.fn-cell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
input[type=checkbox] { width: 14px; height: 14px; cursor: pointer; border-radius: 3px; accent-color: #10a37f; }
.row-dl {
    color: #666; text-decoration: none; font-size: 11px;
    padding: 3px 9px; border: 1px solid #252525; border-radius: 5px;
    white-space: nowrap; transition: all .12s; display: inline-block;
}
.row-dl:hover { background: #1e1e1e; color: #ccc; border-color: #3a3a3a; }

/* ── Pagination ── */
#adm-pagination {
    padding: 14px 20px; display: flex; align-items: center;
    justify-content: space-between; border-top: 1px solid #1a1a1a;
}
.pager-info { font-size: 12px; color: #888; }
#pagination-row { justify-content: flex-end !important; gap: 6px !important; margin: 0 !important; }
#pagination-row button {
    background: #1a1a1a !important; border: 1px solid #2a2a2a !important;
    color: #ccc !important; font-size: 12px !important; font-weight: 500 !important;
    padding: 6px 14px !important; border-radius: 7px !important; min-width: auto !important;
}
#pagination-row button:hover { border-color: #555 !important; color: #fff !important; background: #222 !important; }
#page-info p { font-size: 12px !important; color: #888 !important; margin: 0 !important; }
#page-info { display: flex; align-items: center; }

/* ── Inputs (global) ── */
input, textarea, select, .wrap-inner {
    background: #1a1a1a !important; border: 1px solid #2a2a2a !important;
    border-radius: 8px !important; color: #fff !important; font-size: 13px !important;
}
input:focus, textarea:focus { border-color: #444 !important; outline: none !important; }
button { border-radius: 8px !important; }
label span { color: #ccc !important; font-size: 13px !important; }

/* ── AI Settings ── */
#ai-settings-status p { font-size: 12px !important; color: #10a37f !important; margin: 4px 0 !important; }
.ai-field-label {
    font-size: 11px; font-weight: 600; color: #aaa;
    text-transform: uppercase; letter-spacing: .04em; margin-bottom: 5px; margin-top: 12px;
}
#ai-save-btn button {
    background: #e8e8e8 !important; color: #111 !important;
    border: none !important; font-weight: 500 !important;
}
#ai-save-btn button:hover { background: #fff !important; }

/* ── Danger zone ── */
#danger-zone-accordion {
    margin-top: 16px !important; border: 1px solid #3a1a1a !important;
    border-radius: 10px !important; background: #130a0a !important;
}
#danger-zone-accordion > .label-wrap span { color: #a04040 !important; font-size: 12px !important; }
#clear-all-btn button { background-color: #8b2020 !important; border-color: #a32828 !important; color: #fff !important; }
#confirm-delete-input textarea { background: #1a0808 !important; border-color: #8b2020 !important; color: #ffcccc !important; text-align: center !important; letter-spacing: 2px !important; }
#confirm-delete-confirm-btn button { background-color: #8b2020 !important; border-color: #a32828 !important; color: #fff !important; }
#reindex-btn button { background-color: #1a3a2a !important; border: 1px solid #2a5a3a !important; color: #5cb88a !important; }
#reindex-status p { font-size: 12px !important; color: #5cb88a !important; margin: 4px 0 !important; }
"""

_BACK_SVG = (
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2.2" style="flex-shrink:0">'
    '<path d="M19 12H5M12 5l-7 7 7 7"/></svg>'
)

_FILE_SVG = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" '
    'stroke="white" stroke-width="2">'
    '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>'
    '<polyline points="14 2 14 8 20 8"/>'
    '<line x1="16" y1="13" x2="8" y2="13"/>'
    '<line x1="16" y1="17" x2="8" y2="17"/>'
    '</svg>'
)

_HEADER_HTML = (
    '<div style="display:flex;align-items:center;justify-content:space-between;'
    'padding:14px 0 12px;border-bottom:1px solid #1e1e1e;margin-bottom:20px">'
    '<div style="display:flex;align-items:center;gap:10px">'
    '<span style="font-size:16px;font-weight:700;color:#ececec;letter-spacing:-0.01em">Case Agent</span>'
    '<span style="color:#333;font-size:16px;margin:0 6px">/</span>'
    '<span style="font-size:14px;color:#666">Admin Panel</span>'
    '</div>'
    f'<a href="/" style="font-size:13px;color:#7DC4F5;text-decoration:none;'
    f'display:flex;align-items:center;gap:5px">{_BACK_SVG} Back to chat</a>'
    '</div>'
)


def create_admin_ui(rag_system, doc_manager):

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_state_choices():
        all_states = ["All States"] + DEFAULT_STATE_CHOICES
        all_states += [s for s in doc_manager.get_states() if s not in all_states]
        return all_states

    # ── Render: stats ─────────────────────────────────────────────────────────

    def render_stats():
        summary  = doc_manager.get_namespace_summary()
        statuses = doc_manager.get_indexing_status()
        total    = sum(summary.values()) if summary else 0

        display_states = []
        for s in DEFAULT_STATE_CHOICES:
            cnt = summary.get(s, 0)
            if cnt > 0 or s in ("NSW", "QLD", "VIC"):
                display_states.append((s, cnt))
        for s, cnt in summary.items():
            if s not in DEFAULT_STATE_CHOICES:
                display_states.append((s, cnt))

        cards = (
            '<div class="stat-card">'
            '<div class="sc-label" style="color:#aaa">Total indexed</div>'
            f'<div class="sc-count" style="color:#fff">{total:,}</div>'
            '</div>'
        )
        for state, count in display_states[:5]:
            color = STATE_COLORS.get(state, "#888")
            cards += (
                '<div class="stat-card">'
                f'<div class="sc-label">'
                f'<span class="sc-dot" style="background:{color}"></span>'
                f'<span style="color:#888">{state}</span>'
                f'</div>'
                f'<div class="sc-count" style="color:{color}">{count:,}</div>'
                '</div>'
            )

        # Indexing progress banners
        banners = ""
        if statuses:
            for st in statuses:
                op    = st.get("operation", "indexing").capitalize()
                ns    = st.get("namespace") or "—"
                fname = st.get("filename") or ""
                done  = st.get("done", 0)
                ttl   = st.get("total", 0)
                pct   = int(st.get("progress", 0) * 100)
                banners += (
                    f'<div style="margin-bottom:12px;padding:10px 14px;background:#1a2a1a;'
                    f'border:1px solid #2a4a2a;border-radius:8px;font-size:12px;color:#7ec87e;'
                    f'display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
                    f'⏳ {op} &nbsp;·&nbsp; <strong>[{ns}]</strong> {fname}'
                    f'<span style="margin-left:auto;font-weight:600">{done}/{ttl} &nbsp; {pct}%</span>'
                    f'<div style="width:100%;height:3px;background:#1e3a1e;border-radius:2px;margin-top:4px">'
                    f'<div style="width:{pct}%;height:100%;background:#10a37f;border-radius:2px"></div>'
                    f'</div></div>'
                )

        stats_block = (
            '<div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;'
            'padding:16px 20px;margin-bottom:16px">'
            '<div style="font-size:11px;font-weight:600;color:#aaa;text-transform:uppercase;'
            'letter-spacing:.06em;margin-bottom:12px">Indexed documents</div>'
            f'<div class="stat-cards-row">{cards}</div>'
            '</div>'
        )
        return banners + stats_block

    # ── Render: file table ────────────────────────────────────────────────────

    def render_file_table(state_filter="All", search_query="", page=0):
        files = doc_manager.get_files_structured()

        if state_filter and state_filter.lower() not in ("all", "all states"):
            files = [f for f in files if f["state"] == state_filter]
        if search_query and search_query.strip():
            q = search_query.strip().lower()
            files = [f for f in files if q in f["filename"].lower() or q in f["state"].lower()]

        total       = len(files)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page        = max(0, min(page, total_pages - 1))
        page_files  = files[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

        if not total:
            return (
                '<div style="padding:32px 20px;color:#bbb;text-align:center;font-size:13px">'
                'No documents found.</div>'
            )

        start = page * PAGE_SIZE + 1
        end   = min(start + PAGE_SIZE - 1, total)

        rows = ""
        for f in page_files:
            safe    = f["filename"].replace('"', "")
            badge   = _pill(f["state"])
            date    = f.get("date", "")
            rows += (
                f'<tr>'
                f'<td class="col-cb"><input type="checkbox"></td>'
                f'<td class="col-st">{badge}</td>'
                f'<td><div class="fn-cell" title="{safe}">{safe}</div></td>'
                f'<td class="col-dt">{date}</td>'
                f'<td class="col-ac">'
                f'<a href="/download/{quote(safe)}" download="{safe}" class="row-dl">↓ Download</a>'
                f'</td>'
                f'</tr>'
            )

        pager_info = f'Showing {start}–{end} of {total:,} documents'

        return (
            '<div class="section-card">'
            '<div class="section-head">'
            '<span class="section-head-title">Indexed files</span>'
            f'<span class="section-head-sub">{total:,} total</span>'
            '</div>'
            '<table class="adm-table">'
            '<thead><tr>'
            '<th class="col-cb"><input type="checkbox" id="adm-check-all"></th>'
            '<th class="col-st">State</th>'
            '<th>Filename</th>'
            '<th class="col-dt">Date</th>'
            '<th class="col-ac"></th>'
            '</tr></thead>'
            f'<tbody>{rows}</tbody>'
            '</table>'
            f'<div id="adm-pagination"><span class="pager-info">{pager_info}</span></div>'
            '</div>'
        )

    # ── Other handlers ────────────────────────────────────────────────────────

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
        if state_filter and state_filter.lower() not in ("all", "all states"):
            files = [f for f in files if f["state"] == state_filter]
        if search_query and search_query.strip():
            q = search_query.strip().lower()
            files = [f for f in files if q in f["filename"].lower() or q in f["state"].lower()]
        total_pages = max(1, (len(files) + PAGE_SIZE - 1) // PAGE_SIZE)
        return f"Page {page + 1} of {total_pages}"

    # ── Build UI ──────────────────────────────────────────────────────────────

    with gr.Blocks(title="Admin — Case Agent") as demo:

        gr.HTML(_HEADER_HTML)

        # Stats (refreshed by timer)
        stats_html = gr.HTML(render_stats())

        with gr.Tabs(elem_id="admin-tabs"):

            # ── Tab 1: Documents ──────────────────────────────────────────────
            with gr.TabItem("Documents"):

                # Filter toolbar
                with gr.Row(elem_id="filter-toolbar"):
                    file_search = gr.Textbox(
                        placeholder="Search by filename…",
                        show_label=False, scale=3,
                        container=False, elem_id="adm-search",
                    )
                    state_filter_dd = gr.Dropdown(
                        choices=["All"] + DEFAULT_STATE_CHOICES,
                        value="All",
                        show_label=False, scale=1,
                        container=False, elem_id="state-filter-dd",
                    )
                    upload_toggle_btn = gr.Button(
                        "+ Upload", scale=0, min_width=100, elem_id="upload-toggle-btn",
                    )

                # Upload panel (hidden by default)
                upload_panel_open = gr.State(False)
                with gr.Column(visible=False, elem_id="upload-panel") as upload_panel:
                    gr.HTML(
                        '<div style="display:flex;align-items:baseline;gap:8px;'
                        'padding-bottom:14px;margin-bottom:16px;border-bottom:1px solid #1e1e1e">'
                        '<span style="font-size:14px;font-weight:600;color:#e8e8e8">Upload documents</span>'
                        '<span style="font-size:12px;color:#555">PDF only · max 50 MB per file</span>'
                        '</div>'
                    )
                    with gr.Row(equal_height=False):
                        with gr.Column(scale=1):
                            gr.HTML('<div class="upload-panel-label">Namespace / State</div>')
                            state_dropdown = gr.Dropdown(
                                choices=get_state_choices(),
                                value="All States",
                                allow_custom_value=True,
                                interactive=True,
                                show_label=False,
                                container=False,
                            )
                        with gr.Column(scale=1):
                            gr.HTML('<div class="upload-panel-label">Files</div>')
                            files_input = gr.File(
                                file_count="multiple", type="filepath",
                                height=130, show_label=False,
                            )
                    with gr.Row():
                        add_btn = gr.Button(
                            "Upload documents", variant="primary",
                            scale=0, elem_id="add-docs-btn",
                        )

                # File table
                file_table = gr.HTML(render_file_table())
                file_page  = gr.State(0)

                # Pagination
                with gr.Row(elem_id="pagination-row"):
                    prev_btn  = gr.Button("← Prev", size="sm", scale=0, min_width=88)
                    page_info = gr.Markdown("Page 1", elem_id="page-info")
                    next_btn  = gr.Button("Next →", size="sm", scale=0, min_width=88)

                # Danger zone
                with gr.Accordion("⚠  Danger Zone", open=False, elem_id="danger-zone-accordion"):
                    reindex_btn    = gr.Button("🔄 Re-index All Documents", elem_id="reindex-btn")
                    reindex_status = gr.Markdown("", elem_id="reindex-status")

                with gr.Column(visible=False) as confirm_reindex_panel:
                    gr.HTML("""
                    <div style="background:#1a1a0a;border:1px solid #7a6a00;border-radius:10px;
                                padding:16px;margin-top:12px">
                        <div style="color:#ffd700;font-size:14px;font-weight:600;margin-bottom:6px">
                            ⚠️ Re-index All Documents</div>
                        <div style="color:#ccc;font-size:13px;line-height:1.6">
                            This will <strong style="color:#fff">clear all vectors and parent chunks</strong>
                            then rebuild from scratch.<br>
                            Original PDFs are preserved.
                            <span style="color:#ffcc00">May take a long time.</span>
                        </div>
                    </div>""")
                    confirm_reindex_input = gr.Textbox(
                        placeholder="Type  REINDEX  to confirm",
                        show_label=False, elem_id="confirm-reindex-input", max_lines=1,
                    )
                    with gr.Row():
                        confirm_reindex_btn = gr.Button(
                            "Confirm Re-index", variant="stop", scale=1,
                            elem_id="confirm-reindex-confirm-btn",
                        )
                        cancel_reindex_btn = gr.Button("Cancel", scale=1)

                    gr.HTML(
                        '<div style="margin-top:14px;margin-bottom:6px;font-size:11px;color:#888;'
                        'text-transform:uppercase;letter-spacing:.04em;font-weight:600">'
                        'Delete by State</div>'
                    )
                    with gr.Row():
                        del_state_dropdown = gr.Dropdown(
                            choices=get_state_choices(), value=None,
                            label="Select state to delete", scale=3, elem_id="del-state-dropdown",
                        )
                        del_state_btn = gr.Button(
                            "🗑 Delete State", variant="stop", scale=1, elem_id="del-state-btn",
                        )
                    del_state_status = gr.Markdown("")

                    clear_docs_btn = gr.Button("🗑 Clear All Documents", elem_id="clear-all-btn")

                with gr.Column(visible=False) as confirm_del_state_panel:
                    confirm_del_state_html  = gr.HTML("")
                    confirm_del_state_input = gr.Textbox(
                        placeholder="Type  DELETE  to confirm", show_label=False, max_lines=1,
                    )
                    with gr.Row():
                        confirm_del_state_btn = gr.Button(
                            "Confirm Delete", variant="stop", scale=1,
                            elem_id="confirm-del-state-confirm-btn",
                        )
                        cancel_del_state_btn = gr.Button("Cancel", scale=1)

                with gr.Column(visible=False) as confirm_panel:
                    gr.HTML("""
                    <div style="background:#2a0a0a;border:1px solid #8b2020;border-radius:10px;
                                padding:16px;margin-top:12px">
                        <div style="color:#ff6b6b;font-size:14px;font-weight:600;margin-bottom:6px">
                            ⚠️ Delete All Documents</div>
                        <div style="color:#ccc;font-size:13px;line-height:1.6">
                            Permanently deletes <strong style="color:#fff">all uploaded documents</strong>,
                            all vectors and chunks.<br>
                            <span style="color:#ff9999">This action cannot be undone.</span>
                        </div>
                    </div>""")
                    confirm_input = gr.Textbox(
                        placeholder="Type  DELETE  to confirm",
                        show_label=False, elem_id="confirm-delete-input", max_lines=1,
                    )
                    with gr.Row():
                        confirm_delete_btn = gr.Button(
                            "Confirm Delete", variant="stop", scale=1,
                            elem_id="confirm-delete-confirm-btn",
                        )
                        cancel_delete_btn = gr.Button("Cancel", scale=1)

            # ── Tab 2: AI Settings ────────────────────────────────────────────
            with gr.TabItem("AI settings"):

                gr.HTML(
                    '<div class="section-card"><div class="section-head">'
                    '<span class="section-head-title">Model &amp; retrieval</span>'
                    '</div><div class="section-body">'
                )
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
                gr.HTML('</div></div>')

                gr.HTML(
                    '<div class="section-card"><div class="section-head">'
                    '<span class="section-head-title">Prompts</span>'
                    '</div><div class="section-body">'
                )
                gr.HTML('<div class="ai-field-label">Orchestrator Prompt</div>')
                ai_orchestrator_prompt = gr.Textbox(
                    value=get_orchestrator_prompt(), lines=14, max_lines=40,
                    placeholder="Leave empty for default…", show_label=False,
                )
                gr.HTML('<div class="ai-field-label">Aggregation Prompt</div>')
                ai_aggregation_prompt = gr.Textbox(
                    value=get_aggregation_prompt(), lines=10, max_lines=30,
                    placeholder="Leave empty for default…", show_label=False,
                )
                gr.HTML('<div class="ai-field-label">Fallback Response Prompt</div>')
                ai_fallback_prompt = gr.Textbox(
                    value=get_fallback_response_prompt(), lines=8, max_lines=20,
                    placeholder="Leave empty for default…", show_label=False,
                )
                ai_settings_status = gr.Markdown("", elem_id="ai-settings-status")
                with gr.Row():
                    ai_save_btn  = gr.Button("Save Settings", variant="primary", scale=2, elem_id="ai-save-btn")
                    ai_reset_btn = gr.Button("↺ Reset to Defaults", scale=1)
                gr.HTML('</div></div>')

            # ── Tab 3: Upload log ─────────────────────────────────────────────
            with gr.TabItem("Upload log"):
                gr.HTML(
                    '<div style="padding:40px 20px;color:#bbb;font-size:13px;text-align:center">'
                    'Upload log coming soon.</div>'
                )

        # ── Footer ───────────────────────────────────────────────────────────
        gr.HTML(
            '<div style="text-align:center;font-size:11px;color:#bbb;padding:16px 0 4px">'
            'Case Agent Admin</div>'
        )

        # ── Timer ─────────────────────────────────────────────────────────────
        admin_timer = gr.Timer(value=4.0, active=True)

        # ── Event wiring ──────────────────────────────────────────────────────

        def toggle_upload(is_open):
            new_state = not is_open
            return gr.update(visible=new_state), new_state

        upload_toggle_btn.click(
            toggle_upload, [upload_panel_open], [upload_panel, upload_panel_open],
        )

        add_btn.click(
            upload_handler,
            [files_input, state_dropdown],
            [files_input, file_table, state_dropdown],
            show_progress="corner",
            concurrency_limit=None,
        ).then(render_stats, None, stats_html)

        def reset_page(search, state_filter):
            sf = state_filter if state_filter else "All"
            return render_file_table(sf, search, 0), 0, _page_info(0, sf, search)

        file_search.change(reset_page, [file_search, state_filter_dd], [file_table, file_page, page_info])
        state_filter_dd.change(reset_page, [file_search, state_filter_dd], [file_table, file_page, page_info])

        def go_prev(page, search, state_filter):
            sf    = state_filter if state_filter else "All"
            new_p = max(0, page - 1)
            return render_file_table(sf, search, new_p), new_p, _page_info(new_p, sf, search)

        def go_next(page, search, state_filter):
            sf    = state_filter if state_filter else "All"
            files = doc_manager.get_files_structured()
            if sf.lower() not in ("all", "all states"):
                files = [f for f in files if f["state"] == sf]
            total_p = max(1, (len(files) + PAGE_SIZE - 1) // PAGE_SIZE)
            new_p   = min(total_p - 1, page + 1)
            return render_file_table(sf, search, new_p), new_p, _page_info(new_p, sf, search)

        prev_btn.click(go_prev, [file_page, file_search, state_filter_dd], [file_table, file_page, page_info])
        next_btn.click(go_next, [file_page, file_search, state_filter_dd], [file_table, file_page, page_info])

        def del_state_click(state):
            if not state or state.lower() in ("all states", "all", ""):
                gr.Warning("Please select a specific state.")
                return gr.update(visible=False), gr.update(), ""
            warn = (
                f'<div style="background:#2a0a0a;border:1px solid #8b2020;'
                f'border-radius:10px;padding:14px;margin-top:8px">'
                f'<div style="color:#ff6b6b;font-size:14px;font-weight:600;margin-bottom:4px">'
                f'⚠️ Delete {state}</div>'
                f'<div style="color:#ccc;font-size:13px">All {state} documents, '
                f'vectors and chunks will be permanently deleted.</div>'
                f'</div>'
            )
            return gr.update(visible=True), gr.update(value=warn), ""

        del_state_btn.click(
            del_state_click, [del_state_dropdown],
            [confirm_del_state_panel, confirm_del_state_html, confirm_del_state_input],
        )
        cancel_del_state_btn.click(
            lambda: (gr.update(visible=False), ""), None,
            [confirm_del_state_panel, confirm_del_state_input],
        )

        def confirm_del_state_handler(state, confirm_text):
            if confirm_text.strip() != "DELETE":
                gr.Warning("Type  DELETE  (all caps) to confirm.")
                return gr.update(), gr.update(choices=get_state_choices()), gr.update(visible=True), "", ""
            if not state or state.lower() in ("all states", "all", ""):
                gr.Warning("No state selected.")
                return gr.update(), gr.update(choices=get_state_choices()), gr.update(visible=False), "", ""
            summary = doc_manager.delete_namespace(state)
            msg = (
                f"✅ Deleted **{state}**: {summary['original_files']} files, "
                f"{summary['parent_chunks']} chunks, {summary['vectors']} vectors."
            )
            gr.Info(f"State '{state}' deleted.")
            return (
                render_file_table(),
                gr.update(choices=get_state_choices(), value=None),
                gr.update(visible=False), "", msg,
            )

        confirm_del_state_btn.click(
            confirm_del_state_handler,
            [del_state_dropdown, confirm_del_state_input],
            [file_table, del_state_dropdown, confirm_del_state_panel, confirm_del_state_input, del_state_status],
        )

        clear_docs_btn.click(lambda: gr.update(visible=True), None, confirm_panel)
        cancel_delete_btn.click(
            lambda: (gr.update(visible=False), ""), None, [confirm_panel, confirm_input],
        )

        def clear_handler_full(confirm_text):
            if confirm_text.strip() != "DELETE":
                gr.Warning("Type  DELETE  (all caps) to confirm.")
                return gr.update(), gr.update(choices=get_state_choices()), gr.update(visible=True), ""
            doc_manager.clear_all()
            gr.Info("All documents and vectors removed.")
            return render_file_table(), gr.update(choices=get_state_choices()), gr.update(visible=False), ""

        confirm_delete_btn.click(
            clear_handler_full, [confirm_input],
            [file_table, state_dropdown, confirm_panel, confirm_input],
        )

        reindex_btn.click(lambda: gr.update(visible=True), None, confirm_reindex_panel)
        cancel_reindex_btn.click(
            lambda: (gr.update(visible=False), ""), None,
            [confirm_reindex_panel, confirm_reindex_input],
        )

        def reindex_handler(confirm_text, progress=gr.Progress()):
            if confirm_text.strip() != "REINDEX":
                gr.Warning("Type  REINDEX  (all caps) to confirm.")
                return "", gr.update(), gr.update(visible=True), ""
            total_md = len(list(doc_manager.markdown_dir.rglob("*.md")))
            if total_md == 0:
                return "⚠️ No documents to re-index.", gr.update(), gr.update(visible=False), ""
            indexed = doc_manager.reindex_all(progress_callback=progress)
            return f"✅ Re-indexed {indexed} of {total_md} documents.", render_file_table(), gr.update(visible=False), ""

        confirm_reindex_btn.click(
            reindex_handler,
            [confirm_reindex_input],
            [reindex_status, file_table, confirm_reindex_panel, confirm_reindex_input],
        ).then(render_stats, None, stats_html)

        admin_timer.tick(render_stats, None, stats_html, show_progress=False)

        def save_ai_settings(temperature, max_tool_calls, orch, agg, fallback):
            admin_config.save({
                "temperature": temperature,
                "max_tool_calls": int(max_tool_calls),
                "orchestrator_prompt": orch.strip(),
                "aggregation_prompt": agg.strip(),
                "fallback_response_prompt": fallback.strip(),
            })
            rag_system.apply_settings()
            ts = admin_config.get_all().get("last_updated", "")
            return f"✅ Settings saved at {ts[:19].replace('T', ' ')} UTC"

        def reset_ai_settings():
            admin_config.reset()
            rag_system.apply_settings()
            return (
                config.LLM_TEMPERATURE, config.MAX_TOOL_CALLS,
                get_orchestrator_prompt(), get_aggregation_prompt(),
                get_fallback_response_prompt(), "↺ Reset to defaults.",
            )

        ai_save_btn.click(
            save_ai_settings,
            [ai_temperature, ai_max_tools, ai_orchestrator_prompt, ai_aggregation_prompt, ai_fallback_prompt],
            [ai_settings_status],
        )
        ai_reset_btn.click(
            reset_ai_settings, None,
            [ai_temperature, ai_max_tools, ai_orchestrator_prompt, ai_aggregation_prompt, ai_fallback_prompt, ai_settings_status],
        )

    demo._rag_system  = rag_system
    demo._doc_manager = doc_manager
    return demo
