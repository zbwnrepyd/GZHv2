# AI自媒体知识卡片生产系统

一个本地运行的三段式生产工具：研究一家 AI 公司，人工定稿内容，再制作并导出 8 张知识卡片。

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
http://127.0.0.1:5050/
```

在研究台输入公司名和官网，点击“开始研究”。研究完成后进入定稿台，按行从标准版、商业版、传播版或手写输入中选择最终文案，逐张确认 1-8 号卡片，再进入卡片制作台。研究台会显示已定稿张数/8。卡片 7 是竞争格局，卡片 8 是总结并承接赛道机遇。左侧“传播钩子文案”入口会展示三版钩子；它只供正文开头使用，不写入知识卡片。

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

`YOUTUBE_API_KEY` 和图片生成相关变量可以暂时为空；对应能力会降级或在调用时失败。卡片制作台底部也可以临时输入图片 API URL 和 API Key，API Key 只随当次请求发送，不写入浏览器本地存储，也不在响应中回显。

## 目录

```text
prompts/      L0-L3 研究 Prompt 和文本分段 Prompt
webapp/       Flask 后台、编辑器 API、Python 研究流水线
canvas/       HTML/CSS 卡片制作台、单卡页面和 Puppeteer 截图脚本
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

进入某公司的定稿台：

```text
http://127.0.0.1:5050/editor?company=Anthropic
```

进入卡片制作台：

```text
http://127.0.0.1:5050/canvas/?company=Anthropic
```

卡片制作台会从 `final_db` 读取已确认的 `markdown_full`。左侧只读显示当前项目名，并用互斥手风琴组织“卡片每一页”和“图片夹”；图片夹展示 Markdown 中已有的图片、底部生成过的图片和背景水印控件，导出按钮始终常驻。中间显示 3:4 HTML 画布，右侧显示当前页完整 HTML+CSS 源码并带语法高亮；编辑源码会实时渲染到中间画布。顶部“返回定稿台”会回到当前公司的 `/editor?company=<公司名>`。底部可以编辑图片提示词，并可临时配置图片 API URL / API Key 生成当前页插图。

批量导出 PNG 需要 Node 依赖：

```bash
npm install
node canvas/screenshot.js --company Anthropic --base-url http://127.0.0.1:5050
```

更多架构和运维细节见 [docs/architecture.md](docs/architecture.md) 和 [docs/runbook.md](docs/runbook.md)。
