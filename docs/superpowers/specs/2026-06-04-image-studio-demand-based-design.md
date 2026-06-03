# 图片定稿台按图片需求组织改造设计

## 背景

当前图片定稿台仍然以卡片槽位为主线组织，抓取图片和生成图混在同一套操作界面里。上一次改动已经把 `positioning_charts` 拆成 `chart_competitive` 和 `chart_ecosystem`，但用户体验仍然没有本质变化：图表预览和参数调节弱、生成图缺少数据和文字编辑入口、右侧候选确认与中栏预览割裂。

本设计采用保守改造路线：保留现有三栏基础和 `image_variants` 候选库，但将左侧导航改为“图片需求清单”，中栏和右栏组成当前图片的一体化工作区。每一种图片最终都通过右下角“确定这张图片”写入资产库，并进入 canvas 图片夹。

## 目标

1. 图片定稿左侧不按卡片分页，而按真实图片需求组织。
2. 抓取类图片和生成类图片使用不同工作区，但共用候选版本、预览和确定逻辑。
3. 四张生成图具备可用的编辑和调参能力，而不是只有颜色、字号、点大小等少量滑块。
4. 已确定图片进入 canvas 图片夹，供画布手动填充或模板自动引用。
5. 改动保持 Vanilla JS、Flask、SQLite 现有架构，不引入 React/Vue 或新 ORM。

## 非目标

1. 本期不重做 canvas 画布系统。
2. 本期不新增远程图片 API 或外部工作流。
3. 本期不把所有抓取逻辑重写为新 pipeline，只调整 image-studio 的组织和交互。
4. 本期不要求生成图达到专业设计工具级别，但要达到可调、可预览、可保存、可确定。

## 图片需求清单

左侧固定展示以下需求项。每项显示名称、类型、状态、候选数量和弱提示用途。

```text
logo                 Logo                         抓取图
website_screenshot   官网截图                     抓取图
office               办公室或地图                 抓取图
product_main         主产品截图                   抓取图
products_other       其他产品截图                 抓取图
competitors          竞品截图                     抓取图
chart_competitive    AI 创业公司竞争格局图        生成图 / ECharts
chart_ecosystem      AI 产业链生态位图            生成图 / ECharts
flywheel             飞轮图                       生成图 / SVG
timeline             时间线图                     生成图 / SVG
```

`website_screenshot` 是新增资产键，用于承载官网首页或官网关键截图。它不替代 `product_main`，也不与 `office` 混用。

## 布局

图片定稿标签页仍嵌入定稿台。

```text
左侧：图片需求清单
右侧整体工作区：
  顶部：当前需求标题、类型、状态、候选数、尺寸
  中部左：大预览区
  中部右：候选版本或参数检查器
  底部：当前类型的操作栏
  右下角：确定这张图片
```

中栏和右栏不再像现在一样各自独立，而是围绕当前需求组成一套工作区。点击候选、搜索结果或生成版本时，先进入大预览；只有点击“确定这张图片”才写入最终选择。

## 抓取图工作区

适用项：

```text
logo / website_screenshot / office / product_main / products_other / competitors
```

功能：

1. 大预览区展示当前预览图片。
2. 右侧展示候选缩略图、来源、尺寸、分数、失败原因。
3. 操作栏包含重新采集、搜索、上传、URL 导入、重新评分。
4. `office` 保留地图生成入口。
5. 搜索结果下载后写入 `image_variants`，但不自动最终确定。
6. 右下角“确定这张图片”调用 select 接口，将当前预览候选写入 `company_assets`。

抓取图的核心原则是“候选可多，最终只选一张”。自动采集可以给出默认候选，但用户确认动作必须清晰。

## 生成图工作区

适用项：

```text
chart_competitive / chart_ecosystem / flywheel / timeline
```

生成图不显示搜索工具栏，右侧改为“图表参数检查器”。检查器按分组折叠，同一时间只展开一个分组。

通用分组：

1. 数据与文字：标题、副标题、注释、公司或事件列表、字段覆盖。
2. 画布与版式：输出尺寸、边距、图例位置、标题位置、预览缩放。
3. 字体与颜色：主题、背景、强调色、色板、标题字号、标签字号、轴字号。
4. 图表专属：随图类型切换。
5. 输出版本：生成 PNG 变体、历史版本、删除版本、确定最终图。

参数变化 300ms debounce 后刷新实时预览，不自动保存为最终图片。点击“生成版本”才通过 Playwright 截图生成 PNG 变体；点击“确定这张图片”才选为最终资产。

## 四张生成图的专属参数

### AI 创业公司竞争格局图

数据来源是 `research` 表中的评分字段：

```text
score_defensibility
score_incumbent_attention
funding_stage_score
company_name
```

可调内容：

1. 标题、副标题、图下注释。
2. 公司列表筛选、排序、显示数量。
3. 单家公司 X/Y 分数覆盖。
4. 四象限名称和显示开关。
5. 气泡大小公式和最小/最大半径。
6. 主公司高亮样式。
7. 标签显示密度、标签避让、标签字号。
8. 坐标轴范围、网格线密度、分割线位置。

### AI 产业链生态位图

数据来源是 `research` 表中的：

```text
stack_layer
score_value_capture
funding_stage_score
company_name
```

可调内容：

1. 层级名称、顺序和颜色。
2. 公司所属层级覆盖。
3. 价值捕获阈值，默认 7。
4. 高价值背景区显示开关和颜色。
5. 散点横向抖动，避免同层级重叠。
6. 标签密度、主公司标注、图例位置。

### 飞轮图

数据来源优先使用已缓存的 `svg_data`，没有缓存时从卡片 6 定稿 Markdown 抽取。

可调内容：

1. 中心文字。
2. 阶段名称、描述、顺序、增删。
3. 模板选择：圆形、横向、辐射等。
4. 节点半径、环半径、箭头曲率、线宽。
5. 阶段字号、描述字号、描述显示开关。
6. 每节点颜色或统一强调色。

### 时间线图

数据来源优先使用已缓存的 `svg_data`，没有缓存时从卡片 3 定稿 Markdown 抽取。

可调内容：

1. 事件列表：年份、标题、描述、顺序、增删。
2. 模板选择：左轴、右轴、横向等。
3. 行高、节点间距、时间轴位置。
4. 节点大小、线宽、标题字号、描述字号。
5. 长文本换行和截断策略。
6. 横版/竖版输出尺寸。

## 数据流

### 抓取图

```text
点击图片需求
  -> 加载 company_assets + image_variants
  -> 大预览显示当前 selected variant 或空态
  -> 用户搜索/采集/上传/URL 导入
  -> insert_variant
  -> 点击候选只预览
  -> 点击确定这张图片
  -> select_variant
  -> company_assets.status = ready
  -> canvas 图片夹可读取
```

### 生成图

```text
点击生成图需求
  -> 加载图表数据和参数默认值
  -> 实时预览 HTML/SVG
  -> 用户调整数据/文字/参数
  -> debounce preview
  -> 点击生成版本
  -> Playwright 渲染 PNG
  -> insert_variant(source_type=svg_render)
  -> 点击确定这张图片
  -> select_variant
  -> canvas 图片夹可读取
```

## 后端接口

保留现有接口并扩展：

```text
GET    /api/image-studio/<company>
GET    /api/image-studio/<company>/<asset_key>/variants
POST   /api/image-studio/<company>/<asset_key>/search
POST   /api/image-studio/<company>/<asset_key>/fetch
POST   /api/image-studio/<company>/<asset_key>/import
POST   /api/image-studio/<company>/<asset_key>/rescore
PATCH  /api/image-studio/<company>/<asset_key>/select
DELETE /api/image-studio/<company>/<asset_key>/variants/<variant_id>
```

新增或调整：

```text
POST /api/image-studio/<company>/<asset_key>/chart-data
POST /api/image-studio/<company>/<asset_key>/preview
POST /api/image-studio/<company>/<asset_key>/render-svg
```

`chart-data` 返回当前图的可编辑数据结构。`preview` 返回 HTML 或 SVG 字符串，不经过 Playwright。`render-svg` 生成 PNG 变体并写入 `image_variants`。

## 前端模块

建议将 `studio-app.js` 的大块图表逻辑拆出，但保持 Vanilla JS。

```text
image-studio/js/studio-app.js          顶层状态与路由
image-studio/js/workspace-image.js     抓取图工作区
image-studio/js/workspace-chart.js     生成图工作区
image-studio/js/param-inspector.js     右侧参数检查器
image-studio/js/variant-sidebar.js     候选版本列表，保留并增强
image-studio/js/studio-api.js          API 封装
```

第一期可以先在现有文件内完成，但如果继续堆在 `studio-app.js`，会加重现在的重复方法和事件覆盖问题。当前已有 `_onChartParamChange` 重复定义，后续实现必须清理。

## Canvas 集成

Canvas 图片夹应读取已确定资产，不依赖卡片分页。图片夹展示需求名、状态、缩略图和 asset key。用户在 canvas 中选择图片填充画布时，使用 `company_assets.local_path`。

对于同一卡片可能有多个图片需求的情况，例如卡片 7 同时有竞品截图、竞争格局图、生态位图，canvas 图片夹应全部展示，不由 `CARD_ASSET_MAP` 单键限制。

## 测试范围

后端：

1. `ensure_assets_rows()` 创建 10 个资产键。
2. `website_screenshot` 初始状态正确。
3. `chart_competitive` 和 `chart_ecosystem` 独立变体、独立选择。
4. `select_variant()` 只允许选择同公司同 asset key 的变体。
5. `preview` 返回 HTML/SVG，不生成 PNG。
6. `render-svg` 写入 `image_variants` 并可被 select。

前端静态契约：

1. 左侧使用图片需求清单，不出现卡片分页作为主导航。
2. 抓取图工作区包含采集、搜索、上传、URL 导入、重新评分。
3. 生成图工作区包含参数检查器。
4. 参数检查器包含五个分组。
5. 每种图片工作区右下角都有“确定这张图片”。

端到端：

1. 对一个已有公司打开定稿台图片标签。
2. 选择抓取图，搜索或采集候选，预览后确定。
3. 选择四张生成图之一，调整参数，生成版本，确定。
4. 打开 canvas 图片夹，确认已确定图片出现。

## 实施顺序

1. 数据层：新增 `website_screenshot`，整理资产键和 overview 顺序。
2. 后端：补齐生成图 `chart-data`、`preview`、`render-svg` 的稳定数据结构和错误返回。
3. 前端框架：左侧改为图片需求清单，中右工作区按类型切换。
4. 抓取图工作区：复用现有搜索/候选/选择能力，调整布局和确认按钮。
5. 生成图工作区：实现参数检查器和四张图的专属参数。
6. Canvas 图片夹：展示所有已确定资产，而不是只按卡片单图映射。
7. 测试：先后端和静态契约，再跑最小端到端验证。

## 风险

1. ECharts 预览依赖 CDN，国内网络可能导致 iframe 空白。应考虑本地 vendored ECharts 或失败空态。
2. 生成图参数增多后，未缓存参数会导致用户刷新丢失。需要将参数快照写入 `image_variants.meta_json`。
3. Canvas 现有 `CARD_ASSET_MAP` 单图映射无法表达一张卡多个图片需求，需要图片夹先支持多资产展示。
4. 当前工作区已有未提交改动，实现前必须确认以这些改动为基线还是先整理分支。
