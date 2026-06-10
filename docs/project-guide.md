# 项目指南

新人入口文档。读完这份文档 + 跑通一次研究 = 理解整个系统。

## 一句话

输入公司名 + 官网 URL → 自动研究 → 人工定稿 → 输出 v1 8 张或 v2 7 张 3:4 知识卡片 PNG。

## 快速理解（5 分钟）

### 这是一条流水线，三个工作台

```
研究台(/) → 定稿台(/editor) → 卡片制作台(/canvas) / 排版中心(/layout) → 导出 PNG
```

1. **研究台** `http://127.0.0.1:5050/` — 输入公司名和官网，点「开始研究」。后台跑 4 路数据采集 + 4 层 LLM 分析 + 自动图片收集
2. **定稿台** `http://127.0.0.1:5050/editor?company=<公司名>&set=v1|v2` — 顶部切换套卡→卡片设置→文字定稿→图片定稿，左栏底部固定「进入排版」
3. **卡片制作台** `http://127.0.0.1:5050/canvas/?company=<公司名>` — HTML/CSS 卡片编辑和预览
4. **排版中心** `http://127.0.0.1:5050/layout?company=<公司名>&set=v1|v2` — 选模板、调图层、改文字位置和样式

### 研究工作流

```
Step 1: 4路并行采集
  Tavily 多意图搜索(覆盖 overview/founders/funding/product 等 11+ 意图) + GitHub 仓库 + YouTube 创始人视频 + 官网抓取(trafilatura)
  → 4线程并行，每路独立上报状态

Step 2: 4层 LLM 分析
  L0 信息清洗 → L1 横纵分析 → L2 商业结构 → L3 字段提取(3版本)

Step 3: 评分 + 写入
  枚举字段三层管道(规则层→LLM三组→Pydantic验证) → 加权评分 → research 表

Step 4: 自动图片采集
  Logo/Office/Product/Competitors 多源候选 → 质量检测 → 评分 → image_variants 候选池
```

### 定稿流程

```
卡片设置 → 文字定稿 → 图片定稿 → 进入排版
(卡片数量/内容可自由编排)   (11种素材槽位)
```

### 默认卡片（双套卡）

**v1 经典 8 张：**

| 卡片 | 主题 |
|---|---|
| card_1 | 首页：公司名、类型、核心定位 |
| card_2 | 公司介绍：位置、创始人、团队、融资 |
| card_3 | 发展沿袭：时间线 |
| card_4 | 主产品：产品名、定义、亮点、成就 |
| card_5 | 其他产品：产品矩阵 |
| card_6 | 商业模式：盈利、GTM、冷启动、飞轮 |
| card_7 | 竞争格局：壁垒、竞品、生态位 + 2张评分散点图 |
| card_8 | 总结：赛道机会 |

**v2 新版 7 张：**

| 卡片 | 主题 |
|---|---|
| card_1 | 封面：公司名、Logo |
| card_2 | 公司概览：官网截图、地址、行业、主营业务、成就 |
| card_3 | 产品与定位：生态位图、主产品、技术栈 |
| card_4 | 创始人与团队：创始人照片、背景、团队规模 |
| card_5 | 财务与市场：客户、营收/增长指标、融资 |
| card_6 | GTM 与增长：GTM 策略、增长飞轮 |
| card_7 | 竞争格局：竞争格局图、Top3 竞品、壁垒 |

## 关键架构决策

### 模板渲染而非画布拖拽

卡片不使用 fabric.js 画布拖拽。每张卡是一个 HTML/CSS 模板，在 `900 × 1200` 的 3:4 画布中渲染。模板按 `display_role`（title/body/image/badge）绑定内容区域，不按字段名绑定。`canvas/js/template-renderer.js` 是核心渲染引擎。

### 图片定稿：槽位模式

图片不在卡片制作台处理，而是在专门的图片定稿台（`image-studio/`）中按 11 种 `asset_key` 管理。两类槽位：

- **采集图片类**（logo/office/product/competitors 等）→ 三栏布局：左槽位列表，中预览+搜索+工具栏，右候选缩略图
- **图表类**（flywheel/timeline/chart_competitive/chart_ecosystem）→ 中间 iframe 实时预览 + 底部参数调节 + 右侧代码/操作面板

### 5 个 SQLite 数据库

| 数据库 | 职责 |
|---|---|
| `research_db` | 研究原始数据（宽表 60+ 字段）+ 评分 + 任务状态 |
| `final_db` | 人工定稿字段（按 company+field_key 唯一） |
| `assets_db` | 图片素材槽位 + 候选池 |
| `composition_db` | 卡片编排（每张卡有哪些字段/图片） |
| `template_db` | 模板定义 + 排版实例 |

### 研究数据的三版本

每次研究生成 3 个版本：

- **standard** — 标准版：客观完整，数据优先，适合事实核查
- **business** — 商业版：投资人视角，突出商业潜力和竞争分析
- **spread** — 传播版：高钩子密度，自媒体友好，金句化表达

### 评分体系

10 个枚举字段 → 加权公式 → 3 个 0–10 评分 → 2 张 ECharts 散点图。ECharts 使用 `webapp/static/vendor/echarts.min.js` 本地 runtime，预览和 Playwright 截图不依赖外部 CDN。详见 [docs/scoring-system.md](scoring-system.md)。

## 深入文档

| 文档 | 内容 |
|---|---|
| [README.md](../README.md) | 安装、启动、常用命令 |
| [docs/architecture.md](architecture.md) | 系统架构、数据模型、路由清单 |
| [docs/runbook.md](runbook.md) | 运维手册：冒烟测试、故障排查、API 示例 |
| [docs/card-spec.md](card-spec.md) | 卡片和图片资产规范 |
| [docs/scoring-system.md](scoring-system.md) | 评分体系完整说明 |
| [docs/decoupled-architecture-review.md](decoupled-architecture-review.md) | 解耦架构审查记录 |

## 目录约定

```
prompts/              LLM Prompt 文件（L0-L3 + L3 三组枚举提取）
webapp/               Flask 后台 + 研究流水线
  app.py              主入口（路由 + 资产 API + 渲染）
  pipeline.py          研究流水线
  competitive_scoring.py  评分计算
  field_rules.py       Layer 1 规则层
  field_validator.py   Layer 3 Pydantic 验证
  infographic.py       ECharts/SVG 图表渲染
  asset_pipeline.py    自动图片采集
  path_safety.py        公司名/图片路径片段安全清理
  routes/              Blueprint 路由模块
  services/            业务逻辑层
  repositories/        数据访问层
image-studio/          图片定稿台（独立 HTML + JS/CSS）
canvas/                卡片制作台 + Puppeteer 截图脚本
db/                    SQLite schema + 迁移
  migrate.py            幂等迁移运行器（schema_migrations）
tests/                 14 个 unittest 测试文件
output/                导出输出（卡片 PNG、调试报告）
```

## 第一次上手

```bash
# 1. 安装
pip install -r requirements.txt
npm install

# 2. 初始化数据库
sqlite3 db/research_db.sqlite < db/init_research_db.sql
sqlite3 db/final_db.sqlite < db/init_final_db.sql
sqlite3 db/assets_db.sqlite < db/init_assets_db.sql
python3 db/migrate.py db/research_db.sqlite --only 001_research_fields.sql
python3 db/migrate.py db/final_db.sqlite --only 002_final_fields.sql

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 和 TAVILY_API_KEY

# 4. 启动
cd webapp && python3 app.py

# 5. 研究一家公司
curl -X POST http://127.0.0.1:5050/api/research/start \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Anthropic","company_url":"https://www.anthropic.com"}'

# 6. 在浏览器打开定稿台
open "http://127.0.0.1:5050/editor?company=Anthropic"

# 7. 导出卡片 PNG
node canvas/screenshot.js --company Anthropic --base-url http://127.0.0.1:5050
```
