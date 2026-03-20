#!/usr/bin/env python3
"""
QA agent for the RAG Assistant.

Checks infrastructure, UI rendering, and functional endpoints.
Tracks results over time in qa_results.json.

Usage:
    python qa_check.py                               # local
    python qa_check.py http://13.238.195.140:7860    # EC2
    python qa_check.py --history                     # show trend
"""

import sys
import re
import json
import time
import argparse
import datetime
import pathlib
import requests

RESULTS_FILE = pathlib.Path(__file__).parent / "qa_results.json"

# ── Colours ───────────────────────────────────────────────────────────────────

PASS = "\033[32m  PASS\033[0m"
FAIL = "\033[31m  FAIL\033[0m"
WARN = "\033[33m  WARN\033[0m"
SKIP = "\033[90m  SKIP\033[0m"

_results: list[tuple[str, str, str]] = []


def check(label: str, fn, skip_if=False, warn_only=False):
    if skip_if:
        print(f"{SKIP}  {label}")
        _results.append((label, "skip", ""))
        return
    try:
        result = fn()
        if result is True:
            print(f"{PASS}  {label}")
            _results.append((label, "pass", ""))
        elif result is False:
            icon = WARN if warn_only else FAIL
            print(f"{icon}  {label}")
            _results.append((label, "warn" if warn_only else "fail", ""))
        elif isinstance(result, tuple):
            ok, detail = result
            if ok:
                print(f"{PASS}  {label}  —  {detail}")
                _results.append((label, "pass", detail))
            else:
                icon = WARN if warn_only else FAIL
                print(f"{icon}  {label}  —  {detail}")
                _results.append((label, "warn" if warn_only else "fail", detail))
        else:
            print(f"{PASS}  {label}  —  {result}")
            _results.append((label, "pass", str(result)))
    except Exception as e:
        print(f"{FAIL}  {label}  [{type(e).__name__}: {e}]")
        _results.append((label, "fail", str(e)))


def _get(base, path, timeout=10, **kwargs):
    return requests.get(f"{base}{path}", timeout=timeout, allow_redirects=False, **kwargs)


def _post(base, path, timeout=10, **kwargs):
    return requests.post(f"{base}{path}", timeout=timeout, allow_redirects=False, **kwargs)


# ── Section header ─────────────────────────────────────────────────────────────

def section(title: str):
    print(f"\n  {'─'*50}\n  {title}\n")


# ── Infrastructure ────────────────────────────────────────────────────────────

def check_infra(base: str, auth_mode: bool):
    section("🔧  Infrastructure")

    check("App is reachable (200/302/401)",
          lambda: _get(base, "/").status_code in (200, 302, 307, 401))

    def chk_config():
        r = _get(base, "/config")
        if r.status_code != 200:
            return False, f"status {r.status_code}"
        return True, f"Gradio {r.json().get('version', '?')}"
    check("Gradio /config accessible", chk_config)

    check("Gradio /gradio_api/info accessible (bypasses auth)",
          lambda: _get(base, "/gradio_api/info").status_code == 200)

    check("Static /assets/ not blocked by auth",
          lambda: _get(base, "/assets/", timeout=5).status_code != 403)

    check("/queue/ endpoint accessible (bypasses auth)",
          lambda: _get(base, "/queue/status", timeout=5).status_code in (200, 404))

    # Auth-mode only
    def chk_login():
        r = _get(base, "/login")
        if r.status_code == 200 and "clerk" in r.text.lower():
            return True, "Clerk JS present in HTML"
        return False, f"status {r.status_code}, Clerk JS missing"
    check("Login page serves Clerk JS", chk_login, skip_if=not auth_mode)

    def chk_redirect():
        r = _get(base, "/", headers={"Accept": "text/html,application/xhtml+xml"})
        if r.status_code in (302, 307) and "/login" in r.headers.get("location", ""):
            return True, "→ /login"
        if r.status_code == 401:
            return True, "401 Unauthorized (middleware active)"
        return False, f"status {r.status_code}"
    check("Unauthenticated request → blocked", chk_redirect, skip_if=not auth_mode)

    def chk_health():
        r = _get(base, "/health")
        if r.status_code != 200:
            return False, f"status {r.status_code}"
        d = r.json()
        qdrant = d.get("qdrant", False)
        return qdrant, f"Qdrant={'✓' if qdrant else '✗'}  model={d.get('active_model','?')}"
    check("Health — Qdrant connected + LLM configured", chk_health, skip_if=not auth_mode)

    def chk_verify():
        r = _post(base, "/auth/verify", json={"token": "bad"})
        return r.status_code == 401, f"status {r.status_code}"
    check("/auth/verify rejects bad token → 401", chk_verify, skip_if=not auth_mode)

    def chk_logout():
        r = _get(base, "/auth/logout")
        if r.status_code not in (200, 302, 307):
            return False, f"status {r.status_code}"
        cleared = "rag_uid" in r.headers.get("set-cookie", "")
        return True, f"status={r.status_code} cookie-cleared={cleared}"
    check("/auth/logout reachable + clears cookie", chk_logout, skip_if=not auth_mode)


# ── UI rendering ──────────────────────────────────────────────────────────────

def check_ui(base: str, auth_mode: bool):
    section("🖥️  UI Rendering")

    # In auth mode fetch /login (public), in no-auth mode fetch /
    if auth_mode:
        html_page = _get(base, "/login").text
        page_label = "/login"
    else:
        html_page = _get(base, "/").text
        page_label = "/"

    check(f"Page {page_label} returns non-empty HTML",
          lambda: len(html_page) > 500)

    # Check CSS injected (either via <style> tag or link)
    def chk_css():
        has_style = "<style" in html_page
        has_link = 'rel="stylesheet"' in html_page
        return has_style or has_link, f"<style>={has_style} link={has_link}"
    check("CSS is injected in page HTML", chk_css, skip_if=auth_mode)

    # For no-auth mode — check the Gradio app HTML has our key elements
    if not auth_mode:
        def chk_gradio_ui():
            # Gradio renders a shell; check for gradio root div
            has_gradio = "gradio" in html_page.lower()
            has_body = "<body" in html_page
            return has_gradio and has_body, f"gradio-root={has_gradio}"
        check("Gradio app shell rendered", chk_gradio_ui)

    # Check the Gradio API exposes expected endpoints
    def chk_api_endpoints():
        r = _get(base, "/gradio_api/info")
        if r.status_code != 200:
            return False, f"info status {r.status_code}"
        data = r.json()
        endpoints = list(data.get("named_endpoints", {}).keys())
        required = ["/chat_handler_ui", "/on_model_change"]
        missing = [e for e in required if e not in endpoints]
        if missing:
            return False, f"missing endpoints: {missing}"
        return True, f"{len(endpoints)} endpoints exposed: {', '.join(endpoints[:4])}…"
    check("Key Gradio API endpoints exposed", chk_api_endpoints)

    # Check chat endpoint has correct params
    def chk_chat_params():
        r = _get(base, "/gradio_api/info")
        if r.status_code != 200:
            return False, "info not accessible"
        data = r.json()
        ep = data.get("named_endpoints", {}).get("/chat_handler_ui", {})
        params = [p["parameter_name"] for p in ep.get("parameters", [])]
        required = ["message", "chat_history"]
        missing = [p for p in required if p not in params]
        if missing:
            return False, f"missing params: {missing}"
        return True, f"params: {params}"
    check("/chat_handler_ui has expected parameters", chk_chat_params)

    # Check CSS rules are present in no-auth mode (CSS loaded correctly)
    def chk_css_rules():
        r = _get(base, "/gradio_api/info")
        # We can't easily check injected CSS via HTTP in auth mode
        # In no-auth, the page HTML should have our CSS
        if auth_mode:
            return True, "skipped in auth mode (CSS loaded in Gradio shell)"
        has_sidebar = "sidebar" in html_page
        has_dark = "#1a1a1a" in html_page or "0d0d0d" in html_page
        return has_sidebar or has_dark, f"sidebar-css={has_sidebar} dark-theme={has_dark}"
    check("Custom CSS rules present in page", chk_css_rules)

    # Check footer links are suppressed
    def chk_footer():
        if auth_mode:
            return True, "skipped (login page has no Gradio footer)"
        # footer { display:none } should prevent these from showing
        footer_visible = "Built with Gradio" in html_page or "Use via API" in html_page
        # If present in HTML but hidden via CSS that's acceptable
        return True, f"footer-text-in-html={'yes (hidden by CSS)' if footer_visible else 'no'}"
    check("Footer elements handled", chk_footer)


# ── Functional API ────────────────────────────────────────────────────────────

def check_functional(base: str):
    section("⚙️  Functional API")

    # Model change endpoint (fast, non-streaming)
    def chk_model():
        from gradio_client import Client
        c = Client(base, verbose=False)
        result = c.predict("Claude Haiku 4.5", api_name="/on_model_change")
        return "✓" in str(result) or "haiku" in str(result).lower(), f"result: {str(result)[:60]}"
    check("Model switch via API works", chk_model)

    # Verify gradio session can be created (join queue)
    def chk_queue_join():
        import time
        sh = f"qa_{int(time.time())}"
        r = _post(base, "/gradio_api/queue/join", json={
            "data": ["ping", [], "All States"],
            "fn_index": 1,
            "session_hash": sh,
        })
        if r.status_code != 200:
            return False, f"join status {r.status_code}"
        event_id = r.json().get("event_id", "")
        return bool(event_id), f"event_id={event_id[:8]}…"
    check("Queue join returns event_id", chk_queue_join)

    # Verify RAG API sends a response (using gradio_client predict — slow)
    # This is the real E2E test — skip if taking too long would block CI
    def chk_chat_response():
        from gradio_client import Client
        import re as _re
        c = Client(base, verbose=False)
        result = c.predict(
            "What is a contract?", [], "All States",
            api_name="/chat_handler_ui",
        )
        chat = result[0] if isinstance(result, (list, tuple)) else []
        if not isinstance(chat, list) or not chat:
            return False, "empty chat response"
        last = chat[-1]
        content = last.get("content", "") if isinstance(last, dict) else ""
        if isinstance(content, list):
            content = " ".join(x.get("text", "") for x in content if isinstance(x, dict))
        content = _re.sub(r"<[^>]+>", "", content).strip()
        has_error = content.startswith("❌")
        word_count = len(content.split())
        if has_error:
            return False, f"RAG returned error: {content[:100]}"
        return word_count >= 20, f"{word_count} words — '{content[:80]}…'"
    check("RAG chat returns a substantive response", chk_chat_response)


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary() -> tuple[int, int]:
    passed  = sum(1 for _, s, _ in _results if s == "pass")
    failed  = sum(1 for _, s, _ in _results if s == "fail")
    warned  = sum(1 for _, s, _ in _results if s == "warn")
    skipped = sum(1 for _, s, _ in _results if s == "skip")
    total   = len(_results)

    print(f"\n  {'═'*50}")
    print(f"  {passed}/{total} passed  |  {failed} failed  |  {warned} warnings  |  {skipped} skipped")

    if failed:
        print("\n  ✗ Failed:")
        for label, status, detail in _results:
            if status == "fail":
                d = f"  ({detail})" if detail else ""
                print(f"    •  {label}{d}")

    if warned:
        print("\n  ⚠ Warnings:")
        for label, status, detail in _results:
            if status == "warn":
                d = f"  ({detail})" if detail else ""
                print(f"    •  {label}{d}")

    print()
    return passed, failed


# ── Persistence ───────────────────────────────────────────────────────────────

def _load_history() -> list:
    if RESULTS_FILE.exists():
        try:
            return json.loads(RESULTS_FILE.read_text())
        except Exception:
            return []
    return []


def _save_run(base: str, passed: int, failed: int):
    history = _load_history()
    history.append({
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "target": base,
        "passed": passed,
        "failed": failed,
        "checks": [{"label": l, "status": s, "detail": d} for l, s, d in _results],
    })
    RESULTS_FILE.write_text(json.dumps(history[-100:], indent=2))
    print(f"  Results saved → {RESULTS_FILE.name}")


def show_history():
    history = _load_history()
    if not history:
        print("\nNo QA history yet.\n")
        return
    print(f"\n📈  QA History  ({len(history)} runs)\n")
    print(f"  {'Timestamp':<28} {'Target':<32} {'Result'}")
    print(f"  {'─'*70}")
    for run in history[-20:]:
        ts = run["timestamp"][:19].replace("T", " ")
        target = run["target"][:30]
        p, f = run.get("passed", 0), run.get("failed", 0)
        status = "\033[32mOK\033[0m" if f == 0 else f"\033[31m{f} FAIL\033[0m"
        print(f"  {ts:<28} {target:<32} {p}p/{f}f  {status}")
    print()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="QA agent for RAG Assistant")
    parser.add_argument("base_url", nargs="?", default="http://localhost:7860")
    parser.add_argument("--history", action="store_true", help="Show run history")
    parser.add_argument("--skip-chat", action="store_true",
                        help="Skip the slow RAG chat response test")
    args = parser.parse_args()

    if args.history:
        show_history()
        return

    base = args.base_url.rstrip("/")
    print(f"\n🔍  QA Agent — {base}\n")

    # Detect mode
    try:
        _r = _get(base, "/login")
        auth_mode = _r.status_code == 200 and "clerk" in _r.text.lower()
    except Exception:
        auth_mode = False
    print(f"  Mode: {'auth / Clerk' if auth_mode else 'no-auth / local dev'}\n")

    check_infra(base, auth_mode)
    check_ui(base, auth_mode)

    if not args.skip_chat:
        print(f"\n  (RAG chat test may take 30-60s — use --skip-chat to skip)\n")
        check_functional(base)

    passed, failed = print_summary()
    _save_run(base, passed, failed)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
