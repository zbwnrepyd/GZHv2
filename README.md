# AI自媒体知识卡片生产系统

一个本地运行的三段式生产工具：研究一家 AI 公司，人工定稿内容，再制作并导出 8 张知识卡片。

## 快速开始

```bash
pip install -r requirements.txt
sqlite3 db/research_db.sqlite < db/init_research_db.sql
sqlite3 db/final_db.sqlite < db/init_final_db.sql
sqlite3 db/assets_db.sqlite < db/init_assets_db.sql
cd webapp
python3 app.py
```

打开：

```text
http://127.0.0.1:5050/
```

在研究台输入公司名和官网，点击“开始研究”。研究完成后进入定稿台，按行从标准版、商业版、传播版或手写输入中选择最终文案，逐张确认 1-8 号卡片，再进入卡片制作台。研究台会显示已定稿张数/8。卡片 7 是竞争格局，卡片 8 是总结并承接赛道机遇。左侧“传播钩子文案”入口会展示三版钩子；它只供正文开头使用，不写入知识卡片。

## 环境变量

服务会读取系统环境变量，也会尝试读取项目根目录 `.env`。优先级是：系统环境变量 > 项目 `.env`。项目不读取 `~/.env`。

```bash
DEEPSEEK_API_KEY=sk-...
# Tavily 单 Key 或多 Key 二选一；多 Key 用英文逗号分隔，遇到额度限制会自动尝试下一个
TAVILY_API_KEY=tvly-...
TAVILY_API_KEYS=tvly-...,tvly-...
YOUTUBE_API_KEY=...
GOOGLE_MAPS_API_KEY=...  # 可选：Street View Static API，作为卡片2地图后的补充候选
IMAGE_API_KEY=sk-...
IMAGE_API_URL=https://api.openai.com/v1/images/generations
FLASK_PORT=5050
SCREENSHOT_PROVIDER=local
```

`YOUTUBE_API_KEY` 和图片生成相关变量可以暂时为空；对应能力会降级或在调用时失败。卡片制作台底部也可以临时输入图片 API URL 和 API Key，API Key 只随当次请求发送，不写入浏览器本地存储，也不在响应中回显。

## 目录

```text
prompts/      L0-L3 研究 Prompt 和文本分段 Prompt
webapp/       Flask 后台、编辑器 API、Python 研究流水线
image-studio/ 图片定稿台：中栏上下分区（预览/搜索切换 + 工具栏），右栏候选缩略图+确定
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

卡片制作台会从 `final_db` 读取已确认的 `markdown_full`。左侧只读显示当前项目名，并用互斥手风琴组织“卡片每一页”和“图片夹”；图片夹展示 Markdown 中已有的图片、底部生成过的图片和背景水印控件，导出按钮始终常驻。中间显示 3:4 HTML 画布，右侧显示当前页完整 HTML+CSS 源码并带语法高亮；编辑源码会实时渲染到中间画布。顶部“返回定稿台”会回到当前公司的 `/editor?company=<公司名>`。图片生成功能已整合至图片定稿台搜索面板。

图片定稿台管理 8 个 `asset_key`，其中 `positioning_charts` 先挂在卡片6用于竞争格局/生态位图定稿。卡片2 的 `office` 槽位默认生成并选中公司位置地图；Google Street View 和 Tavily 办公室/街景图会补充为后续候选。候选变体展示在中间主区域，带来源、尺寸、分数和失败原因，默认按 `final_score` 排序；右侧只放生成、重新评分、当前选定、导入/上传和 SVG 渲染操作。

批量导出 PNG 需要 Node 依赖：

```bash
npm install
node canvas/screenshot.js --company Anthropic --base-url http://127.0.0.1:5050
```

默认每张卡会导出 3 张高倍率候选图（`--shots 3 --scale 3`），文件名形如 `Anthropic_card_01_shot_01.png`。需要更少或更高倍率可改 `--shots`、`--scale`。

更多架构和运维细节见 [docs/architecture.md](docs/architecture.md) 和 [docs/runbook.md](docs/runbook.md)。
