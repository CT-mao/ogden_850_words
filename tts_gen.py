import json
import os
import time
from pathlib import Path

import requests

# ── Kokoro TTS API 配置 ──────────────────────────────────────
TTS_API_URL = "http://localhost:5200/tts"
# TTS_PARAMS = {
#     "gender": "female",
#     "pitch": 1.0,
#     "speed": 0.9,
#     "temperature": 0.7,
#     "top_k": 50,
#     "top_p": 0.95,
# }
TTS_PARAMS = {
    "voice":"af_heart","speed":0.9
}


# ── OpenAI 兼容 TTS 配置（预留，切换时将下方适配器替换即可） ──
# TTS_BASE_URL = "http://localhost:8000/v1"
# TTS_API_KEY   = "not-needed"
# TTS_MODEL     = "tts-1"
# TTS_VOICE     = "alloy"
# TTS_SPEED     = 1.0

# ── 路径 ──────────────────────────────────────────────────────
DATA_PATH = "ogden_850_words_with_ipa.json"
AUDIO_DIR = "audio"

RETRY_DELAY = 5
MAX_RETRIES = 3


def tts(text: str, audio_path: str) -> None:
    payload = {**TTS_PARAMS, "text": text}
    last_err = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(TTS_API_URL, json=payload, timeout=120)
            resp.raise_for_status()
            with open(audio_path, "wb") as f:
                f.write(resp.content)
            return
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)

    raise RuntimeError(f"TTS failed after {MAX_RETRIES} retries: {last_err}")


def main():
    Path(AUDIO_DIR).mkdir(parents=True, exist_ok=True)

    with open(DATA_PATH, encoding="utf-8") as f:
        entries = json.load(f)

    total_ok = total_skip = total_err = 0

    for entry in entries:
        wid = entry["id"]
        word = entry["word"]
        sentence = entry["example"]["en"]

        tasks = [
            (f"{wid}_word.wav",      f"{word} , {word} , {word} "),
            (f"{wid}_sentence.wav",   sentence),
        ]

        for filename, text in tasks:
            filepath = os.path.join(AUDIO_DIR, filename)
            if os.path.exists(filepath):
                total_skip += 1
                continue

            print(f"  generating {filename} ... ", end="", flush=True)
            try:
                tts(text, filepath)
                print("OK")
                total_ok += 1
            except Exception as e:
                print(f"ERROR  {e}")
                total_err += 1

    print(f"\nDone  —  {total_ok} generated, {total_skip} skipped, {total_err} errors")


if __name__ == "__main__":
    main()
