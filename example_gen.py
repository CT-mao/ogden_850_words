"""Step 2+4: LLM 例句生成脚本

Usage:
  python3 example_gen.py --all --level intermediate,advanced --tense simple_past,simple_future
  python3 example_gen.py --word word_001 --tense simple_past --count 2
  python3 example_gen.py --backfill
  python3 example_gen.py --backfill --dry-run
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

DATA_PATH = "ogden_850_words_with_ipa.json"
JS_PATH = "words_data.js"

TENSE_LABELS = {
    "simple_present": "一般现在时, habitual actions or general truths",
    "present_continuous": "现在进行时, actions happening right now",
    "present_perfect": "现在完成时, past actions with present relevance",
    "simple_past": "一般过去时, completed past actions",
    "past_continuous": "过去进行时, actions in progress at a past moment",
    "past_perfect": "过去完成时, actions completed before another past action",
    "simple_future": "一般将来时, future actions or predictions",
    "future_continuous": "将来进行时, actions in progress at a future moment",
}

LEVEL_DESCRIPTIONS = {
    "beginner": "·A1· ≤5 words, only Ogden 850 vocabulary, SVO sentences",
    "elementary": "·A2· 8-12 words, simple modifiers, basic conjunctions (and, but, or)",
    "intermediate": "·B1· compound sentences, subordinate clauses, passive voice basics",
    "advanced": "·B2-C1· complex structures, subjunctive mood, abstract expressions",
    "native": "·C2· idiomatic expressions, rhetorical devices, cultural references",
}

DEFAULT_OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
DEFAULT_MODEL = "huihui_ai/hy-mt1.5-abliterated:latest"


def load_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_data(entries):
    if len(entries) < 800:
        raise RuntimeError(f"Refusing to save: only {len(entries)} entries (expected ≥800). Data corruption detected.")
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    js = "window.__WORDS_DATA =\n" + json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
    with open(JS_PATH, "w", encoding="utf-8") as f:
        f.write(js)


def build_prompt(entry, count, level, tense):
    word = entry["word"]
    ipa = entry.get("ipa", "")
    def_en = entry.get("definition_en", "")
    meaning_cn = entry.get("meaning_cn", "")

    level_desc = LEVEL_DESCRIPTIONS.get(level, "")
    tense_desc = TENSE_LABELS.get(tense, tense)

    prompt = f"""You are a professional English teaching assistant. Generate {count} English sentence(s) for the word "{word}".

Word info:
- IPA: {ipa}
- Definition: {def_en}
- Chinese: {meaning_cn}
- CEFR Level: {level} {level_desc}
- Tense: {tense} — {tense_desc}

Requirements:
1. The word "{word}" MUST appear in EVERY sentence.
2. Use ONLY CEFR {level}-level vocabulary and grammar.
3. Tense must be strictly {tense}.
4. Each sentence must be a complete, natural, everyday sentence suitable for language learners.
5. Keep sentences short and clear for level {level}.

Return ONLY a valid JSON array — no markdown, no explanation, no other text:
[
  {{"en": "...", "cn": "Chinese translation..."}},
  {{"en": "...", "cn": "Chinese translation..."}}
]"""
    return prompt


def call_llm(prompt, api_url, model, temperature=0.7, max_retries=2):
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = httpx.post(
                api_url,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 1024,
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            content = content.removeprefix("```json").removesuffix("```").strip()

            parsed = json.loads(content)
            if not isinstance(parsed, list):
                raise ValueError("response is not a list")
            for item in parsed:
                if not isinstance(item, dict) or "en" not in item:
                    raise ValueError(f"invalid item: {item}")
            return parsed
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"LLM call failed after {max_retries + 1} attempts: {last_err}")


def gen_examples(entry, count, level, tense, api_url, model):
    prompt = build_prompt(entry, count, level, tense)
    result = call_llm(prompt, api_url, model)
    examples = []
    for i, item in enumerate(result):
        ex = {
            "id": f"{entry['id']}_{len(entry.get('examples', [])) + i + 1:02d}",
            "en": item["en"],
            "cn": item.get("cn", ""),
            "tense": tense,
            "level": level,
        }
        examples.append(ex)
    return examples


COVERAGE_TARGET = 4  # minimum examples per word
PRIORITY_TENSES = ["simple_present", "simple_past", "simple_future",
                   "present_continuous", "present_perfect", "past_continuous"]


def build_backfill_prompt(entry, missing):
    word = entry["word"]
    lines = []
    for tense, level in missing:
        lines.append(f"  - tense={tense}, level={level}: {LEVEL_DESCRIPTIONS[level]}")
    combos_str = "\n".join(lines)

    return f"""You are a professional English teaching assistant. Generate example sentences for the word "{word}" (IPA: {entry.get("ipa", "")}) — definition: {entry.get("definition_en", "")}, Chinese: {entry.get("meaning_cn", "")}.

Generate exactly {len(missing)} sentences, one for each tense+level combo below:

{combos_str}

Requirements:
1. The word "{word}" MUST appear in EVERY sentence.
2. Each sentence must use the exact tense specified for it.
3. Each sentence must use only vocabulary appropriate for its CEFR level.
4. All sentences must be complete, natural, everyday sentences.

Return a JSON array where each item has the "tense" and "level" fields matching the spec:
[
  {{"en": "...", "cn": "Chinese translation...", "tense": "...", "level": "..."}},
  {{"en": "...", "cn": "Chinese translation...", "tense": "...", "level": "..."}}
]
Return ONLY the JSON, no markdown, no other text."""


def backfill_all(entries, api_url, model, dry_run=False):
    total_gen = 0
    total_err = 0
    error_words = []

    for idx, entry in enumerate(entries):
        wid = entry["id"]
        existing = set()
        for ex in entry.get("examples", []):
            existing.add((ex.get("tense"), ex.get("level")))

        missing = []
        covered_tenses = set(t for t, _ in existing)

        for t in PRIORITY_TENSES:
            if t not in covered_tenses:
                for lv in ["beginner", "elementary"]:
                    if (t, lv) not in existing:
                        missing.append((t, lv))

        while len(existing) + len(missing) < COVERAGE_TARGET:
            found = False
            for t in PRIORITY_TENSES:
                for lv in ["beginner", "elementary", "intermediate"]:
                    if (t, lv) not in existing and (t, lv) not in missing:
                        missing.append((t, lv))
                        found = True
                        break
                if found:
                    break
            if not found:
                break

        if not missing:
            continue

        if dry_run:
            for tense, level in missing:
                print(f"  [{wid}] {entry['word']}: missing ({tense}, {level})")
            continue

        try:
            prompt = build_backfill_prompt(entry, missing)
            result = call_llm(prompt, api_url, model)
            start_idx = len(entry.get("examples", []))
            added = 0
            for i, item in enumerate(result):
                tense = item.get("tense") or missing[i][0]
                level = item.get("level") or missing[i][1]
                if (tense, level) in existing:
                    continue
                ex = {
                    "id": f"{wid}_{start_idx + added + 1:02d}",
                    "en": item["en"],
                    "cn": item.get("cn", ""),
                    "tense": tense,
                    "level": level,
                }
                entry.setdefault("examples", []).append(ex)
                existing.add((tense, level))
                added += 1
            total_gen += added
            t_str = ", ".join(f"{t}/{lv}" for t, lv in missing[:added])
            print(f"  [{wid}] {entry['word']}: generated {added} ({t_str})")
        except Exception as e:
            total_err += 1
            error_words.append((wid, str(e)))
            print(f"  [{wid}] {entry['word']}: ERROR — {e}")

        if idx % 25 == 0 and idx > 0:
            print(f"  --- checkpoint at {idx}/{len(entries)} ---")
            save_data(entries)

    save_data(entries)

    print(f"\nBackfill complete — {len(entries)} words processed")
    print(f"  Generated: {total_gen}")
    print(f"  Errors: {total_err}")
    for wid, err in error_words:
        print(f"    ⚠ {wid}: {err}")

    counts = [len(w.get("examples", [])) for w in entries]
    print(f"  Now avg: {sum(counts)/len(counts):.1f} per word")
    ge4 = sum(1 for c in counts if c >= 4)
    print(f"  Words with ≥4 examples: {ge4}")

    return total_gen, total_err


def main():
    parser = argparse.ArgumentParser(description="Generate English example sentences via local LLM")
    parser.add_argument("--word", help="Word ID to generate for (comma-separated)")
    parser.add_argument("--all", action="store_true", help="Generate for all words")
    parser.add_argument("--backfill", action="store_true", help="Backfill missing tense×level combos")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated")
    parser.add_argument("--level", default="beginner,intermediate,advanced", help="Comma-separated levels")
    parser.add_argument("--tense", default="simple_present,simple_past,simple_future", help="Comma-separated tenses")
    parser.add_argument("--count", type=int, default=1, help="Examples per call")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name")
    parser.add_argument("--api-url", default=DEFAULT_OLLAMA_URL, help="OpenAI-compatible API URL")
    parser.add_argument("--force", action="store_true", help="Regenerate even if examples exist")
    args = parser.parse_args()

    entries = load_data()
    api_url = os.environ.get("LLM_API_URL", args.api_url)
    model = os.environ.get("LLM_MODEL", args.model)

    if args.backfill:
        backfill_all(entries, api_url, model, dry_run=args.dry_run)
        return

    levels = [l.strip() for l in args.level.split(",")]
    tenses = [t.strip() for t in args.tense.split(",")]

    if args.word:
        word_ids = [w.strip() for w in args.word.split(",")]
        targets = [e for e in entries if e["id"] in word_ids]
    elif args.all:
        targets = entries
    else:
        parser.print_help()
        return

    total_gen = 0
    total_err = 0
    for entry in targets:
        if not args.force and entry.get("examples") and len(entry["examples"]) > 1:
            print(f"  [{entry['id']}] {entry['word']}: exists, use --force")
            continue
        for tense in tenses:
            for level in levels:
                try:
                    exs = gen_examples(entry, args.count, level, tense, api_url, model)
                    entry.setdefault("examples", [])
                    entry["examples"].extend(exs)
                    total_gen += len(exs)
                    print(f"  [{entry['id']}] {entry['word']} ({level}, {tense}) → {len(exs)} exs")
                except Exception as e:
                    total_err += 1
                    print(f"  [{entry['id']}] {entry['word']} ({level}, {tense}) → ERROR: {e}")

    save_data(entries)
    print(f"\nDone. Generated {total_gen}, errors {total_err}")


if __name__ == "__main__":
    main()
