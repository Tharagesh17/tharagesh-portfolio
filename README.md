# Portfolio — Live AI Agent Playground

A freelance portfolio site with **5 runnable AI agents** powered by **Sarvam AI**
(`sarvam-105b` for chat, `saaras:v3` for speech). Visitors can try the agents live
from the dashboard.

## Agents
1. **Web Research** — searches the web (DuckDuckGo) and synthesizes a markdown report.
2. **Competitive Analysis** — compares companies on a chosen dimension.
3. **PDF Q&A** — answers questions from an uploaded PDF (text only).
4. **Email Draft** — drafts a clean email from bullet points.
5. **Voice Agent** — transcribes uploaded audio (≤30s) and answers.

## Run locally
```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
# put your key in .env:  SARVAM_API_KEY=sk_...
.venv\Scripts\python app.py
# open http://127.0.0.1:5000
```

## Deploy (free, Render)
1. Push this repo to GitHub.
2. In Render: New → Web Service → connect repo → free plan.
3. Set env var `SARVAM_API_KEY` in the Render dashboard (never commit it).
4. Deploy — Render serves a public URL.

## Security
- The Sarvam key is **server-side only** (env var). It is never sent to the browser.
- Rate-limited to 12 agent runs/hour per visitor.

## Notes
- Sarvam's free tier occasionally returns empty completions under load; the agent
  clients retry with backoff and a source-free fallback so responses stay useful.
