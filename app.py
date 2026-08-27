"""Freelance portfolio + live AI-agent playground (Flask).

Serves a portfolio landing + 5 runnable agents (web-research, competitive-analysis,
pdf-qa, email-draft, voice) powered by the user's Sarvam key. The key is server-side
only (env var). Ships a small editorial UI (AgentHelm tokens).
"""
import os, io, time, re, hashlib, threading
from flask import Flask, request, jsonify, render_template_string, send_from_directory
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
    return render_template_string(INDEX_HTML)


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


INDEX_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Agent Dev — Portfolio</title>
<style>
  :root{ --paper:#F4F1EA; --ink:#1A1916; --line:#D5D0C4; --vermilion:#C7431F;
         --muted:#6b665c; --card:#FBF9F4; }
  *{box-sizing:border-box}
  body{margin:0;background:var(--paper);color:var(--ink);
    font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;}
  header{border-bottom:1px solid var(--line);padding:22px 32px;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}
  header h1{font-size:22px;margin:0;font-weight:680;letter-spacing:-.01em}
  header .sub{color:var(--muted);font-size:14px}
  .wrap{max-width:1080px;margin:0 auto;padding:32px}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:600;margin:36px 0 14px}
  .hero p{font-size:19px;max-width:680px;color:var(--ink)}
  .hero .cta{display:inline-block;margin-top:14px;background:var(--vermilion);color:#fff;
    padding:11px 20px;border-radius:8px;text-decoration:none;font-weight:600}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}
  .card{border:1px solid var(--line);border-radius:12px;background:var(--card);padding:18px}
  .card h3{margin:0 0 4px;font-size:17px}
  .card .tag{font-size:11px;color:var(--vermilion);text-transform:uppercase;letter-spacing:.08em;font-weight:700}
  .card p.desc{color:var(--muted);font-size:13.5px;margin:6px 0 12px;min-height:38px}
  input,textarea,select{width:100%;border:1px solid var(--line);border-radius:8px;background:#fff;
    color:var(--ink);padding:9px 11px;font:14px/1.4 inherit;margin-bottom:8px}
  textarea{min-height:64px;resize:vertical}
  button{font:inherit;cursor:pointer;border:1px solid var(--ink);background:var(--ink);color:var(--paper);
    padding:8px 15px;border-radius:8px;font-weight:600}
  button:disabled{opacity:.45;cursor:not-allowed}
  .out{margin-top:12px;background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px;
    font-size:13.5px;white-space:pre-wrap;max-height:280px;overflow:auto;display:none}
  .err{color:var(--vermilion);font-size:13px;margin-top:8px;display:none}
  .note{font-size:12px;color:var(--muted);margin-top:6px}
  footer{border-top:1px solid var(--line);margin-top:48px;padding:20px 32px;color:var(--muted);font-size:13px;
    display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
  a{color:var(--vermilion)}
</style>
</head>
<body>
<header>
  <h1>AI Agent Developer</h1>
  <span class="sub">Freelance · production-ready AI agents</span>
</header>
<div class="wrap">
  <section class="hero">
    <h2>About</h2>
    <p>I build production-ready AI agents — RAG, tool-use, multi-agent workflows, and voice —
       for businesses that want something that actually works, not a demo. Try five of my
       agents live below. They run on <a href="https://sarvam.ai" target="_blank">Sarvam AI</a>.</p>
    <a class="cta" href="mailto:hello@example.com">Work with me</a>
  </section>

  <h2>Try my agents</h2>
  <div class="grid" id="cards"></div>

  <p class="note">Runs are rate-limited (12/hour per visitor) and powered by the Sarvam API.
     Your API key stays server-side and is never sent to the browser.</p>
</div>
<footer>
  <span>Built with Sarvam AI · sarvam-105b + saaras:v3</span>
  <span>© 2026 — freelance AI agent developer</span>
</footer>

<script>
const AGENTS = [
  {id:'web_research', name:'Web Research', tag:'multi-step', desc:'Searches the web and synthesizes a markdown report.',
    fields:[{k:'query',ph:'e.g. latest advances in RAG',t:'text'}]},
  {id:'competitive_analysis', name:'Competitive Analysis', tag:'multi-step', desc:'Compares up to 3 companies on a dimension.',
    fields:[{k:'competitors',ph:'OpenAI, Anthropic, Cohere',t:'text'},{k:'dimension',ph:'features and pricing',t:'text'}]},
  {id:'pdf_qa', name:'PDF Q&A', tag:'document', desc:'Answers questions from an uploaded PDF (text only).',
    fields:[{k:'pdf',t:'file',accept:'.pdf'},{k:'question',ph:'Summarize the key points',t:'text'}]},
  {id:'email_draft', name:'Email Draft', tag:'text', desc:'Drafts a clean email from your bullet points.',
    fields:[{k:'context',ph:'Bullets: project delayed...',t:'area'},{k:'tone',ph:'professional',t:'text'}]},
  {id:'voice', name:'Voice Agent', tag:'speech', desc:'Upload audio (<=30s) — gets transcribed and answered.',
    fields:[{k:'audio',t:'file',accept:'audio/*'}]},
];

const cards = document.getElementById('cards');
AGENTS.forEach(a=>{
  const c=document.createElement('div'); c.className='card';
  let fields='';
  a.fields.forEach(f=>{
    if(f.t==='file') fields+=`<input type="file" data-k="${f.k}" accept="${f.accept||''}">`;
    else if(f.t==='area') fields+=`<textarea data-k="${f.k}" placeholder="${f.ph||''}"></textarea>`;
    else fields+=`<input data-k="${f.k}" placeholder="${f.ph||''}" value="${f.t==='text'?(f.ph==='professional'?'professional':''):''}">`;
  });
  c.innerHTML=`<span class="tag">${a.tag}</span><h3>${a.name}</h3><p class="desc">${a.desc}</p>${fields}
    <button data-id="${a.id}">Run</button><div class="out"></div><div class="err"></div>`;
  cards.appendChild(c);
  const btn=c.querySelector('button'); const out=c.querySelector('.out'); const err=c.querySelector('.err');
  btn.onclick=async()=>{
    btn.disabled=true; out.style.display='none'; err.style.display='none'; out.textContent='Running…'; out.style.display='block';
    try{
      if(a.id==='pdf_qa'){
        const fd=new FormData(); const pf=c.querySelector('[data-k=pdf]').files[0];
        if(!pf){throw new Error('Upload a PDF first.');}
        fd.append('pdf',pf);
        const r1=await fetch('/api/pdf',{method:'POST',body:fd}); const j1=await r1.json();
        if(!j1.ok) throw new Error(j1.error);
        const q=c.querySelector('[data-k=question]').value;
        const r2=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({agent:'pdf_qa',pdf_text:j1.pdf_text,question:q})});
        const j2=await r2.json(); if(!j2.ok) throw new Error(j2.error);
        out.textContent=j2.result;
      } else if(a.id==='voice'){
        const af=c.querySelector('[data-k=audio]').files[0];
        if(!af){throw new Error('Upload audio first.');}
        const fd=new FormData(); fd.append('audio',af);
        const r=await fetch('/api/voice',{method:'POST',body:fd}); const j=await r.json();
        if(!j.ok) throw new Error(j.error);
        out.textContent='Transcript: '+j.transcript+'\n\nReply: '+j.reply;
      } else {
        const p={agent:a.id};
        a.fields.forEach(f=>{ if(f.t!=='file') p[f.k]=c.querySelector(`[data-k="${f.k}"]`).value; });
        const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
        const j=await r.json(); if(!j.ok) throw new Error(j.error);
        out.textContent=j.result;
      }
    }catch(e){ err.textContent=e.message; err.style.display='block'; out.style.display='none'; }
    finally{ btn.disabled=false; }
  };
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
