# 解耦架构审查 — 2026-06-04

> Trigger: superpower code review. 结论：架构骨架已搭，旧主链路未替换。

## 核心判断

**现在代码已经有"解耦架构的外形"，但还没有形成"解耦生产流程"。**

当前完成度：
- 数据模型方向：70%
- 字段解耦：40%
- 图片解耦：50%
- 卡片自由编排：45%
- 文字定稿新流程：40%
- 图片定稿新流程：35%
- ECharts 生成图：20%
- 排版界面：45%
- 导出：55%

## 最该先修的 7 个点

### 1. pipeline 写入 `research_fields`（P0）
**第一优先级。**
```python
# pipeline.py 写完 research 宽表后
from services.field_service import split_research_to_fields
from repositories.field_repo import insert_research_fields_batch
```
否则字段定稿页没有稳定数据来源。

### 2. 降级旧的"内容定稿 1-8 张卡"（P0）
旧的内容定稿保留为兼容入口，主流程切到：
```
字段定稿 → 卡片设置 → 图片定稿 → 排版
```
`/api/final/save` 不再作为主路径。

### 3. 卡片设置补完整编辑（P1）
当前只支持新增和删除。需补：
- 修改卡名、序号、启用/禁用
- 修改字段、图片、顺序、display_role
- 已有卡片的编辑界面（当前只有 `alert('拖拽排序在排版界面完成')`）

### 4. 图片定稿 UI 收窄（P1）
一级按钮只保留：预览、重新采集、上传、确认
搜索、URL 导入、重新评分、AI 生图 → 高级面板

### 5. ECharts 工作台单独做（P1）
不要继续混在 SVG 渲染里。至少需要：
```
GET  /api/charts/<company>/<media_key>/data
POST /api/charts/<company>/<media_key>/preview
POST /api/charts/<company>/<media_key>/render
POST /api/charts/<company>/<media_key>/save
```
ECharts option 编辑、参数面板、实时预览、渲染 PNG、候选保存、确认定稿。

### 6. 修 TemplateRenderer 多图绑定（P2）
`multi_chart` 模板有两个 chart region，但 renderer 对同一 role 只取第一个 media item：
```js
const media = mediaItems[0]; // BUG: 永远取第一个
```
修复：region 支持 `bind` 字段精确匹配 `media_key`，再按 role fallback。

### 7. 导出改成弹窗（P2）
不要按钮直接导出当前卡。弹窗字段：
- 导出范围（当前/全部/自定义）
- 格式（PNG/ZIP）
- 倍率
- 确认下载

## 已完成的部分

- ✅ 新数据模型：card_compositions, card_items, default_card_configs
- ✅ 字段/图片契约：contracts/fields.json, contracts/media.json
- ✅ 新 API 框架：card_config, field, render_data, media Blueprint
- ✅ 排版界面雏形：卡片列表、模板选择、图层列表、属性面板
- ✅ 模板制作界面：画布尺寸、背景、文字/图片/形状区域、角色绑定
- ✅ 导出服务基础：多文件 ZIP、card_ids、format、scale

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
