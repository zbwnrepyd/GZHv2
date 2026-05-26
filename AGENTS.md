# AI自媒体知识卡片生产系统

## 项目概述
三模块流水线系统：Python研究流水线 → 内容定稿（Flask）→ 知识卡片制作（HTML/CSS画布）

## 目录约定

```
prompts/      — 4层LLM Prompt文件（layer0-3）和分段Prompt
webapp/       — Flask编辑后台 + 研究流水线（app.py入口）
canvas/       — HTML/CSS卡片制作台、单卡页面、Puppeteer截图脚本
db/           — SQLite建表SQL和数据库文件
tests/        — unittest 回归测试
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
```

## 技术约束
- 所有LLM调用使用DeepSeek V4 Pro
- 前端不用React/Vue，Vanilla JS + CDN
- `canvas/` 主路径不用 fabric.js；使用 HTML/CSS 源码编辑器 + iframe 预览，右侧展示当前页完整 HTML+CSS 并实时渲染
- 数据库用sqlite3标准库，不用ORM
- 网页抓取用本地 trafilatura（`webapp/firecrawl_local.py`），不依赖外部 API
- 成本目标 < $0.20/次研究
- 不生成卡片8
- 研究主流程不依赖 n8n；不要新增 n8n 工作流作为主路径
- 定稿台是四列逐行选择：标准版、商业版、传播版、定稿输入；不要恢复旧字段级编辑器作为主路径
- `hook_paragraph_1/2/3` 只在左侧“传播钩子文案”入口展示，不写入卡片8，也不参与卡片确认保存
- `final_content` 以 `company_name + card_index + field_name` 作为唯一字段键，重复确认应更新而非插入
- 定稿保存优先使用 `field_name='markdown_full'` 的整张 Markdown
- L3 任一版本字段提取失败时，任务应失败且不写入假成功记录
- 图片 API Key 可通过环境变量配置，也可在卡片制作台临时输入；临时 Key 只随 `/api/generate-image` 请求发送，不写入 localStorage 或响应

## 参考
- 新人入口：`README.md`
- 架构说明：`docs/architecture.md`
- 运行手册：`docs/runbook.md`
- 技术文档：aistartups_tech_doc.docx
