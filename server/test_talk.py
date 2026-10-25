"""
Tests the server without the device: speaks a question with Piper,
sends it to /talk, and saves Friday's spoken answer to reply.wav.

Run (with server.py running in another terminal):
    python test_talk.py "What is the capital of Italy?"
"""

import io
import sys
import urllib.request
import wave

import numpy as np
from piper import PiperVoice

SERVER = "http://127.0.0.1:8000"
question = sys.argv[1] if len(sys.argv) > 1 else "In one sentence, what is Ohm's law?"

# 1. Make a fake "recording" of the question at 16 kHz
voice = PiperVoice.load("en_US-lessac-medium.onnx")
buf = io.BytesIO()
with wave.open(buf, "wb") as wf:
    (voice.synthesize_wav if hasattr(voice, "synthesize_wav") else voice.synthesize)(question, wf)
buf.seek(0)
with wave.open(buf, "rb") as wf:
    rate = wf.getframerate()
    pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
n = int(len(pcm) * 16000 / rate)
pcm = np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype(np.int16)

# 2. Send it, exactly like the device does
req = urllib.request.Request(f"{SERVER}/talk", data=pcm.tobytes(),
                             headers={"Content-Type": "application/octet-stream"})
with urllib.request.urlopen(req, timeout=120) as r:
    you, _, reply = r.read().decode().partition("\n")
    audio_id = r.headers["X-Audio-Id"]
print(f"Heard: {you}\nReply: {reply}")

# 3. Fetch the spoken reply and save it
with urllib.request.urlopen(f"{SERVER}/audio/{audio_id}", timeout=60) as r:
    reply_pcm = r.read()
with wave.open("reply.wav", "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
    wf.writeframes(reply_pcm)
print("Saved reply.wav - open it to hear Friday.")
