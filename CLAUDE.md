# AI自媒体知识卡片生产系统

## 项目概述
三模块流水线系统：Python研究流水线 → 内容定稿（Flask）→ 知识卡片制作（HTML/CSS画布）

## 目录约定

```
prompts/        — 4层LLM Prompt文件（layer0-3）和分段Prompt
webapp/         — Flask编辑后台 + 研究流水线（app.py入口）
image-studio/   — 图片定稿台（三栏：槽位总览 | 中间搜索+候选变体 | 右侧操作/导入），通过 iframe 嵌入定稿台
canvas/         — HTML/CSS卡片制作台、单卡页面、Puppeteer截图脚本
db/             — SQLite建表SQL和数据库文件
tests/          — unittest 回归测试
```

## 日常操作

### 启动服务
```bash
pip install -r requirements.txt
cd webapp && python3 app.py
# 访问研究台 http://127.0.0.1:5050/
# 定稿台 http://127.0.0.1:5050/editor?company=<公司名>
# 卡片制作台 http://127.0.0.1:5050/canvas/?company=<公司名>
```

### 研究一家公司
```bash
curl -X POST http://127.0.0.1:5050/api/research/start \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Anthropic","company_url":"https://www.anthropic.com"}'
# 返回 {"job_id":"abc123","status":"running"}
```

### 查询研究进度
```bash
curl http://127.0.0.1:5050/api/research/status/<job_id>
```

### 验证
```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile webapp/*.py
node canvas/screenshot.js --help
```

### 初始化数据库
```bash
sqlite3 db/research_db.sqlite < db/init_research_db.sql
sqlite3 db/final_db.sqlite < db/init_final_db.sql
sqlite3 db/assets_db.sqlite < db/init_assets_db.sql
```

## 技术约束
- 所有LLM调用使用DeepSeek V4 Pro
- 前端不用React/Vue，Vanilla JS + CDN
- `canvas/` 主路径不用 fabric.js；使用 HTML/CSS 源码编辑器 + iframe 预览，右侧展示当前页完整 HTML+CSS 并实时渲染
- 卡片制作台左侧公司名是只读项目状态，来自定稿台跳转或 `?company=<公司名>`；不要恢复可输入公司名框
- 左侧“卡片每一页”和“图片夹”是互斥手风琴，长内容在各自面板内滚动；背景水印控件放在图片夹内，导出按钮保持常驻，不放进折叠区
- 卡片制作台返回按钮应回到当前公司的定稿台 `/editor?company=<公司名>`；研究台定稿进度以 8 张为总数
- 数据库用sqlite3标准库，不用ORM
- 网页抓取用本地 trafilatura（`webapp/firecrawl_local.py`），不依赖外部 API
- 环境变量只读取系统环境变量和项目根目录 `.env`；不要读取或恢复用户目录 `~/.env`
- Tavily 可用 `TAVILY_API_KEYS` 配置逗号分隔的多 Key，额度限制时自动尝试下一个；不要把真实 Key 写进代码、测试、文档或日志
- 成本目标 < $0.20/次研究
- 生成 1-8 号卡片；卡片7为竞争格局（壁垒、竞争格局），卡片8为总结（机遇）
- 研究主流程不依赖 n8n；不要新增 n8n 工作流作为主路径
- 定稿台是四列逐行选择：标准版、商业版、传播版、定稿输入；不要恢复旧字段级编辑器作为主路径
- `hook_paragraph_1/2/3` 只在左侧“传播钩子文案”入口展示，不写入知识卡片，也不参与卡片确认保存
- `final_content` 以 `company_name + card_index + field_name` 作为唯一字段键，重复确认应更新而非插入
- 定稿保存优先使用 `field_name='markdown_full'` 的整张 Markdown
- canvas Markdown 解析必须保留远程/本地 Markdown 图片 URL，并兼容首页、公司介绍、主产品里的无标签正文
- L3 任一版本字段提取失败时，任务应失败且不写入假成功记录
- 创始人 `founder_edu/founder_achievement` 缺失修复属于 L3 主流程内重试，不要恢复后置补抓流程
- 图片 API Key 可通过环境变量配置，也可在图片定稿台搜索面板 AI 生图时随请求发送；临时 Key 不写入 localStorage 或响应
- 公司图片资产通过 `company_assets` 表管理（7 种 asset_key），不用路径约定或 localStorage；资产采集走 `asset_pipeline.py`，信息图（飞轮/时间线）走 `infographic.py` 的 SVG 模板渲染管线
- 卡片2 `office` 槽位默认使用公司位置地图：OSM 瓦片本地拼接 + HTML pin/legend 生成 PNG，并默认选中；Google Street View/Tavily 办公室图只作为后续候选变体，不抢默认选中
- 图片定稿台候选变体必须展示在中间主区域；右侧栏只放操作、当前选定、导入/上传和 SVG 渲染按钮
- 本地 Python SVG 模板上传只允许本机请求并要求 `X-Template-Upload-Intent: local-dev`；不要开放远程上传
- 飞轮/时间线 SVG 信息图在卡片定稿确认时自动生成（卡片3=时间线，卡片6=飞轮）；也可在图片定稿台手动调参渲染；SVG 渲染需要 Playwright
- 国内环境访问 Tavily 和 YouTube API 需配 HTTPS_PROXY（`config.py` 不自动设置代理，需在 `.env` 手动配置）
- Pexels（200 req/h，支持中文）和 Unsplash（50 req/h，英文关键词）API Key 通过环境变量配置，用于图片定稿台手动搜索
- 图片自动采集不再使用 Lorem Flickr / Picsum 通用图；搜不到真实图片时标记 `failed`，进入图片定稿台手动补
- 定稿台左侧为三区手风琴：内容定稿（卡片1-8）、传播钩子文案、图片定稿（iframe 嵌入 image-studio，embed 模式隐藏顶栏和槽位面板，槽位列表在左手风琴内渲染）
- 研究台要展示 Tavily/GitHub/YouTube/官网抓取的链路状态与数量；公司库点击一条只展开该公司研究信息，点另一条时其他行折叠

## 参考
- 新人入口：`README.md`
- 架构说明：`docs/architecture.md`
- 运行手册：`docs/runbook.md`
