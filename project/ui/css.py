custom_css = """
/* ── Base ── */
footer { display: none !important; }
.gradio-container {
    max-width: 100vw !important;
    width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
}
.contain, .main, .wrap { max-width: 100% !important; }
body { background: #212121 !important; }

/* ── Root row: no gap ── */
#app-root { gap: 0 !important; min-height: 100vh; align-items: stretch; width: 100% !important; }

/* ── Sidebar ── */
#sidebar {
    background: #171717 !important;
    border-right: 1px solid #2a2a2a !important;
    padding: 12px 8px !important;
    min-height: 100vh !important;
}
#sidebar.sidebar-collapsed { display: none !important; }

.sidebar-header {
    color: #ececec;
    font-size: 16px;
    font-weight: 600;
    padding: 6px 10px 14px;
}
.sidebar-label {
    font-size: 11px;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding: 12px 10px 4px;
}
.sidebar-divider { border-top: 1px solid #2a2a2a; margin: 10px 4px; }

/* New chat button */
#new-chat-btn {
    background: transparent !important;
    border: 1px solid #333 !important;
    color: #ccc !important;
    width: 100% !important;
    text-align: left !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    font-size: 13px !important;
    margin-bottom: 4px !important;
}
#new-chat-btn:hover { background: #2a2a2a !important; color: #fff !important; }

/* Session HTML list */
#session-list {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    max-height: calc(100vh - 280px) !important;
    overflow-y: auto !important;
    scrollbar-width: thin !important;
    scrollbar-color: #333 transparent !important;
}
#session-list::-webkit-scrollbar { width: 4px; }
#session-list::-webkit-scrollbar-track { background: transparent; }
#session-list::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }
.session-empty { font-size: 12px; color: #444; padding: 8px 10px; }
.session-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 7px 10px;
    border-radius: 8px;
    font-size: 13px;
    color: #999;
    cursor: pointer;
    margin-bottom: 2px;
}
.session-item:hover { background: #232323; color: #ddd; }
.session-item.session-active { background: #2a2a2a; color: #ececec; }
.session-item-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-del-btn {
    visibility: hidden;
    background: transparent !important;
    border: none !important;
    color: #555 !important;
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

/* Admin / History sidebar buttons */
#admin-btn, #history-btn {
    background: transparent !important;
    border: none !important;
    color: #888 !important;
    width: 100% !important;
    text-align: left !important;
    justify-content: flex-start !important;
    border-radius: 8px !important;
    padding: 7px 10px !important;
    font-size: 13px !important;
}
#admin-btn:hover, #history-btn:hover { background: #252525 !important; color: #ddd !important; }

/* Health status */
#health-md { padding: 8px 10px 0 !important; font-size: 11px !important; color: #444 !important; }
#health-md p { color: #444 !important; font-size: 11px !important; margin: 0 !important; }

/* ── Main area ── */
#main-area { background: #212121 !important; padding: 0 24px !important; }

/* ── Top bar: toggle + state filter ── */
#main-topbar {
    align-items: center !important;
    gap: 8px !important;
    padding: 10px 0 6px !important;
    border-bottom: 1px solid #2a2a2a !important;
    margin-bottom: 8px !important;
    flex-wrap: nowrap !important;
}

/* Toggle sidebar button — small, left-anchored */
#toggle-sidebar-btn {
    background: transparent !important;
    border: none !important;
    color: #666 !important;
    font-size: 14px !important;
    padding: 2px 6px !important;
    cursor: pointer !important;
    border-radius: 5px !important;
    min-width: unset !important;
    width: 28px !important;
    max-width: 28px !important;
    height: 26px !important;
    min-height: unset !important;
    flex-shrink: 0 !important;
    line-height: 1 !important;
}
#toggle-sidebar-btn:hover { color: #ccc !important; background: #2a2a2a !important; }

/* ── Top-bar: strip ALL block backgrounds ── */
#main-topbar,
#main-topbar > *,
#main-topbar .block,
#main-topbar .form,
#main-topbar > div > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* State filter — one line: label then dropdown */
#state-filter {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 6px !important;
    flex-shrink: 0 !important;
    white-space: nowrap !important;
}
#state-filter label {
    font-size: 12px !important;
    color: #666 !important;
    white-space: nowrap !important;
    margin: 0 !important;
    padding: 0 !important;
    flex-shrink: 0 !important;
    line-height: 1 !important;
    display: inline !important;
}
#state-filter .wrap {
    flex-shrink: 0 !important;
    min-width: 130px !important;
    max-width: 160px !important;
}
#state-filter .wrap-inner {
    background: transparent !important;
    border: 1px solid #3a3a3a !important;
    border-radius: 6px !important;
    height: 26px !important;
    min-height: unset !important;
}
#state-filter input {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    font-size: 12px !important;
    padding: 0 6px !important;
    height: 24px !important;
    min-height: unset !important;
    color: #aaa !important;
}

/* ── Chatbot ── */
#chatbot { border: none !important; }

/* Hide top-right toolbar buttons (share / copy-all / delete) */
#chatbot .top-panel { display: none !important; }
#chatbot .share-button { display: none !important; }
#chatbot button[title="Share"],
#chatbot button[title="Delete"],
#chatbot button[title="Copy"],
#chatbot button[aria-label="Share"],
#chatbot button[aria-label="Delete"],
#chatbot button[aria-label="Clear"] { display: none !important; }

/* Message bubbles */
#chatbot .message { color: #ececec !important; font-size: 14px !important; line-height: 1.65 !important; }
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

/* Thinking indicator */
@keyframes thinking-dot { 0%, 80%, 100% { opacity: 0.2; } 40% { opacity: 1; } }
.thinking-dot { display: inline-block; animation: thinking-dot 1.4s infinite; }
.thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dot:nth-child(3) { animation-delay: 0.4s; }

/* ── Input row ── */
#input-row { align-items: flex-end !important; gap: 8px !important; margin-top: 4px !important; }
#user-input textarea {
    background: #2a2a2a !important;
    border: 1px solid #3a3a3a !important;
    border-radius: 12px !important;
    color: #ececec !important;
    font-size: 15px !important;
    padding: 10px 14px !important;
    resize: none !important;
    min-height: 52px !important;
    overflow-y: hidden !important;
    field-sizing: content !important;
}
#user-input textarea:focus { border-color: #555 !important; outline: none !important; }
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
    background: #2a2a2a !important;
    border: 1px solid #3a3a3a !important;
    border-radius: 8px !important;
    color: #ececec !important;
}
input:focus, textarea:focus { border-color: #555 !important; outline: none !important; }
textarea[readonly] { color: #888 !important; }

.wrap-inner, select {
    background: #2a2a2a !important;
    border: 1px solid #3a3a3a !important;
    border-radius: 8px !important;
    color: #ececec !important;
}
.file-preview, [data-testid="file-upload"] {
    background: #252525 !important;
    border: 1px dashed #3a3a3a !important;
    border-radius: 10px !important;
}
.file-preview *, [data-testid="file-upload"] * { color: #ccc !important; }

h1, h2, h3, h4, h5, h6, p, span, div { color: inherit; }
.progress-text { display: none !important; }
.progress-bar { background: #10a37f !important; }

/* ── Suggestion pills ── */
#sugg-row {
    flex-wrap: wrap !important; gap: 8px !important;
    margin: 6px 0 2px !important; padding: 0 !important;
}
.sugg-btn {
    background: #2a2a2a !important; border: 1px solid #3a3a3a !important;
    color: #ccc !important; border-radius: 20px !important;
    padding: 6px 16px !important; font-size: 13px !important;
    height: auto !important; min-width: unset !important;
    white-space: nowrap !important; flex: 0 1 auto !important;
}
.sugg-btn:hover { background: #333 !important; border-color: #555 !important; color: #fff !important; }

/* ── Cited source files ── */
#cited-files { margin-top: 6px !important; }
.cited-sources {
    padding: 8px 12px; background: #1a1a1a;
    border: 1px solid #2a2a2a; border-radius: 10px;
}
.cited-label {
    font-size: 11px; color: #555; text-transform: uppercase;
    letter-spacing: 0.6px; margin-bottom: 6px;
}
.cited-link {
    display: inline-block; background: #252525; color: #aaa !important;
    text-decoration: none !important; padding: 4px 10px;
    border-radius: 6px; font-size: 12px; margin: 2px 4px 2px 0; border: 1px solid #333;
}
.cited-link:hover { background: #2f2f2f !important; color: #fff !important; border-color: #555; }

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
"""
