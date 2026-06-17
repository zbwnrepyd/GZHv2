# 解耦架构审查 — 2026-06-04（2026-06-06 更新）

> Trigger: superpower code review. 结论：架构骨架已搭，旧主链路已替换。

## 核心判断

**解耦生产流程已成型。** 主链路从研究→字段定稿→卡片编排→图片定稿→排版→导出已全部打通。

当前完成度（2026-06-06 更新）：
- 数据模型方向：100% ✅
- 字段解耦：90% ✅（final_fields 按 (company, field_key) 唯一，三版本切换 + 枚举三层管道）
- 图片解耦：90% ✅（11 种 asset_key，候选池 + 评分 + 图片/图表双模式工作台）
- 卡片自由编排：85% ✅（card_compositions + card_items，卡片设置面板可自由增减）
- 文字定稿新流程：95% ✅（旧版内容定稿/钩子文案/数据库字段面板已删除，主流程走卡片设置→文字定稿→图片定稿→排版）
- 图片定稿新流程：90% ✅（图片槽三栏布局 + 图表槽 ECharts 实时预览，嵌入编辑器和独立页面双模式）
- ECharts 生成图：95% ✅（chart_competitive/chart_ecosystem 走独立 workspace，ECharts 代码编辑 + 实时预览 + 参数调节；渲染路径内联本地 ECharts runtime）
- 排版界面：80% ✅（图层选择 + 属性面板 + Markdown 文字编辑 + layout overrides 持久化）
- 导出：90% ✅（排版中心导出弹窗 + render-data API + template-renderer + Puppeteer 批量截图）

## 最该先修的 7 个点（2026-06-06 状态更新）

### 1. pipeline 写入 `research_fields`（P0）✅ 已完成
已通过 `field_service.py` + 三层枚举管道写入 research 宽表。枚举字段走三层解耦（规则层 → LLM 三组 → Pydantic 验证），评分自动计算。

### 2. 降级旧的"内容定稿 1-8 张卡"（P0）✅ 已完成
旧版内容定稿、钩子文案、数据库字段面板已删除。主流程：卡片设置 → 文字定稿 → 图片定稿 → 进入排版。

### 3. 卡片设置补完整编辑（P1）⚠️ 部分完成
当前支持新增、删除、修改卡名、启用/禁用。拖拽排序和 display_role 编辑在排版界面完成。

### 4. 图片定稿 UI 收窄（P1）✅ 已完成
图片槽：预览/搜索切换 + 工具栏（搜索/采集/AI生图/上传/URL导入）。图表槽：ECharts iframe 实时预览 + 参数调节 bar + 代码编辑面板 + 确定按钮。

### 5. ECharts 工作台单独做（P1）✅ 已完成
chart_competitive / chart_ecosystem 使用独立 WorkspaceChart 控制器，HTML 代码编辑 + 语法高亮 + 实时预览 + 参数面板 + 渲染 PNG + 确定定稿。不混在 SVG 渲染路径。

### 6. 修 TemplateRenderer 多图绑定（P2）✅ 已完成
`canvas/js/template-renderer.js` 会优先用 region `bind` 精确匹配 `item_key`，同一 role 下的多个 chart/image region 不再重复取第一张 media item。

### 7. 导出改成弹窗（P2）✅ 已完成
排版中心已提供导出弹窗，可选择范围、格式和倍率并通过 `/api/export/<company>` 启动异步导出。命令行 `node canvas/screenshot.js --company <公司> --set v1|v2|v3` 仍保留为批量截图和自动化验证路径。

## 已完成的部分

- ✅ 新数据模型：card_compositions, card_items, default_card_configs
- ✅ 字段/图片契约：contracts/fields.json, contracts/media.json
- ✅ 新 API 框架：card_config, field, render_data, media Blueprint
- ✅ 排版界面雏形：卡片列表、模板选择、图层列表、属性面板
- ✅ 模板制作界面：画布尺寸、背景、文字/图片/形状区域、角色绑定
- ✅ 导出服务基础：多文件 ZIP、card_ids、format、scale、card_set_key

## 目标链路

```
pipeline
→ research_fields
→ final_fields
→ card_items
→ render-data
→ template-renderer
→ export
```
