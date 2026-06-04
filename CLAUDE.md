# AI自媒体知识卡片生产系统

## 项目概述
三模块流水线系统：Python研究流水线 → 内容定稿（Flask）→ 知识卡片制作（HTML/CSS画布）

## 目录约定

```
prompts/        — LLM Prompt文件（layer0-3 + layer3-group-a/b/c 三组枚举提取）
webapp/         — Flask编辑后台 + 研究流水线（app.py入口）
image-studio/   — 图片定稿台（三栏），通过 iframe 嵌入定稿台
canvas/         — HTML/CSS卡片制作台、单卡页面、Puppeteer截图脚本
db/             — SQLite建表SQL和数据库文件
tests/          — unittest 回归测试
```

## 日常操作

### 启动服务
```bash
pip install -r requirements.txt
cd webapp && python3 app.py
# Flask 已配置 TEMPLATES_AUTO_RELOAD=True，模板修改后无需重启
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
- CSS 共享设计系统在 `webapp/static/css/gzh2-base.css`（变量、顶栏、按钮、面板布局）；`editor.css` 只定义研究台/定稿台专属样式，不重复定义 :root 变量和 .btn 基类；image-studio 使用独立的 `studio.css`（变量名不同但颜色值对齐）
- `canvas/` 主路径不用 fabric.js；使用 HTML/CSS 源码编辑器 + iframe 预览，右侧展示当前页完整 HTML+CSS 并实时渲染。左侧含模板系统（全局共享，`localStorage` key `aistartups.templates`，默认模板 JSON 在 `canvas/default-templates.json`）
- 卡片制作台左侧公司名是只读项目状态，来自定稿台跳转或 `?company=<公司名>`；不要恢复可输入公司名框
- 左侧“卡片每一页”和“图片夹”是互斥手风琴，长内容在各自面板内滚动；背景水印控件放在图片夹内，导出按钮保持常驻，不放进折叠区
- 卡片制作台返回按钮应回到当前公司的定稿台 `/editor?company=<公司名>`；研究台定稿进度以 8 张为总数
- 数据库用sqlite3标准库，不用ORM
- 网页抓取用本地 trafilatura（`webapp/firecrawl_local.py`），不依赖外部 API
- 环境变量只读取系统环境变量和项目根目录 `.env`；不要读取或恢复用户目录 `~/.env`
- Tavily 可用 `TAVILY_API_KEYS` 配置逗号分隔的多 Key，额度限制时自动尝试下一个；不要把真实 Key 写进代码、测试、文档或日志
- 成本目标 < $0.20/次研究
- 生成 1-8 号卡片；卡片7为竞争格局（壁垒 + 生态位分析 + 竞品列表），卡片8为总结（机遇）。L3 prompt 已将壁垒 `moat` 和生态位 `ecosystem_niche` 拆为独立字段；markdown_builder 对旧数据自动拆分
- 研究主流程不依赖 n8n；不要新增 n8n 工作流作为主路径
- 定稿台是四列逐行选择：标准版、商业版、传播版、定稿输入；不要恢复旧字段级编辑器作为主路径
- `hook_paragraph_1/2/3` 只在左侧“传播钩子文案”入口展示，不写入知识卡片，也不参与卡片确认保存
- `final_content` 以 `company_name + card_index + field_name` 作为唯一字段键，重复确认应更新而非插入
- 定稿保存优先使用 `field_name='markdown_full'` 的整张 Markdown
- canvas Markdown 解析必须保留远程/本地 Markdown 图片 URL，并兼容首页、公司介绍、主产品里的无标签正文
- L3 任一版本字段提取失败时，任务应失败且不写入假成功记录
- L3 枚举字段（10个竞争评分维度）改三层解耦：规则层 `field_rules.py`（爬 pricing 页+关键词推断）→ LLM 拆为3组独立调用（prompts/layer3-group-a/b/c）→ Pydantic 验证 `field_validator.py`；关键字段多数投票。不改动 L3 主调用的 45 个非枚举字段提取
- 创始人 `founder_edu/founder_achievement` 缺失修复属于 L3 主流程内重试，不要恢复后置补抓流程
- 图片 API Key 可通过环境变量配置，也可在图片定稿台搜索面板 AI 生图时随请求发送；临时 Key 不写入 localStorage 或响应
- 公司图片资产通过 `company_assets` 表管理（8 种 asset_key，含卡片6 `positioning_charts` 竞争/生态位图槽位），不用路径约定或 localStorage。采集统一走 `collect_image_variants_pipeline`（含官网首页截图 candidate，不抢 OSM 默认）。信息图（飞轮/时间线/散点图）走 `infographic.py`：飞轮/时间线用 SVG 模板渲染，散点图用 Frappe Charts CDN 渲染为 HTML 再 Playwright 截图（2x scale 高清）
- 自动图片采集必须走候选池：下载后用 `image_quality.py` 检测、`image_scorer.py` 评分，写入尺寸/分数/失败原因；Tavily 不允许取第一张直接当最终图
- 卡片2 `office` 槽位默认使用公司位置地图：OSM 瓦片本地拼接 + HTML pin/legend 生成 PNG，并默认选中；Google Street View/Tavily 办公室图只作为后续候选变体，不抢默认选中
- 图片定稿台两类槽位两种界面：①采集图片类（logo/office/product/competitors）→ 三栏布局，中间栏上部预览/搜索切换 + 下部工具栏（搜索/采集/AI生图/上传）；②图表类（flywheel/timeline/positioning_charts）→ 中间栏 iframe 实时预览（Frappe Charts / SVG）+ 下部功能区 bar（调参+重置+渲染保存），无搜索框
- 本地 Python SVG 模板上传只允许本机请求并要求 `X-Template-Upload-Intent: local-dev`；不要开放远程上传
- 飞轮/时间线 SVG 在卡片定稿确认时自动生成（卡片3=时间线，卡片6=飞轮+散点图）；也可在图片定稿台手动调参渲染；SVG 渲染需要 Playwright
- 卡片制作台中间栏下方可展开参数调节 bar（手风琴式，单段展开）：排版/颜色/间距/布局滑块，实时注入 iframe 预览；参数持久化 localStorage key `aistartups.paramTuning`
- iframe 内文字始终可双击编辑（Enter 完成，Escape 取消），自动保存到 SourceEditor
- 国内环境访问 Tavily 和 YouTube API 需配 HTTPS_PROXY（在 `.env` 手动配置）。Tavily 使用显式 `proxies=` 传参并支持超时后换 Key；超时配置在 `pipeline.py`
- Pexels（200 req/h，支持中文）和 Unsplash（50 req/h，英文关键词）API Key 通过环境变量配置，用于图片定稿台手动搜索
- 图片自动采集不再使用 Lorem Flickr / Picsum 通用图；搜不到真实图片时标记 `failed`，进入图片定稿台手动补
- 定稿台左侧为六区手风琴：卡片设置、字段定稿、内容定稿（卡片1-8）、传播钩子文案、数据库字段、图片定稿（iframe 嵌入 image-studio）。每个面板点击后占据中右全区域，互斥切换。卡片设置/字段定稿内容渲染在中右 overlay 容器内，不在左侧手风琴 body
- 研究台要展示 Tavily/GitHub/YouTube/官网抓取的链路状态与数量；公司库点击一条只展开该公司研究信息，点另一条时其他行折叠

## 参考
- 新人入口：`README.md`
- 架构说明：`docs/architecture.md`
- 运行手册：`docs/runbook.md`
