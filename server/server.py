"""
Friday v0 server - the voice loop.

  friday (raw 16 kHz mono PCM)  ->  POST /talk
      Whisper (speech to text)  ->  Claude  ->  Piper (text to speech)
  friday  <-  "what you said\\nreply" + X-Audio-Id header
  friday  ->  GET /audio/<id>  <-  raw 16 kHz mono PCM

Run:  python server.py
"""

import io
import os
import socket
import time
import uuid
import wave

import anthropic
import numpy as np
import uvicorn
from fastapi import FastAPI, Request, Response
from faster_whisper import WhisperModel
from piper import PiperVoice

# ------------------------------------------------------------- settings
SAMPLE_RATE = 16000
WHISPER_MODEL = os.getenv("FRIDAY_WHISPER", "base.en")       # "small.en" = more accurate, slower
CLAUDE_MODEL = os.getenv("FRIDAY_MODEL", "claude-haiku-5-5")  # fast and cheap; try claude-sonnet-5-5
VOICE_PATH = os.getenv("FRIDAY_VOICE", "en_US-lessac-medium.onnx")
PORT = int(os.getenv("FRIDAY_PORT", "8000"))
MEMORY_EXCHANGES = 3        # remembers the last 3 back-and-forths
MEMORY_TIMEOUT_S = 300      # ...and forgets after 5 quiet minutes

SYSTEM_PROMPT = """You are Friday, a voice assistant living in a tiny pocket device \
with a small screen. Your reply is spoken aloud and shown on that screen.
- Answer in one to three short sentences unless the user asks for more.
- Plain spoken English only: no markdown, bullet points, emoji, or URLs.
- Say symbols as words ("degrees", "percent", "dollars").
- If you don't know something current (news, weather, their email), say so briefly."""

# ------------------------------------------------------------- startup
print(f"Loading Whisper ({WHISPER_MODEL})...")
stt = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
print(f"Loading voice ({VOICE_PATH})...")
tts = PiperVoice.load(VOICE_PATH)
# Reads ANTHROPIC_API_KEY. If your key isn't scoped to a workspace, also set
# FRIDAY_WORKSPACE to the workspace ID (Console > Settings > Workspaces).
_ws = os.getenv("FRIDAY_WORKSPACE")
claude = anthropic.Anthropic(default_headers={"anthropic-workspace-id": _ws} if _ws else None)

app = FastAPI()
history: list[dict] = []
last_talk = 0.0
pending_audio: dict[str, bytes] = {}


# ------------------------------------------------------------- pipeline
def transcribe(pcm: bytes) -> str:
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    segments, _ = stt.transcribe(audio, language="en", vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()


def ask_claude(text: str) -> str:
    global history, last_talk
    if time.time() - last_talk > MEMORY_TIMEOUT_S:
        history = []
    history.append({"role": "user", "content": text})
    try:
        msg = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=history[-(2 * MEMORY_EXCHANGES + 1):],  # always starts with a user turn
        )
    except Exception as e:
        history.pop()
        print(f"Claude error: {e}")
        return "Sorry, I couldn't reach Claude just now."
    reply = "".join(b.text for b in msg.content if b.type == "text").strip()
    history.append({"role": "assistant", "content": reply})
    last_talk = time.time()
    return reply


def speak(text: str) -> bytes:
    """Text -> raw 16 kHz mono 16-bit PCM."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        if hasattr(tts, "synthesize_wav"):   # piper-tts 1.3+
            tts.synthesize_wav(text, wf)
        else:                                 # piper-tts 1.2
            tts.synthesize(text, wf)
    buf.seek(0)
    with wave.open(buf, "rb") as wf:
        rate = wf.getframerate()
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    if rate != SAMPLE_RATE:  # resample (e.g. 22050 -> 16000)
        n = int(len(pcm) * SAMPLE_RATE / rate)
        pcm = np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype(np.int16)
    return pcm.tobytes()


def screen_safe(s: str) -> str:
    """The device font is ASCII-only."""
    for a, b in {"’": "'", "‘": "'", "“": '"', "”": '"',
                 "—": "-", "–": "-", "…": "...", "\n": " "}.items():
        s = s.replace(a, b)
    return s.encode("ascii", "ignore").decode()


# ------------------------------------------------------------- routes
@app.post("/talk")
async def talk(request: Request):
    pcm = await request.body()
    t0 = time.time()
    you = transcribe(pcm) if len(pcm) >= SAMPLE_RATE // 2 else ""
    t1 = time.time()
    reply = ask_claude(you) if you else "Sorry, I didn't catch that."
    t2 = time.time()
    audio_id = uuid.uuid4().hex[:8]
    pending_audio[audio_id] = speak(reply)
    t3 = time.time()
    print(f'\nYOU:  "{you}"\nFRIDAY: "{reply}"\n'
          f"      hear {t1 - t0:.1f}s | think {t2 - t1:.1f}s | speak {t3 - t2:.1f}s | "
          f"audio {len(pcm) / 2 / SAMPLE_RATE:.1f}s in")
    return Response(f"{screen_safe(you)}\n{screen_safe(reply)}",
                    media_type="text/plain; charset=utf-8",
                    headers={"X-Audio-Id": audio_id})


@app.get("/audio/{audio_id}")
def audio(audio_id: str):
    return Response(pending_audio.pop(audio_id, b""), media_type="application/octet-stream")


@app.get("/")
def health():
    return {"status": "ok", "model": CLAUDE_MODEL}


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    print(f'\nFriday server ready. In the firmware set:\n  SERVER = "http://{lan_ip()}:{PORT}"\n')
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
