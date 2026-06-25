"""Step 1: 数据迁移 — 旧 example → examples[] 数组"""
import json
import os

DATA_PATH = "ogden_850_words_with_ipa.json"
JS_PATH = "words_data.js"

TENSE_LABELS = {
    "simple_present": "一般现在时",
    "present_continuous": "现在进行时",
    "present_perfect": "现在完成时",
    "simple_past": "一般过去时",
    "past_continuous": "过去进行时",
    "past_perfect": "过去完成时",
    "simple_future": "一般将来时",
    "future_continuous": "将来进行时",
}

LEVEL_LABELS = {
    "beginner": "初级 · A1",
    "elementary": "初中级 · A2",
    "intermediate": "中级 · B1",
    "advanced": "中高级 · B2-C1",
    "native": "母语级 · C2",
}

def detect_tense(en: str) -> str:
    s = en.lower().strip()
    if any(w in s for w in ["will", "shall", "going to", "gonna"]):
        return "simple_future"
    if any(w in s for w in ["was", "were"]) and any(w.endswith("ing") for w in s.split()):
        return "past_continuous"
    if any(w in s for w in ["have", "has", "had"]) and any(w.endswith("ed") or w.endswith("en") for w in s.split()):
        return "present_perfect"
    if any(w in s for w in ["is", "am", "are"]) and any(w.endswith("ing") for w in s.split()):
        return "present_continuous"
    if any(w in s for w in ["came", "got", "gave", "went", "kept", "made", "put", "took", "was", "were", "did", "had", "said", "saw", "sent"]):
        return "simple_past"
    return "simple_present"

def detect_level(en: str) -> str:
    word_count = len(en.split())
    if word_count <= 5:
        return "beginner"
    if word_count <= 10:
        return "elementary"
    if word_count <= 15:
        return "intermediate"
    if word_count <= 20:
        return "advanced"
    return "native"

def migrate():
    with open(DATA_PATH, encoding="utf-8") as f:
        entries = json.load(f)

    for entry in entries:
        if "examples" in entry and len(entry["examples"]) > 0:
            continue

        old = entry.get("example", {})
        if not old or not old.get("en"):
            old = {"en": f"Example sentence for {entry['word']}.", "cn": f"关于{entry['word']}的例句。"}

        examples = [{
            "id": f"{entry['id']}_01",
            "en": old["en"],
            "cn": old.get("cn", ""),
            "tense": detect_tense(old["en"]),
            "level": detect_level(old["en"]),
        }]
        entry["examples"] = examples

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"Migrated {len(entries)} words → examples[] written to {DATA_PATH}")

    js_content = "window.__WORDS_DATA =\n" + json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
    with open(JS_PATH, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"Synced → {JS_PATH}")

    # stats
    tense_count = {}
    level_count = {}
    for entry in entries:
        for ex in entry.get("examples", []):
            t = ex.get("tense", "unknown")
            lv = ex.get("level", "unknown")
            tense_count[t] = tense_count.get(t, 0) + 1
            level_count[lv] = level_count.get(lv, 0) + 1
    print("\nTense distribution:")
    for k in TENSE_LABELS:
        print(f"  {k:25s} {TENSE_LABELS[k]:12s} → {tense_count.get(k, 0)}")
    print("\nLevel distribution:")
    for k in LEVEL_LABELS:
        print(f"  {k:15s} {LEVEL_LABELS[k]:20s} → {level_count.get(k, 0)}")

if __name__ == "__main__":
    migrate()
