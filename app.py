"""
Flask application — the front desk.
Coordinates the scraper, session manager, and exporter.
Streams two-phase progress to the browser via Server-Sent Events.
"""

import json
import os
import threading
import time
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

from flask import Flask, Response, jsonify, render_template, request, send_file

from scraper.listing_scraper import analyze_listing, scrape_page
from scraper.detail_scraper  import analyze_detail, scrape_detail
from session.session_manager import SessionManager
from exporter.excel_exporter import export_to_excel

app         = Flask(__name__)
session_mgr = SessionManager(os.path.join(os.path.dirname(__file__), "sessions.db"))


@app.errorhandler(Exception)
def handle_exception(exc):
    """
    Catch any unhandled Python exception and return JSON instead of Flask's
    default HTML error page.  This prevents the browser from seeing
    "Unexpected token '<'" when something crashes server-side.
    """
    import traceback
    return jsonify({
        "success": False,
        "error": f"{type(exc).__name__}: {exc}",
        "detail": traceback.format_exc(),
    }), 500


# ---------------------------------------------------------------------------
# Routes — pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Routes — Step 1: Analyze
# ---------------------------------------------------------------------------

@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Open the listing URL and the example detail URL.
    Return field samples from both pages + total page count.
    """
    data         = request.get_json()
    listing_url  = (data.get("listing_url")  or "").strip()
    detail_url   = (data.get("detail_url")   or "").strip()

    if not listing_url:
        return jsonify({"success": False, "error": "Listing URL is required."})
    if not detail_url:
        return jsonify({"success": False, "error": "Example detail URL is required."})

    try:
        listing_fields, total_pages = analyze_listing(listing_url)
    except Exception as exc:
        return jsonify({"success": False, "error": f"Listing page error: {exc}"})

    try:
        detail_fields = analyze_detail(detail_url)
    except Exception as exc:
        return jsonify({"success": False, "error": f"Detail page error: {exc}"})

    return jsonify({
        "success":       True,
        "listing_fields": listing_fields,
        "detail_fields":  detail_fields,
        "total_pages":    total_pages,
    })


# ---------------------------------------------------------------------------
# Routes — Step 2/3: Start & progress
# ---------------------------------------------------------------------------

@app.route("/start", methods=["POST"])
def start():
    """Create a session and launch the two-phase scraping thread."""
    data = request.get_json()
    listing_url             = (data.get("listing_url") or "").strip()
    selected_listing_fields = data.get("listing_fields") or []
    selected_detail_fields  = data.get("detail_fields")  or []
    pages_to_scrape         = int(data.get("pages_to_scrape") or 1)

    if not listing_url:
        return jsonify({"success": False, "error": "Listing URL is required."})
    if not selected_listing_fields and not selected_detail_fields:
        return jsonify({"success": False, "error": "Select at least one field."})

    session_id = session_mgr.create_session(
        listing_url,
        pages_to_scrape,
        selected_listing_fields,
        selected_detail_fields,
    )
    _launch(session_id, listing_url, pages_to_scrape,
            selected_listing_fields, selected_detail_fields)

    return jsonify({"success": True, "session_id": session_id})


@app.route("/resume/<session_id>", methods=["POST"])
def resume(session_id):
    """Resume a paused session from exactly where it stopped."""
    session = session_mgr.get_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Session not found."})
    if session["status"] == "completed":
        return jsonify({"success": False, "error": "Session is already completed."})

    session_mgr.set_status(session_id, "running")
    _launch(
        session_id,
        session["primary_url"],
        session["total_listing_pages"],
        session["selected_listing_fields"],
        session["selected_detail_fields"],
    )
    return jsonify({"success": True, "session_id": session_id})


@app.route("/progress/<session_id>")
def progress(session_id):
    """
    Server-Sent Events stream.
    Sends one JSON update per second describing both phases until done/paused.
    """
    def generate():
        while True:
            session = session_mgr.get_session(session_id)
            if not session:
                yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
                return

            total_merchants, done_merchants = session_mgr.count_merchants(session_id)

            payload = {
                "phase":             session["phase"],
                "phase1_current":    session["last_listing_page"],
                "phase1_total":      session["total_listing_pages"],
                "phase2_current":    done_merchants,
                "phase2_total":      total_merchants,
                "status":            session["status"],
                "error":             session.get("error_message") or "",
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if session["status"] in ("completed", "paused"):
                return

            time.sleep(1)

    return Response(
        generate(),
        content_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Routes — Download & session list
# ---------------------------------------------------------------------------

@app.route("/download/<session_id>")
def download(session_id):
    try:
        file_path = export_to_excel(session_id, session_mgr)
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"talabat_merchants_{session_id}.xlsx",
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/sessions")
def sessions():
    return jsonify(session_mgr.list_sessions())


# ---------------------------------------------------------------------------
# Background scraping — two phases
# ---------------------------------------------------------------------------

def _launch(session_id, listing_url, total_pages, listing_fields, detail_fields):
    thread = threading.Thread(
        target=_run,
        args=(session_id, listing_url, total_pages, listing_fields, detail_fields),
        daemon=True,
    )
    thread.start()


def _run(session_id, listing_url, total_pages, listing_fields, detail_fields):
    """
    Phase 1: scan listing pages, collect merchant URLs + card data.
    Phase 2: visit each detail page, enrich merchant rows.
    Both phases are resumable independently via last_listing_page and
    the detail_scraped flag on each merchant row.
    """
    session = session_mgr.get_session(session_id)

    # ---- Phase 1 --------------------------------------------------------
    if session["phase"] == 1:
        start_page = session["last_listing_page"] + 1

        for page_num in range(start_page, total_pages + 1):
            page_url = _page_url(listing_url, page_num)
            success  = False

            for attempt in range(3):
                try:
                    merchants = scrape_page(page_url, listing_fields)
                    session_mgr.save_merchants_from_page(session_id, merchants)
                    session_mgr.update_listing_progress(session_id, page_num)
                    success = True
                    break
                except Exception as exc:
                    last_err = str(exc)
                    time.sleep(2)

            if not success:
                session_mgr.set_status(
                    session_id, "paused",
                    f"Phase 1, page {page_num}: {last_err}"
                )
                return

            time.sleep(1)   # polite delay between listing pages

        session_mgr.set_phase(session_id, 2)

    # ---- Phase 2 --------------------------------------------------------
    if not detail_fields:
        # User only selected listing fields — skip detail scraping entirely
        session_mgr.set_status(session_id, "completed")
        return

    while True:
        merchant = session_mgr.get_next_unscraped_merchant(session_id)
        if not merchant:
            break

        success = False
        for attempt in range(3):
            try:
                detail_data = scrape_detail(merchant["merchant_url"], detail_fields)
                session_mgr.update_merchant_detail(merchant["id"], detail_data)
                success = True
                break
            except Exception as exc:
                last_err = str(exc)
                time.sleep(2)

        if not success:
            session_mgr.set_status(
                session_id, "paused",
                f"Phase 2, merchant {merchant['id']}: {last_err}"
            )
            return

        time.sleep(1)   # polite delay between detail pages

    session_mgr.set_status(session_id, "completed")


def _page_url(base_url, page_num):
    """Append ?page=N to a URL, correctly handling existing query params."""
    if page_num == 1:
        return base_url
    parsed = urlparse(base_url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["page"] = [str(page_num)]
    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs("exports", exist_ok=True)
    app.run(debug=False, threaded=True, port=5000)
