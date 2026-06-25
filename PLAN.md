# Words850 — 多例句增强计划

## 概述

为 850 个 Ogden 基础词汇扩充多难度、多时态例句，前端支持设置筛选，LLM 驱动生成。

---

## Step 1 — 存储模型设计

### 1.1 难度等级（5 级，CEFR 对齐）

| key | label | CEFR | 句子特征 |
|-----|-------|------|---------|
| `beginner` | 初级 · A1 | A1 | ≤5 词，仅用 Ogden 850 词汇，SVO 简单句 |
| `elementary` | 初中级 · A2 | A2 | 8-12 词，少量修饰语，基础连词 |
| `intermediate` | 中级 · B1 | B1 | 复合句，含从句、被动语态基础用法 |
| `advanced` | 中高级 · B2-C1 | B2-C1 | 复杂句式，虚拟语气，抽象表达 |
| `native` | 母语级 · C2 | C2 | 地道习语，修辞手法，文化典故 |

### 1.2 时态体系（8 种）

| key | label |
|-----|-------|
| `simple_present` | 一般现在时 |
| `present_continuous` | 现在进行时 |
| `present_perfect` | 现在完成时 |
| `simple_past` | 一般过去时 |
| `past_continuous` | 过去进行时 |
| `past_perfect` | 过去完成时 |
| `simple_future` | 一般将来时 |
| `future_continuous` | 将来进行时 |

### 1.3 数据模型变更

```json
{
  "id": "word_001",
  "word": "come",
  "ipa": "/kʌm/",
  "category": "OP",
  "meaning_cn": "来,前来",
  "definition_en": "move toward the speaker or a place",
  "synonyms": ["arrive", "approach", "reach"],
  "example": {                          ← 保留向后兼容
    "en": "Come here when you're ready.",
    "cn": "准备好了就过来。"
  },
  "examples": [                         ← 新增数组
    {
      "id": "ex_001_01",
      "en": "Come here when you're ready.",
      "cn": "准备好了就过来。",
      "tense": "simple_present",
      "level": "beginner"
    }
  ]
}
```

迁移规则：
- 旧 `example` 保留不动，`examples` 数组从 `example` 派生第一条
- 前端优先读 `examples`，不存在则 fallback 到 `example`

### 1.4 涉及文件

- `ogden_850_words_with_ipa.json` — 主数据源（增量更新）
- `words_data.js` — 同步输出（用于前端，保持与 JSON 一致）

---

## Step 2 — LLM 例句生成脚本

### 2.1 文件：`example_gen.py`

依赖：`httpx` 或 `openai` 库（用户自行 `pip install`）

调用 Ollama OpenAI 兼容接口：`http://localhost:11434/v1/chat/completions`

模型：`huihui_ai/hy-mt1.5-abliterated:latest`

### 2.2 CLI 接口

```
python3 example_gen.py --level intermediate  \
                       --tense simple_past   \
                       --count 2             \
                       --word word_001       \
                       --force

python3 example_gen.py --backfill            \
                       --min-per-word 4
```

参数：
- `--level` 难度，多值逗号分隔，默认全部
- `--tense` 时态，多值逗号分隔，默认全部
- `--count` 每条生成几条，默认 1
- `--word` 指定单词 ID，支持多个逗号分隔
- `--all` 遍历全部 850 词
- `--force` 覆盖已有例句
- `--backfill` 补全模式：自动探测缺口并生成
- `--dry-run` 仅输出统计，不调用 LLM

### 2.3 Prompt 模板

```
You are a professional English teaching assistant.
Generate {count} English sentence(s) for the word "{word}" (IPA: {ipa}).

## Word info
- Definition: {definition_en}
- Chinese: {meaning_cn}
- CEFR Level: {level} — {level_description}
- Tense: {tense}

## Requirements
1. The word "{word}" MUST appear in EVERY sentence.
2. Use ONLY CEFR {level} vocabulary and grammar.
3. Tense must be strictly {tense}.
4. Each sentence must be a complete, natural, everyday sentence.
5. Keep sentences short for level {level}.

## Output format
Return ONLY a valid JSON array (no markdown, no other text):
[
  {"en": "...", "cn": "..."},
  {"en": "...", "cn": "..."}
]
```

### 2.4 生成策略优先级（补全模式）

每个词的目标：
- 覆盖率目标：至少 4 条例句，覆盖至少 3 种不同时态 × 2 种难度
- 生成顺序：按 (tense × level) 组合的数量差异排序，缺口大的先补

### 2.5 输出更新流程

1. 调用 LLM 获得 JSON 结果
2. 追加到 `examples` 数组
3. 写入 `ogden_850_words_with_ipa.json`
4. 同步更新 `words_data.js`（保持两份数据一致）

---

## Step 3 — 前端设置面板

### 3.1 UI 位置

词卡区域，voice-settings 同级下方，新增 `#exampleSettings` 面板，展开/折叠式。

### 3.2 设置项

- **例句数量**：滑块 1-5，默认 3
- **难度筛选**：5 个 checkbox，默认全选
- **时态筛选**：8 个标签按钮，多选，默认全选
- **学习模式**：单选按钮 — "随机展示" / "按难度递增" / "按时态循环"

### 3.3 存储

`localStorage` key: `words850_example_settings`

```json
{
  "count": 3,
  "levels": ["beginner","elementary","intermediate","advanced","native"],
  "tenses": ["simple_present","simple_past","simple_future"],
  "mode": "random"
}
```

### 3.4 词卡背面改版

- 翻到背面后，按设置筛选 `examples` 数组
- 多例句分页展示：底部 `◀ 1/3 ▶` 翻页控件
- 每个例句展示：EN + CN + 右上角标注 `[intermediate · simple_past]` 标签
- 每个例句右侧加 🔄 按钮（Step 5 对接）

### 3.5 浏览模式改进

- List 行中增加"例句数量"列，显示该词已有例句数（如 `3/8 tenses`）

---

## Step 4 — 补全模式实现

`example_gen.py --backfill` 执行逻辑：

1. 加载 JSON，统计每个词的 (tense, level) 覆盖矩阵
2. 定义目标：每个词至少覆盖 3 种时态 × 2 种难度 = 6 条
3. 按缺失数量降序排序单词
4. 逐词调用 LLM 批量生成缺失组合
5. 每生成 50 词自动保存一次
6. 输出补全报告：

```
Backfill complete — 850 words processed
  Total examples before: 850
  Total examples after:  5274
  Generated:  4424
  Skipped:    0
  Errors:     3  (word_042, word_218, word_633)
```

---

## Step 5 — 单例句重新生成

### 5.1 Python API 服务

文件：`api_server.py`

启动：`python3 api_server.py` → `http://localhost:5201`

端点：
- `POST /regenerate`
  ```json
  {
    "word_id": "word_001",
    "tense": "simple_past",
    "level": "intermediate",
    "old_example_id": "ex_001_05"
  }
  ```
  → 返回替换后的新例句 JSON

- `GET /health` → 心跳

内部用 `asyncio` + `httpx` 调 Ollama（避免阻塞），同步更新 JSON 文件。

### 5.2 前端对接

- 词卡背面的 🔄 按钮 → `POST /api_server/regenerate`
- 加载动画中禁用按钮
- 成功后直接替换当前显示的例句（不重新翻牌）

---

## 文件清单（新增/修改）

| 文件 | 动作 | 说明 |
|------|------|------|
| `ogden_850_words_with_ipa.json` | 修改 | 新增 `examples` 数组字段 |
| `words_data.js` | 修改 | 同步数据 |
| `index.html` | 修改 | 设置面板 + 多例句翻页 + regenerate 按钮 |
| `example_gen.py` | 新增 | LLM 生成脚本 |
| `api_server.py` | 新增 | 单例句重新生成 API |

---

## 实施顺序

```
1. 数据迁移（写迁移脚本，旧 example → examples）
2. 写 example_gen.py（核心生成逻辑）
3. 执行 --backfill 一次性补全
4. 改 index.html（设置面板 + 多例句展示）
5. 写 api_server.py（单条 regenerate）
6. 前端对接 regenerate API
```
