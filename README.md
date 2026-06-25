# Words850

Ogden 基础词汇（850词）学习工具，支持间隔重复（Leitner）、多难度/时态例句、AI 按需生成。

## 截图

<img width="944" height="667" alt="词卡" src="https://github.com/user-attachments/assets/232ea59b-ac44-4e71-ac2b-a2acb318f851" />
<img width="908" height="782" alt="进度" src="https://github.com/user-attachments/assets/bab59366-9552-408a-b955-6ca221b0790d" />

## 本地启动

### 前置要求

- Python 3.10+
- [Ollama](https://ollama.com/)（例句生成需要）
- 已拉取模型 `huihui_ai/hy-mt1.5-abliterated:latest`（或其他兼容模型）

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install httpx
```

### 2. 启动 API 服务（例句生成）

```bash
python3 api_server.py
```

默认端口 5201，模型 `huihui_ai/hy-mt1.5-abliterated:latest`。可通过环境变量覆盖：

```bash
LLM_MODEL=qwen3.5:9b LLM_API_URL=http://localhost:11434/v1/chat/completions python3 api_server.py
```

### 3. 启动前端

**方式 A — HTTP 服务器（推荐）**

```bash
python3 -m http.server 8080
```

打开浏览器访问 `http://localhost:8080`

**方式 B — 直接打开文件**

双击 `index.html` 用浏览器打开（部分浏览器可能限制 fetch 请求）。

### 4. 使用

1. 打开页面后，点击右上角 **⚙** 设置学习难度（5 级单选）和时态（8 种多选）
2. 点击"词卡"开始学习，翻转卡片查看释义
3. 若当前设置下无匹配例句，点击 **"用 AI 生成"** 按钮实时生成
4. 生成后立即持久化，后续同设置秒开

### 5. 可选：批量生成例句

```bash
# 为指定词生成
python3 example_gen.py --word word_001,word_002 --tense simple_past,simple_future --level intermediate

# 为所有词补全缺口
python3 example_gen.py --backfill

# 仅预览缺口，不调用 LLM
python3 example_gen.py --backfill --dry-run
```

### 6. 可选：TTS 音频

```bash
python3 tts_gen.py
```

需本地运行 [Kokoro TTS API](https://github.com/remsky/Kokoro-FastAPI)（端口 5200）。

## 项目结构

```
├── index.html              # 前端单页应用
├── words_data.js           # 单词数据（前端加载）
├── ogden_850_words_with_ipa.json  # 主数据源
├── api_server.py           # LLM 代理 API（按需生成）
├── example_gen.py          # 批量生成脚本
├── migrate.py              # 数据迁移工具
├── tts_gen.py              # TTS 音频生成
├── audio/                  # 音频文件
└── PLAN.md                 # 架构文档
```

## 数据格式

每条单词包含 `examples[]` 数组，支持多难度、多时态例句：

```json
{
  "id": "word_001",
  "word": "come",
  "examples": [
    { "en": "Come here.", "cn": "过来。", "tense": "simple_present", "level": "beginner" },
    { "en": "She came yesterday.", "cn": "她昨天来了。", "tense": "simple_past", "level": "elementary" }
  ]
}
```

难度：`beginner` / `elementary` / `intermediate` / `advanced` / `native`（CEFR A1→C2）

时态：`simple_present`、`present_continuous`、`present_perfect`、`simple_past`、`past_continuous`、`past_perfect`、`simple_future`、`future_continuous`
