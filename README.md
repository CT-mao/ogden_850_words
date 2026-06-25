# Words850

Ogden 基础词汇（850词）学习工具，支持间隔重复（Leitner）、多难度/时态例句、AI 按需生成。

## 截图

<img width="944" height="667" alt="词卡" src="https://github.com/user-attachments/assets/232ea59b-ac44-4e71-ac2b-a2acb318f851" />
<img width="908" height="782" alt="进度" src="https://github.com/user-attachments/assets/bab59366-9552-408a-b955-6ca221b0790d" />

## 本地启动

> 为什么不直接打开 `index.html`？
>
> 浏览器出于安全策略，`file://` 页面无法调用本地 HTTP API（CORS 拒绝）。
> `api_server.py` 同时托管前端静态文件和 AI 生成接口，一条命令搞定一切。

### 前置要求

- Python 3.10+
- [Ollama](https://ollama.com/)（例句生成需要）
- 已拉取模型（推荐 `huihui_ai/hy-mt1.5-abliterated:latest` 或其他兼容模型）

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install httpx
```

### 2. 启动（一条命令）

```bash
python3 api_server.py
```

打开浏览器访问 **http://localhost:5201** 即可。

API 和前端同端口，无需额外服务器。默认模型为 `huihui_ai/hy-mt1.5-abliterated:latest`，可通过环境变量覆盖：

```bash
LLM_MODEL=qwen3.5:9b LLM_API_URL=http://localhost:11434/v1/chat/completions python3 api_server.py
```

### 3. 使用

1. 打开 http://localhost:5201，点击右上角 **⚙** 打开设置
2. 在设置中可配置：
   - **难度**（5 级单选）和**时态**（8 种多选）
   - **大模型** — 从下拉菜单中选 Ollama 已拉取的模型（自动从本地 Ollama 获取列表）
   - **语音引擎** — 填写 TTS 接口地址（如 Kokoro `http://localhost:5200/tts`），留空则使用浏览器内置 SpeechSynthesis
3. 点击"词卡"翻转学习，词卡背面展示匹配当前设置的例句
4. 若当前设置下无例句，点击 **"用 AI 生成"** 实时调用 Ollama 生成，自动持久化
5. 设置面板随时可改，修改后立即生效

### 4. 可选：批量生成例句

```bash
# 为指定词生成例句
python3 example_gen.py --word word_001,word_002 --tense simple_past,simple_future --level intermediate

# 为所有词补全缺失的时态×难度组合
python3 example_gen.py --backfill

# 只预览缺口，不调用 LLM
python3 example_gen.py --backfill --dry-run
```

### 5. 可选：TTS 音频

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
