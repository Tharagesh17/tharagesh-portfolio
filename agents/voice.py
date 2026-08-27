"""Agent 5 — Voice Agent: audio -> Sarvam STT (saaras:v3) -> sarvam-105b reply.

All on the one Sarvam key. Audio is bytes (WAV/MP3, REST <=30s). The transcript is
treated as DATA for the reply step.
"""
import os
from langchain_core.messages import HumanMessage, SystemMessage
from chat_sarvam import chat


def _transcribe(client, audio_bytes: bytes, filename: str) -> str:
    # Try the documented SDK path; fall back to raw REST if SDK shape differs.
    try:
        resp = client.speech_to_text.transcribe(
            file=audio_bytes, model="saaras:v3", mode="transcribe",
        )
        if isinstance(resp, str):
            return resp
        # resp.transcript may be '' for silence — distinguish from missing attr.
        if hasattr(resp, "transcript"):
            return resp.transcript or ""
        return str(resp)
    except Exception:
        import requests
        r = requests.post(
            "https://api.sarvam.ai/v1/speech-to-text",
            headers={
                "api-subscription-key": os.environ["SARVAM_API_KEY"],
                "Authorization": f"Bearer {os.environ['SARVAM_API_KEY']}",
            },
            files={"file": (filename, audio_bytes)},
            data={"model": "saaras:v3", "mode": "transcribe"},
            timeout=60,
        )
        r.raise_for_status()
        return r.json().get("transcript", "")


def run(audio_bytes: bytes, filename: str = "audio.wav") -> dict:
    from sarvamai import SarvamAI
    client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
    transcript = _transcribe(client, audio_bytes, filename)
    reply = chat(
        [
            SystemMessage(content="You are a helpful voice assistant. Answer concisely and clearly."),
            HumanMessage(content=transcript or "(no speech detected)"),
        ],
        fallback_messages=[
            SystemMessage(content="You are a helpful assistant. Answer concisely."),
            HumanMessage(content=transcript or "(no speech detected)"),
        ],
    )
    return {"transcript": transcript, "reply": reply}
