custom_css = """
/* ── Base ── */
footer { display: none !important; }
html, body {
    height: 100vh !important;
    overflow: hidden !important;
    background: #1a1a1a !important;
}
.gradio-container {
    max-width: 100vw !important;
    width: 100vw !important;
    height: 100vh !important;
    padding: 0 !important;
    margin: 0 !important;
    overflow: hidden !important;
}
/* Strip ALL Gradio inner container padding/max-width down to #app-root */
.gradio-container > *,
.gradio-container > * > *,
.contain,
.main,
.app,
.fillable {
    max-width: 100% !important;
    width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
    box-sizing: border-box !important;
}

/* ── Root row: no gap, full height ── */
#app-root {
    gap: 0 !important;
    height: calc(100vh - 1px) !important;
    margin-top: 1px !important;
    overflow: hidden !important;
    align-items: stretch;
    width: 100% !important;
}

/* ── Sidebar ── */
#sidebar {
    background: #111111 !important;
    padding: 10px 8px !important;
    min-height: 100vh !important;
    height: 100vh !important;
    display: flex !important;
    flex-direction: column !important;
    transition: flex 0.2s ease, min-width 0.2s ease !important;
    overflow: hidden !important;
}
#sidebar.sidebar-collapsed {
    flex: 0 0 52px !important;
    min-width: 52px !important;
    width: 52px !important;
}
#sidebar.sidebar-collapsed #sidebar-body { display: none !important; }


/* Sidebar body wrapper — hides all content below the hamburger on collapse */
#sidebar-body {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 !important;
    gap: 0 !important;
    padding: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    min-height: 0 !important;
}
#sidebar-body > * { background: transparent !important; border: none !important; box-shadow: none !important; }

/* Spacer pushes admin/health/profile to bottom.
   gr.HTML wraps content in a .block div, so we target the block that contains the spacer. */
.sidebar-spacer { display: block; }
#sidebar-body > .block:has(.sidebar-spacer) {
    flex: 1 !important;
    min-height: 12px !important;
}

/* Toggle sidebar button — sits at top of sidebar */
#toggle-sidebar-btn {
    background: transparent !important;
    border: none !important;
    color: #555 !important;
    font-size: 16px !important;
    padding: 4px 8px !important;
    cursor: pointer !important;
    border-radius: 6px !important;
    min-width: unset !important;
    width: 36px !important;
    max-width: 36px !important;
    height: 32px !important;
    min-height: unset !important;
    margin-bottom: 6px !important;
    flex-shrink: 0 !important;
    line-height: 1 !important;
    align-self: flex-start !important;
}
#toggle-sidebar-btn:hover { color: #aaa !important; background: #1e1e1e !important; }

.sidebar-header {
    color: #ececec;
    font-size: 14px;
    font-weight: 700;
    padding: 4px 10px 12px;
    letter-spacing: -0.01em;
}
.sidebar-label {
    font-size: 11px;
    color: #444;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding: 12px 10px 4px;
}
.sidebar-divider { border-top: 1px solid #222; margin: 10px 4px; }

/* New chat button */
#new-chat-btn {
    background: #10a37f18 !important;
    border: 1px solid #10a37f33 !important;
    color: #10a37f !important;
    width: 100% !important;
    text-align: left !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    font-size: 13px !important;
    margin-bottom: 4px !important;
    font-weight: 500 !important;
}
#new-chat-btn:hover { background: #10a37f28 !important; border-color: #10a37f55 !important; color: #16c99a !important; }

/* Session HTML list */
#session-list {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    max-height: calc(100vh - 280px) !important;
    overflow-y: auto !important;
    scrollbar-width: thin !important;
    scrollbar-color: #2a2a2a transparent !important;
}
#session-list::-webkit-scrollbar { width: 4px; }
#session-list::-webkit-scrollbar-track { background: transparent; }
#session-list::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 4px; }
.session-empty { font-size: 12px; color: #444; padding: 8px 10px; }
.session-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 7px 10px;
    border-radius: 8px;
    font-size: 13px;
    color: #888;
    cursor: pointer;
    margin-bottom: 2px;
}
.session-item:hover { background: #1c1c1c; color: #ddd; }
.session-item.session-active { background: #1e1e1e; color: #ececec; border-left: 2px solid #10a37f; border-radius: 0 8px 8px 0; padding-left: 8px !important; }
.session-item-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-del-btn {
    visibility: hidden;
    background: transparent !important;
    border: none !important;
    color: #444 !important;
    font-size: 12px !important;
    padding: 2px 5px !important;
    border-radius: 4px !important;
    cursor: pointer !important;
    flex-shrink: 0 !important;
    line-height: 1 !important;
    margin-left: 4px !important;
}
.session-item:hover .session-del-btn { visibility: visible; }
.session-del-btn:hover { color: #e05252 !important; background: rgba(224,82,82,0.12) !important; }

/* CSS-hidden event textboxes (always in DOM) */
#session-click-txt, #session-del-txt {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

/* Admin link button in sidebar */
.admin-link-btn {
    display: block !important;
    background: transparent !important;
    border: none !important;
    color: #777 !important;
    width: 100% !important;
    text-align: left !important;
    border-radius: 8px !important;
    padding: 7px 10px !important;
    font-size: 13px !important;
    text-decoration: none !important;
    cursor: pointer !important;
    box-sizing: border-box !important;
}
.admin-link-btn:hover { background: #1c1c1c !important; color: #ddd !important; }

/* Health status */
#health-md { padding: 6px 10px 0 !important; font-size: 11px !important; }
#health-md p { font-size: 11px !important; margin: 0 !important; color: #484848 !important; }

/* ── Main area — full height flex column ── */
#main-area {
    background: #1a1a1a !important;
    padding: 0 0 !important;
    height: 100vh !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
    box-sizing: border-box !important;
}

/* ── Chat title (read-only, top of chat area) ── */
#chat-title {
    font-size: 13px;
    font-weight: 600;
    color: #aaa;
    padding: 10px 0 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
#chat-title-html { flex-shrink: 0 !important; }

/* ── Chat view — fills remaining height ── */
#chat-view {
    flex: 1 1 0 !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
    padding: 0 5px !important;
    box-sizing: border-box !important;
}

/* All direct children shrink to content by default */
#chat-view > * { flex-shrink: 0 !important; }

/* Chatbot grows to fill all available space */
#chatbot {
    flex: 1 1 0 !important;
    min-height: 0 !important;
    overflow: hidden !important;
    height: auto !important;
    max-height: 100% !important;
}

/* Gradio's internal chatbot wrapper — must fill the chatbot block */
#chatbot > div,
#chatbot .wrap {
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
}

/* The actual scrollable message list */
#chatbot .bubble-wrap {
    height: 100% !important;
    max-height: 100% !important;
    overflow-y: auto !important;
}

/* Input rows: never scroll away */
#input-row { flex-shrink: 0 !important; }
#input-meta-row { flex-shrink: 0 !important; }

/* ── Admin / History views — fill remaining height, scroll inside ── */

/* Gradio wraps each gr.Column in an outer .block div.
   display:contents makes those wrappers transparent to the flex layout,
   so #chat-view / #admin-view / #history-view participate as direct flex items.
   This means when #chat-view is display:none it truly takes no space. */
#main-area > *:has(> #chat-view),
#main-area > *:has(> #admin-view),
#main-area > *:has(> #history-view) {
    display: contents !important;
}

#admin-view, #history-view {
    flex: 1 1 0 !important;
    min-height: 0 !important;
    display: block !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    padding: 24px 24px !important;
    box-sizing: border-box !important;
    height: 100% !important;
    scrollbar-width: thin !important;
    scrollbar-color: #2a2a2a transparent !important;
}
#admin-view::-webkit-scrollbar { width: 4px; }
#admin-view::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 4px; }

/* Strip any Gradio inner wrappers from adding margin/padding */
#admin-view > *,
#history-view > * {
    margin-top: 0 !important;
}

/* Admin tab content area gets a card background */
#admin-view .tabitem {
    background: #141414 !important;
    border: 1px solid #1e1e1e !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
    padding: 16px !important;
}

/* Admin inputs */
#admin-view input,
#admin-view textarea,
#admin-view .wrap-inner {
    background: #1a1a1a !important;
    border-color: #2a2a2a !important;
}

/* Pagination row */
#pagination-row {
    margin-top: 8px !important;
    justify-content: center !important;
    gap: 12px !important;
}
#pagination-row button {
    background: transparent !important;
    border: 1px solid #2a2a2a !important;
    color: #666 !important;
    font-size: 12px !important;
    padding: 4px 12px !important;
    border-radius: 6px !important;
}
#pagination-row button:hover { border-color: #444 !important; color: #aaa !important; }
#page-info p { font-size: 12px !important; color: #555 !important; }

/* ── Shared dropdown style (model + state filter) ── */
#model-picker-inline,
#state-filter {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    flex-shrink: 0 !important;
}
#state-filter label { display: none !important; }
#model-picker-inline .wrap,
#state-filter .wrap {
    flex-shrink: 0 !important;
    min-width: 130px !important;
}
#model-picker-inline .wrap-inner,
#state-filter .wrap-inner {
    background: transparent !important;
    border: 1px solid #2e2e2e !important;
    border-radius: 6px !important;
    height: 28px !important;
    min-height: unset !important;
    padding: 0 8px !important;
    cursor: pointer !important;
}
#model-picker-inline .wrap-inner:hover,
#state-filter .wrap-inner:hover {
    border-color: #444 !important;
    background: #1a1a1a !important;
}
#model-picker-inline input,
#state-filter input {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    font-size: 12px !important;
    color: #999 !important;
    height: 26px !important;
    min-height: unset !important;
    padding: 0 !important;
    cursor: pointer !important;
}
#model-picker-inline svg,
#state-filter svg { color: #555 !important; width: 12px !important; }

/* ── Chatbot ── */
#chatbot { border: none !important; background: transparent !important; }

/* Hide top-right toolbar buttons (share / copy-all / delete) */
#chatbot .top-panel { display: none !important; }
#chatbot .share-button { display: none !important; }
#chatbot button[title="Share"],
#chatbot button[title="Delete"],
#chatbot button[aria-label="Share"],
#chatbot button[aria-label="Delete"],
#chatbot button[aria-label="Clear"] { display: none !important; }

/* Message bubbles */
#chatbot .message { color: #ececec !important; font-size: 14px !important; line-height: 1.7 !important; }
#chatbot .message p  { color: #ececec !important; margin: 0 0 8px !important; }
#chatbot .message h1, #chatbot .message h2, #chatbot .message h3 {
    color: #fff !important; font-weight: 600 !important; margin: 12px 0 6px !important;
}
#chatbot .message strong, #chatbot .message b {
    color: #ffffff !important; font-weight: 700 !important;
    background: rgba(255,255,255,0.06) !important;
    border-radius: 3px !important; padding: 0 2px !important;
}
#chatbot .message em { color: #d0d0d0 !important; }
#chatbot .message code {
    background: #1e3a2f !important; color: #4eca8b !important;
    padding: 1px 6px !important; border-radius: 4px !important;
    font-size: 13px !important; font-family: ui-monospace, monospace !important;
    border: 1px solid #2a5040 !important;
}
#chatbot .message pre {
    background: #1e1e1e !important; border: 1px solid #333 !important;
    border-radius: 8px !important; padding: 12px !important; overflow-x: auto !important;
}
#chatbot .message ul, #chatbot .message ol { padding-left: 20px !important; margin: 6px 0 !important; }
#chatbot .message li { color: #ececec !important; margin: 3px 0 !important; }
#chatbot .message blockquote {
    border-left: 3px solid #10a37f !important; padding-left: 12px !important;
    color: #aaa !important; margin: 8px 0 !important;
}
#chatbot .message mark {
    background: #3a3500 !important; color: #ffd700 !important;
    padding: 1px 3px !important; border-radius: 3px !important;
}

/* Thinking indicator — JS-driven random word cycler */
@keyframes thinking-dot { 0%, 80%, 100% { opacity: 0.2; } 40% { opacity: 1; } }

.thinking-container { display: inline-flex; align-items: baseline; gap: 0; }
.thinking-word-display {
    display: inline-block;
    min-width: 90px;
    color: #aaa;
    opacity: 1;
    transform: translateY(0);
}
.thinking-dot { display: inline-block; animation: thinking-dot 1.4s infinite; color: #555; }
.thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dot:nth-child(3) { animation-delay: 0.4s; }

/* ── Input row ── */
#input-row {
    align-items: flex-end !important;
    gap: 8px !important;
    margin-top: 4px !important;
    background: #161616 !important;
    border: 1px solid #232323 !important;
    border-radius: 14px !important;
    padding: 8px 8px 6px !important;
}

/* ── Input meta row: dropdowns + disclaimer ── */
#input-meta-row {
    align-items: center !important;
    gap: 8px !important;
    padding: 4px 2px 2px !important;
    flex-wrap: nowrap !important;
}
#input-meta-row > *,
#input-meta-row .block,
#input-meta-row .form {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
#input-disclaimer {
    text-align: center !important;
    font-size: 11px !important;
    color: #444 !important;
    padding: 8px 0 4px !important;
    width: 100% !important;
}

#user-input textarea {
    background: transparent !important;
    border: none !important;
    border-radius: 8px !important;
    color: #ececec !important;
    font-size: 14px !important;
    padding: 6px 10px !important;
    resize: none !important;
    min-height: 44px !important;
    overflow-y: hidden !important;
    field-sizing: content !important;
    box-shadow: none !important;
}
#user-input textarea:focus { border-color: transparent !important; outline: none !important; box-shadow: none !important; }
#user-input label { font-size: 0 !important; }

/* ── Send / Stop buttons — perfect circles with unicode icons ── */
#send-btn, #stop-btn {
    flex: 0 0 44px !important;
    width: 44px !important;
    max-width: 44px !important;
    min-width: 44px !important;
    height: 44px !important;
    min-height: 44px !important;
    max-height: 44px !important;
    padding: 0 !important;
    align-self: flex-end !important;
    margin-bottom: 3px !important;
}
#send-btn button, #stop-btn button,
#send-btn > button, #stop-btn > button {
    border-radius: 50% !important;
    width: 44px !important;
    height: 44px !important;
    min-width: 44px !important;
    min-height: 44px !important;
    padding: 0 !important;
    font-size: 18px !important;
    line-height: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
#send-btn button, #send-btn > button {
    background-color: #10a37f !important;
    color: #fff !important;
}
#send-btn button:hover, #send-btn > button:hover { background-color: #0e906f !important; }
#stop-btn button, #stop-btn > button {
    background-color: #c0392b !important;
    color: #fff !important;
}

/* ── View titles ── */
.view-title { font-size: 20px; font-weight: 600; color: #ececec; padding: 20px 0 12px; }

/* ── General ── */
button { border-radius: 8px !important; }

input, textarea {
    background: #222 !important;
    border: 1px solid #2e2e2e !important;
    border-radius: 8px !important;
    color: #ececec !important;
}
input:focus, textarea:focus { border-color: #444 !important; outline: none !important; }
textarea[readonly] { color: #666 !important; }

.wrap-inner, select {
    background: #222 !important;
    border: 1px solid #2e2e2e !important;
    border-radius: 8px !important;
    color: #ececec !important;
}
.file-preview, [data-testid="file-upload"] {
    background: #1e1e1e !important;
    border: 1px dashed #2e2e2e !important;
    border-radius: 10px !important;
}
.file-preview *, [data-testid="file-upload"] * { color: #aaa !important; }

h1, h2, h3, h4, h5, h6, p, span, div { color: inherit; }
.progress-text { display: none !important; }
.progress-bar { background: #10a37f !important; }

/* ── Suggestion pills ── */
#sugg-row {
    flex-wrap: wrap !important; gap: 8px !important;
    margin: 6px 0 2px !important; padding: 0 !important;
}
.sugg-btn {
    background: #1e1e1e !important; border: 1px solid #2a2a2a !important;
    color: #aaa !important; border-radius: 20px !important;
    padding: 6px 16px !important; font-size: 13px !important;
    height: auto !important; min-width: unset !important;
    white-space: nowrap !important; flex: 0 1 auto !important;
}
.sugg-btn:hover { background: #252525 !important; border-color: #3a3a3a !important; color: #fff !important; }

/* ── Re-index button ── */
#reindex-btn button {
    background-color: #1a3a2a !important;
    border-color: #2a5a3a !important;
    color: #5cb88a !important;
}
#reindex-btn button:hover {
    background-color: #1f4a34 !important;
    border-color: #3a7a50 !important;
}
#reindex-status p { font-size: 12px !important; color: #5cb88a !important; margin: 4px 0 !important; }

/* ── Agent activity panel ── */
#agent-activity { margin-bottom: 6px !important; }
.activity-panel {
    background: #161616;
    border-radius: 8px;
    overflow: hidden;
    font-size: 12px;
}
.activity-summary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 12px;
    color: #555;
    cursor: pointer;
    user-select: none;
    list-style: none;
}
.activity-summary::-webkit-details-marker { display: none; }
.activity-panel[open] .activity-summary { color: #777; border-bottom: 1px solid #1e1e1e; }
.activity-count {
    background: #222;
    color: #444;
    border-radius: 10px;
    padding: 1px 6px;
    font-size: 11px;
}
.activity-steps {
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    max-height: 115px;
    overflow-y: auto;
    scroll-behavior: smooth;
    scrollbar-width: thin;
    scrollbar-color: #2a2a2a transparent;
}
.activity-steps::-webkit-scrollbar { width: 3px; }
.activity-steps::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 3px; }
.activity-step { color: #888; font-size: 12px; line-height: 1.4; }
.activity-step-done { color: #444; }
.activity-step em { color: #10a37f; font-style: normal; }

/* ── Cited source files ── */
#cited-files { margin-top: 6px !important; }
.cited-sources {
    background: #161616; border-radius: 10px;
    overflow: hidden;
}
.cited-summary {
    font-size: 12px; color: #555; padding: 7px 12px;
    cursor: pointer; user-select: none; list-style: none;
    display: flex; align-items: center; gap: 6px;
}
.cited-summary::-webkit-details-marker { display: none; }
.cited-summary::before {
    content: '▶'; font-size: 9px; color: #444;
    transition: transform 0.15s;
}
.cited-sources[open] > .cited-summary::before { transform: rotate(90deg); }
.cited-summary:hover { color: #888; }
.cited-links {
    padding: 4px 12px 10px;
    border-top: 1px solid #1e1e1e;
}
.cited-link {
    display: inline-block; background: #1e1e1e; color: #888 !important;
    text-decoration: none !important; padding: 4px 10px;
    border-radius: 6px; font-size: 12px; margin: 2px 4px 2px 0;
}
.cited-link:hover { background: #252525 !important; color: #ddd !important; }

/* ── Admin tabs ── */
#admin-tabs > .tab-nav { border-bottom: 1px solid #2a2a2a !important; }
#admin-tabs .tab-nav button { color: #888 !important; font-size: 13px !important; }
#admin-tabs .tab-nav button.selected { color: #ececec !important; border-bottom-color: #10a37f !important; }
#ai-settings-status p { font-size: 12px !important; color: #10a37f !important; margin: 4px 0 !important; }

/* ── Danger zone accordion ── */
#danger-zone-accordion {
    margin-top: 16px !important;
    border: 1px solid #3a1a1a !important;
    border-radius: 8px !important;
    background: #1a1010 !important;
}
#danger-zone-accordion > .label-wrap span {
    color: #a04040 !important;
    font-size: 12px !important;
}

/* ── Clear All (danger) button ── */
#clear-all-btn button {
    background-color: #8b2020 !important;
    border-color: #a32828 !important;
    color: #fff !important;
}
#clear-all-btn button:hover {
    background-color: #a32828 !important;
    border-color: #c03030 !important;
}

/* ── Confirm delete panel ── */
#confirm-delete-input textarea {
    background: #1a0808 !important;
    border-color: #8b2020 !important;
    color: #ffcccc !important;
    font-size: 15px !important;
    text-align: center !important;
    letter-spacing: 2px !important;
}
#confirm-delete-confirm-btn button {
    background-color: #8b2020 !important;
    border-color: #a32828 !important;
    color: #fff !important;
}
#confirm-delete-confirm-btn button:hover {
    background-color: #c0392b !important;
}

/* ── Namespace status overview ── */
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
.ns-progress-bar {
    width: 100%; height: 3px; background: #1e3a1e; border-radius: 2px; margin-top: 4px;
}
.ns-progress-fill { height: 100%; background: #10a37f; border-radius: 2px; transition: width 0.4s; }
.ns-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.ns-pill {
    display: flex; align-items: center; gap: 6px;
    background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 20px;
    padding: 4px 10px; font-size: 12px;
}
.ns-pill-active { border-color: #2a4a2a; background: #1a2a1a; }
.ns-pill-name { color: #888; }
.ns-pill-count {
    background: #222; color: #555; border-radius: 10px;
    padding: 1px 7px; font-size: 11px;
}
.ns-pill-active .ns-pill-count { background: #1e3a1e; color: #7ec87e; }
.ns-empty { font-size: 12px; color: #444; padding: 4px 2px; }

/* ── Hide feedback/share buttons but keep copy ── */
#chatbot .extra-feedback,
#chatbot .extra-feedback-options { display: none !important; }

/* Style the copy button on each message */
#chatbot .options { display: flex !important; opacity: 0; transition: opacity 0.15s; }
#chatbot .message-wrap:hover .options { opacity: 1; }
#chatbot .option {
    background: transparent !important;
    border: none !important;
    color: #444 !important;
    padding: 2px 5px !important;
    font-size: 12px !important;
    cursor: pointer !important;
    border-radius: 4px !important;
}
#chatbot .option:hover { color: #aaa !important; background: #1e1e1e !important; }

/* ── User profile + logout ── */
#user-profile {
    padding: 0 !important;
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}
.user-profile-card {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 8px 8px 6px;
    border-top: 1px solid #1e1e1e;
    margin-top: 4px;
}
.user-avatar {
    width: 32px;
    height: 32px;
    min-width: 32px;
    border-radius: 50%;
    background: #2a2a2a;
    border: 1px solid #3a3a3a;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 600;
    color: #aaa;
    flex-shrink: 0;
}
.user-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
}
.user-name {
    font-size: 12px;
    color: #bbb;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: left;
}
.user-email-small {
    font-size: 10px;
    color: #484848;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: left;
}
.logout-btn {
    font-size: 11px;
    color: #484848;
    text-decoration: none !important;
    padding: 3px 7px;
    border: 1px solid #252525;
    border-radius: 4px;
    flex-shrink: 0;
    white-space: nowrap;
    transition: color 0.15s, border-color 0.15s;
}
.logout-btn:hover { color: #aaa !important; border-color: #444 !important; }

/* ── Eval button & panel ── */
#eval-btn { display: none !important; }
#eval-btn button {
    background: transparent !important;
    border: 1px solid #2a2a2a !important;
    color: #666 !important;
    font-size: 12px !important;
    padding: 4px 12px !important;
    border-radius: 6px !important;
    cursor: pointer !important;
    transition: border-color 0.15s, color 0.15s !important;
}
#eval-btn button:hover {
    border-color: #444 !important;
    color: #aaa !important;
}
#eval-panel {
    margin-top: 8px !important;
    padding: 14px 16px !important;
    background: #141414 !important;
    border-radius: 10px !important;
    border: 1px solid #242424 !important;
}
#eval-panel p, #eval-panel li { font-size: 13px !important; color: #aaa !important; line-height: 1.6 !important; }
#eval-panel h2 { font-size: 13px !important; color: #666 !important; text-transform: uppercase !important; letter-spacing: 0.5px !important; margin-bottom: 10px !important; font-weight: 600 !important; }
#eval-panel strong { color: #ccc !important; }
#eval-panel em { color: #777 !important; font-style: normal !important; }
#eval-panel hr { border-color: #222 !important; margin: 10px 0 !important; }
"""
