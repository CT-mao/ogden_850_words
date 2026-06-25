"""本地服务 — 托管前端 + AI 例句生成

前端与 API 同端口，一条命令启动：
  python3 api_server.py

Usage:
  python3 api_server.py [--port 5201] [--model huihui_ai/hy-mt1.5-abliterated:latest]
  LLM_MODEL=qwen3.5:9b python3 api_server.py
"""

import argparse
import json
import mimetypes
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

import httpx

DATA_PATH = "ogden_850_words_with_ipa.json"
JS_PATH = "words_data.js"
DEFAULT_OLLAMA_URL = "http://localhost:11434/v1/chat/completions"

LEVEL_DESC = {
    "beginner": "A1 level, ≤5 words, only basic vocabulary, SVO sentences",
    "elementary": "A2 level, 8-12 words, simple modifiers, basic conjunctions (and, but, or)",
    "intermediate": "B1 level, compound sentences, subordinate clauses, passive voice basics",
    "advanced": "B2-C1 level, complex structures, abstract expressions",
    "native": "C2 level, idiomatic expressions, rhetorical devices",
}

TENSE_DESC = {
    "simple_present": "habitual actions or general truths",
    "present_continuous": "actions happening right now",
    "present_perfect": "past actions with present relevance",
    "simple_past": "completed past actions",
    "past_continuous": "actions in progress at a past moment",
    "past_perfect": "actions completed before another past action",
    "simple_future": "future actions or predictions",
    "future_continuous": "actions in progress at a future moment",
}


def load_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_data(entries):
    if len(entries) < 800:
        raise RuntimeError(f"Refusing to save: only {len(entries)} entries")
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    js = "window.__WORDS_DATA =\n" + json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
    with open(JS_PATH, "w", encoding="utf-8") as f:
        f.write(js)


class Handler(BaseHTTPRequestHandler):
    api_url = DEFAULT_OLLAMA_URL
    model = "huihui_ai/hy-mt1.5-abliterated:latest"

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._json(200, {"status": "ok"})
            return
        if path in ("", "/"):
            path = "/index.html"
        self._serve_static(path)

    def _serve_static(self, path):
        filepath = Path(".") / path.lstrip("/")
        filepath = filepath.resolve()
        cwd = Path(".").resolve()
        if not str(filepath).startswith(str(cwd)):
            self._json(403, {"error": "forbidden"})
            return
        if not filepath.is_file():
            self._json(404, {"error": "not found"})
            return
        mime, _ = mimetypes.guess_type(str(filepath))
        if mime is None:
            mime = "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(filepath, "rb") as f:
            self.wfile.write(f.read())

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/generate":
            self._json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception as e:
            self._json(400, {"error": f"bad request: {e}"})
            return

        word_id = body.get("word_id")
        tense = body.get("tense", "simple_present")
        level = body.get("level", "beginner")
        count = body.get("count", 1)

        if not word_id:
            self._json(400, {"error": "word_id is required"})
            return

        try:
            result = self._generate(word_id, tense, level, count)
            self._json(200, result)
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _generate(self, word_id, tense, level, count):
        entries = load_data()
        entry = next((e for e in entries if e["id"] == word_id), None)
        if not entry:
            raise ValueError(f"word {word_id} not found")

        prompt = self._build_prompt(entry, tense, level, count)
        llm_result = self._call_llm(prompt)

        existing = entry.setdefault("examples", [])
        start_idx = len(existing)
        new_examples = []
        for i, item in enumerate(llm_result):
            ex = {
                "id": f"{word_id}_{start_idx + i + 1:02d}",
                "en": item["en"],
                "cn": item.get("cn", ""),
                "tense": tense,
                "level": level,
            }
            existing.append(ex)
            new_examples.append(ex)

        save_data(entries)
        return {"examples": new_examples}

    def _build_prompt(self, entry, tense, level, count):
        return f"""You are a professional English teaching assistant. Generate {count} English sentence(s) for the word "{entry['word']}".

Word: {entry['word']} (IPA: {entry.get('ipa', '')})
Definition: {entry.get('definition_en', '')}
Chinese: {entry.get('meaning_cn', '')}

Requirements:
1. "{entry['word']}" MUST appear in EVERY sentence.
2. Level: {level} — {LEVEL_DESC.get(level, level)}
3. Tense: {tense} — {TENSE_DESC.get(tense, tense)}
4. Each sentence must be natural, everyday, suitable for language learners.

Return ONLY a valid JSON array — no markdown, no other text:
[
  {{"en": "...", "cn": "..."}},
  {{"en": "...", "cn": "..."}}
]"""

    def _call_llm(self, prompt, max_retries=2):
        last_err = None
        for attempt in range(max_retries + 1):
            try:
                resp = httpx.post(
                    self.api_url,
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 1024,
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"].strip()
                content = content.removeprefix("```json").removesuffix("```").strip()
                parsed = json.loads(content)
                if not isinstance(parsed, list):
                    raise ValueError("response not a list")
                return parsed
            except Exception as e:
                last_err = e
                if attempt < max_retries:
                    time.sleep(3 * (attempt + 1))
        raise RuntimeError(f"LLM failed: {last_err}")

    def _json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self._json(204, "")

    def log_message(self, fmt, *args):
        print(f"[api] {args[0]} {args[1]} {args[2]}")


def main():
    parser = argparse.ArgumentParser(description="Words850 API server")
    parser.add_argument("--port", type=int, default=5201)
    parser.add_argument("--model", default="huihui_ai/hy-mt1.5-abliterated:latest")
    parser.add_argument("--api-url", default=DEFAULT_OLLAMA_URL)
    args = parser.parse_args()

    Handler.api_url = os.environ.get("LLM_API_URL", args.api_url)
    Handler.model = os.environ.get("LLM_MODEL", args.model)

    server = HTTPServer(("0.0.0.0", args.port), Handler)
    print(f"Words850 API running at http://localhost:{args.port}")
    print(f"  Model: {Handler.model}")
    print(f"  Post to http://localhost:{args.port}/generate to create examples")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
