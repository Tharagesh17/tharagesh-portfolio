"""Freelance portfolio + live AI-agent playground (Flask).

Serves a portfolio landing + 5 runnable agents (web-research, competitive-analysis,
pdf-qa, email-draft, voice) powered by the user's Sarvam key. The key is server-side
only (env var). Ships a small editorial UI (AgentHelm tokens).
"""
import os, io, time, re, hashlib, threading
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv, dotenv_values

# Force-load THIS project's .env (override any stray .env up the tree).
_local = dotenv_values(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
for _k, _v in _local.items():
    os.environ[_k] = _v
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

import chat_sarvam
import agents.web_research as web_research
import agents.competitive_analysis as competitive_analysis
import agents.pdf_qa as pdf_qa
import agents.email_draft as email_draft
import agents.voice as voice

app = Flask(__name__)
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- simple per-IP rate limit (in-memory) ---
_RATE = {}
_RATE_LOCK = threading.Lock()
LIMIT_PER_HOUR = 12


def _rate_ok(ip: str) -> bool:
    now = time.time()
    with _RATE_LOCK:
        hits = _RATE.get(ip, [])
        hits = [t for t in hits if now - t < 3600]
        if len(hits) >= LIMIT_PER_HOUR:
            _RATE[ip] = hits
            return False
        hits.append(now)
        _RATE[ip] = hits
        return True


# --- serialize Sarvam calls: free tier throttles concurrent/burst calls with empty replies ---
_SARVAM_LOCK = threading.Lock()
_LAST_CALL = 0.0
_MIN_GAP = 2.0  # seconds between Sarvam calls to avoid throttle


def _with_sarvam(fn):
    """Run fn while holding the Sarvam lock, spacing calls by _MIN_GAP."""
    global _LAST_CALL
    with _SARVAM_LOCK:
        wait = _MIN_GAP - (time.time() - _LAST_CALL)
        if wait > 0:
            time.sleep(wait)
        _LAST_CALL = time.time()
        return fn()


DISPATCH = {
    "web_research": lambda p: web_research.run(p.get("query", "")),
    "competitive_analysis": lambda p: competitive_analysis.run(
        p.get("competitors", ""), p.get("dimension", "features and pricing")),
    "email_draft": lambda p: email_draft.run(p.get("context", ""), p.get("tone", "professional")),
    "pdf_qa": lambda p: pdf_qa.run(p.get("pdf_text", ""), p.get("question", "")),
}


@app.route("/")
def index():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html"),
              encoding="utf-8") as fh:
        return fh.read()


@app.route("/api/run", methods=["POST"])
def api_run():
    if "SARVAM_API_KEY" not in os.environ:
        return jsonify({"ok": False, "error": "Sarvam key not configured on server."}), 500
    ip = request.remote_addr
    if not _rate_ok(ip):
        return jsonify({"ok": False, "error": "Rate limit: 12 runs/hour per IP."}), 429
    try:
        p = request.get_json(force=True)
        agent = p.get("agent")
        if agent not in DISPATCH:
            return jsonify({"ok": False, "error": f"Unknown agent: {agent}"}), 400
        if agent == "voice":
            return jsonify({"ok": False, "error": "Use /api/voice for audio."}), 400
        result = _with_sarvam(lambda: DISPATCH[agent](p))
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/voice", methods=["POST"])
def api_voice():
    if "SARVAM_API_KEY" not in os.environ:
        return jsonify({"ok": False, "error": "Sarvam key not configured on server."}), 500
    ip = request.remote_addr
    if not _rate_ok(ip):
        return jsonify({"ok": False, "error": "Rate limit: 12 runs/hour per IP."}), 429
    f = request.files.get("audio")
    if not f:
        return jsonify({"ok": False, "error": "No audio file."}), 400
    data = f.read()
    if len(data) > 8 * 1024 * 1024:
        return jsonify({"ok": False, "error": "Audio too large (max 8MB)."}), 400
    try:
        out = _with_sarvam(lambda: voice.run(data, f.filename or "audio.wav"))
        return jsonify({"ok": True, **out})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/pdf", methods=["POST"])
def api_pdf():
    if "SARVAM_API_KEY" not in os.environ:
        return jsonify({"ok": False, "error": "Sarvam key not configured on server."}), 500
    ip = request.remote_addr
    if not _rate_ok(ip):
        return jsonify({"ok": False, "error": "Rate limit: 12 runs/hour per IP."}), 429
    f = request.files.get("pdf")
    if not f:
        return jsonify({"ok": False, "error": "No PDF file."}), 400
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(f.read()))
        text = "\n".join((pg.extract_text() or "") for pg in reader.pages)[:12000]
        return jsonify({"ok": True, "pdf_text": text, "pages": len(reader.pages)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/resume")
def resume():
    return send_from_directory("static", "resume.pdf", as_attachment=True)




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
