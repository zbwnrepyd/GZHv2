# 知识卡片 HTML 生成器技术方案

日期：2026-05-27

## 1. 背景

当前项目的卡片制作模块位于 `canvas/`，主实现依赖 `fabric.js`：

- `canvas/card-renderer.html`
- `canvas/js/card-layout.js`
- `canvas/js/fabric-renderer.js`
- `canvas/js/markdown-parser.js`
- `canvas/js/api-loader.js`
- `canvas/js/export.js`
- `canvas/js/thumbnail-nav.js`

现有方案能从 `final_db` 读取定稿 Markdown 并绘制到 canvas，但在中文排版、字体控制、复杂布局、图片容器样式、截图一致性上维护成本较高。

本次改造目标是将 `canvas/` 推翻重建为 HTML/CSS 卡片制作台，用浏览器原生排版完成卡片渲染，再用 Puppeteer 批量截图导出 PNG。

## 2. 目标

1. 使用 HTML/CSS 渲染知识卡片，不再使用 `fabric.js` 作为主路径。
2. 卡片比例固定为 3:4 竖版，默认基准尺寸为 `900 x 1200`。
3. 视觉风格为极简白底，顶部章节导航显示多个栏目，当前页加粗。
4. 去掉底部 `aistartups` 标识。
5. 插图区使用克制的 iOS 毛玻璃边框。
6. 画布下方增加图片 prompt bar，可编辑每页预设提示词并调用图片 API。
7. 增加 HTML+CSS 源码编辑器，用户可直接编辑当前页完整 `<style> + <article>` 并实时渲染。
8. 中间画布必须完整展示，左右工具栏收窄。
9. 支持 Puppeteer CLI 批量导出数据库版本 PNG；浏览器内源码改动保存在本机 `localStorage`。

## 3. 非目标

1. 不做自由拖拽式设计器。
2. 不引入 React/Vue。
3. 不新增 n8n 工作流。
4. 不恢复旧字段级编辑器作为主路径。
5. 不新增外部图片生成供应商；第一版复用项目现有 `/api/generate-image`。
6. 不生成卡片 8。

## 4. 推荐架构

```text
研究流水线
  -> SQLite research_db
  -> 定稿台四列逐行选择
  -> final_db markdown_full
  -> /canvas/?company=<公司名>
  -> HTML/CSS 单卡 iframe 预览
  -> 图片 prompt bar 调用 /api/generate-image
  -> HTML+CSS 源码编辑器实时渲染预览
  -> Puppeteer 截图导出 PNG
```

主路径继续从定稿台进入：

```text
/editor?company=Anthropic
  -> 确认 1-7 张卡片
  -> 点击“去制作卡片”
  -> /canvas/?company=Anthropic
```

## 5. 页面布局

`/canvas/?company=<company>` 重写为三栏布局：

```text
┌──────────────┬──────────────────────────────────────┬────────────────┐
│ 左栏 210     │ 中间画布优先完整展示                  │ 右栏 520       │
│              │                                      │                │
│ 卡片 1-7     │ 顶部：当前卡片名 + 适配窗口 + 导出    │ HTML+CSS源码   │
│ 确认状态     │ 中部：3:4 HTML 卡片 iframe            │ 语法高亮/保存  │
│ 导出入口     │ 底部：图片 prompt bar                 │ 当前页/全部    │
└──────────────┴──────────────────────────────────────┴────────────────┘
```

布局要求：

- 左栏只放必要导航，避免挤占画布。
- 中间区域默认 `fit-to-window`，保证完整卡片可见。
- 右栏不是滑块 UI，而是当前页完整 HTML+CSS 源码编辑器，带本地语法高亮。
- 右栏可折叠；折叠后中间画布自动扩展。

## 6. 单张卡片结构

每张卡片由 HTML/CSS 组成，不使用 canvas 绘制文本。

```html
<article class="knowledge-card card-index-6">
  <header class="card-nav">
    <span>首页</span>
    <span>产品策略</span>
    <strong>商业模式</strong>
    <span>总结</span>
  </header>

  <section class="card-image-frame">
    <img class="card-image" src="/images/demo.png" alt="">
  </section>

  <h1 class="card-title">把收入模型讲清楚</h1>

  <section class="card-body">
    <!-- Markdown 渲染后的正文 -->
  </section>
</article>
```

默认 CSS 变量：

```css
:root {
  --card-width: 900px;
  --card-height: 1200px;
  --card-padding-x: 72px;
  --card-padding-y: 64px;
  --nav-size: 20px;
  --title-size: 54px;
  --title-line-height: 1.08;
  --title-top: 64px;
  --body-size: 28px;
  --body-line-height: 1.45;
  --image-height: 260px;
  --image-radius: 32px;
  --text-primary: #111827;
  --text-muted: #8A94A6;
  --accent: #29B8D4;
}
```

用户可继续写选择器覆盖：

```css
.card-title {
  max-width: 760px;
}

.card-index-1 .card-title {
  font-size: 68px;
}
```

## 7. HTML+CSS 源码编辑器

右侧源码面板提供一个高亮代码编辑器，内容是当前卡片的完整 `<style>...</style>` 和 `<article class="knowledge-card">...</article>`。

行为：

1. 打开 `/canvas/?company=...` 时按定稿 Markdown 生成默认源码。
2. 如果本地已有当前卡片自定义源码，从 `localStorage` 恢复。
3. 用户输入时防抖渲染到中间 iframe。
4. “保存当前页源码”把当前卡片源码保存到本机浏览器。
5. “重置”删除当前卡片源码并重新从定稿 Markdown 生成。
6. 高亮层只用于编辑体验；真实渲染以 textarea 中的源码为准。

建议状态结构：

```json
{
  "1": "<style>...</style><article class=\"knowledge-card\">...</article>",
  "6": "<style>...</style><article class=\"knowledge-card\">...</article>"
}
```

`localStorage` key：

```text
aistartups.cardSource.<company_name>
```

## 8. 图片 Prompt Bar

画布下方增加 prompt bar。

组成：

- prompt 输入框
- “恢复预设”按钮
- “生成图片”按钮
- 生成状态提示

每张卡片有默认 prompt。默认 prompt 由前端根据卡片内容生成，不额外调用 LLM：

```text
极简 iOS 毛玻璃边框内的抽象插图，
主题：{卡片标题 / 正文关键词}，
白色背景，低饱和青蓝色，矢量插画，
无文字，无水印，适合知识卡片。
```

调用现有接口：

```http
POST /api/generate-image
Content-Type: application/json

{
  "company_name": "Anthropic",
  "field_name": "card_6_image",
  "prompt": "..."
}
```

成功响应沿用现有结构：

```json
{
  "status": "ok",
  "img_path": "/images/Anthropic_card_6_image_1779810000.png"
}
```

当前行为：

- 图片生成成功后立即更新当前卡片预览。
- 图片路径保存在前端状态与 `localStorage`。
- 图片 API URL 可保存在本机浏览器；API Key 只保存在页面内存，不写入 `localStorage`，也不在响应中回显。

第二版可扩展：

- 新增后端接口把图片路径写回 `final_content.img_local_path`。
- 这样换浏览器或换机器后也能恢复图片。

## 9. 后端路由

保留：

```http
GET /canvas/
GET /canvas/<path:filename>
GET /api/final/export/<company>?format=json
POST /api/generate-image
```

新增：

```http
GET /canvas/card/<company>/<int:card_index>
```

用途：返回单张卡片 HTML。参数：

- `company`：公司名。
- `card_index`：1-7。
- `css_token` 或 `style_id`：可选，用于服务端导出场景。

第一版也可让 iframe 使用静态 `canvas/card.html`，再通过 query 参数拉 JSON 渲染。两种方式取舍：

- 服务端 route：更利于 Puppeteer 直接截图。
- 静态 card.html：前端开发更快。

推荐采用服务端 route，导出路径更稳定。

## 10. 前端模块

建议重建 `canvas/js/`：

```text
canvas/
  card-renderer.html          # 制作台入口，三栏布局
  card-template.html          # 单卡 HTML 模板，或由 Flask render_template 返回
  screenshot.js               # Puppeteer 批量截图
  js/
    markdown-parser.js        # 保留并收敛：Markdown -> card data
    html-card-renderer.js     # card data -> HTML+CSS source
    api-loader.js             # final export JSON loader
    prompt-bar.js             # prompt preset + generate image
    source-editor.js          # HTML+CSS 源码编辑、高亮、localStorage
    export-client.js          # 导出按钮与参数组装
```

可以删除或停止主路径引用：

```text
canvas/js/card-layout.js
canvas/js/fabric-renderer.js
canvas/js/export.js
canvas/js/thumbnail-nav.js
```

为减少一次性风险，可以先保留文件但从 `card-renderer.html` 移除引用；确认新方案稳定后再删除旧文件。

## 11. Puppeteer 导出

新增 `canvas/screenshot.js`。

命令：

```bash
node canvas/screenshot.js \
  --company Anthropic \
  --base-url http://127.0.0.1:5050 \
  --out output/cards/Anthropic
```

行为：

1. 请求 `/api/final/export/<company>?format=json` 确认数据存在。
2. 逐张打开 `/canvas/card/<company>/<card_index>`。
3. 等待字体、图片、布局完成。
4. 按 `900 x 1200` 或 2x 输出 PNG。
5. 文件名为：

```text
<company>_card_01.png
<company>_card_02.png
...
<company>_card_07.png
```

截图参数：

```js
await page.setViewport({
  width: 900,
  height: 1200,
  deviceScaleFactor: 2
});
```

## 12. 数据状态

浏览器侧状态：

```json
{
  "companyName": "Anthropic",
  "currentCard": 6,
  "images": {
    "6": "/images/Anthropic_card_6_image_1779810000.png"
  },
  "prompts": {
    "6": "极简 iOS 毛玻璃边框内的抽象收入飞轮图标..."
  },
  "sources": {
    "6": "<style>...</style><article class=\"knowledge-card\">...</article>"
  }
}
```

`localStorage` keys：

```text
aistartups.cardImages.<company_name>
aistartups.cardPrompts.<company_name>
aistartups.cardSource.<company_name>
```

服务端权威数据仍是 `final_db` 的 `markdown_full`。

## 13. 测试策略

Python 测试：

1. `/canvas/` 返回新的制作台 HTML。
2. `/canvas/card/<company>/<n>` 对 1-7 返回 200。
3. `/canvas/card/<company>/8` 返回 400 或 404。
4. `/api/final/export/<company>?format=json` 仍兼容 `markdown_full`。
5. `/api/generate-image` 现有 mock 测试保持通过。

静态契约测试：

1. `card-renderer.html` 不再引用 `fabric.min.js`。
2. `card-renderer.html` 包含 HTML+CSS 源码编辑器入口。
3. `card-renderer.html` 包含 prompt bar。
4. JS 中存在 `localStorage` 样式状态 key。
5. JS 中存在源码高亮和实时渲染入口。

Node 侧验证：

1. `node canvas/screenshot.js --help` 能输出使用说明。
2. 在 Flask 服务启动后，能导出测试公司 PNG。

项目既有验证命令：

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile webapp/*.py
```

## 14. 实施步骤

1. 写测试：先覆盖 Flask route 与静态契约。
2. 新增单卡 HTML route，返回最小可渲染卡片。
3. 重写 `canvas/card-renderer.html` 为三栏制作台。
4. 实现 `html-card-renderer.js`，从 Markdown 数据生成卡片 DOM。
5. 实现 `source-editor.js`，支持源码编辑、语法高亮、实时渲染、localStorage。
6. 实现 `prompt-bar.js`，支持默认 prompt、编辑、调用图片 API。
7. 实现 `screenshot.js` 和 `package.json`。
8. 移除主路径对 fabric 相关 JS 的引用。
9. 运行 Python 测试与 py_compile。
10. 启动 Flask，用浏览器验证 `/canvas/?company=...`。
11. 用 Puppeteer 导出 PNG 并检查尺寸与画面完整性。

## 15. 风险与处理

### 15.1 源码编辑破坏布局

用户直接写 HTML/CSS，可能写出导致画面溢出或结构破坏的源码。

处理：

- 保留“重置”按钮，从定稿 Markdown 重新生成默认源码。
- iframe 外层始终以 `fit-to-window` 显示完整卡片。
- 导出前检测 `.knowledge-card` 尺寸是否仍为 3:4。

### 15.2 CLI 导出与浏览器预览不一致

源码、图片状态保存在浏览器 `localStorage` 时，命令行 Puppeteer 默认拿不到这些状态。

处理：

- CLI 导出默认使用数据库定稿内容。
- 浏览器内源码编辑主要服务预览、单页打开和人工截图。
- 后续如需批量导出浏览器编辑结果，应增加状态导出 JSON 或服务端持久化接口。

### 15.3 图片生成耗时或失败

处理：

- prompt bar 显示生成中、失败、重试。
- 失败时保留原图片或默认 SVG 占位。
- 不阻断卡片 HTML/PNG 导出。

### 15.4 旧 canvas 文件迁移风险

处理：

- 第一阶段从 HTML 入口移除旧 JS 引用，而不是立即删除全部旧文件。
- 测试稳定后再清理 `fabric-renderer.js` 等旧文件。

## 16. 验收标准

1. `/canvas/?company=<公司名>` 能打开三栏制作台。
2. 左右栏收窄，中间卡片默认完整展示。
3. 卡片比例为 3:4，导出 PNG 尺寸正确。
4. 顶部 header 显示多个章节，当前页加粗。
5. 卡片无底部 `aistartups` 标识。
6. prompt bar 能显示每页预设 prompt，并能编辑。
7. 点击生成图片能调用 `/api/generate-image` 并更新当前预览。
8. HTML+CSS 源码编辑器能实时改变当前页内容、字体、位置、色彩、间距。
9. 当前页源码可保存到本机浏览器并可重置。
10. CLI 能按数据库定稿内容导出 PNG。
11. 既有 Python 测试通过。
12. `python3 -m py_compile webapp/*.py` 通过。
