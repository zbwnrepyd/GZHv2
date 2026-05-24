# AI自媒体知识卡片生产系统

一个本地运行的三段式生产工具：研究一家 AI 公司，人工定稿内容，再导出 7 张知识卡片。

## 快速开始

```bash
pip install -r requirements.txt
sqlite3 db/research_db.sqlite < db/init_research_db.sql
sqlite3 db/final_db.sqlite < db/init_final_db.sql
cd webapp
python3 app.py
```

打开：

```text
http://127.0.0.1:5050/editor/
```

在页面顶部输入公司名和官网，点击“开始研究”。研究完成后选择三种版本中的字段，逐张确认 1-7 号卡片，再导出 Markdown。

## 环境变量

服务会读取系统环境变量，也会尝试读取 `~/.env`。

```bash
DEEPSEEK_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
YOUTUBE_API_KEY=...
IMAGE_API_KEY=sk-...
IMAGE_API_URL=https://api.openai.com/v1/images/generations
FLASK_PORT=5050
```

`YOUTUBE_API_KEY` 和图片生成相关变量可以暂时为空；对应能力会降级或在调用时失败。

## 目录

```text
prompts/      L0-L3 研究 Prompt 和文本分段 Prompt
webapp/       Flask 后台、编辑器 API、Python 研究流水线
canvas/       fabric.js 静态卡片渲染器
db/           SQLite schema 和本地数据库
tests/        unittest 回归测试
```

## 常用命令

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile webapp/*.py
```

命令行启动一次研究：

```bash
curl -X POST http://127.0.0.1:5050/api/research/start \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Anthropic","company_url":"https://www.anthropic.com"}'
```

查询进度：

```bash
curl http://127.0.0.1:5050/api/research/status/<job_id>
```

更多架构和运维细节见 [docs/architecture.md](docs/architecture.md) 和 [docs/runbook.md](docs/runbook.md)。
