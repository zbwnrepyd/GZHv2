# GZHv2 卡片规格 v2 — 完整技术改造文档

**文档版本：** 1.0  
**目标版本：** `card_spec_version = v2`  
**基于代码库：** GZHv2-main（截止 2026-06-08）  
**涉及文件数：** 11 个文件 + 1 个新建迁移文件

---

## 目录

1. [变更概述](#1-变更概述)
2. [新版卡片规格（v2）](#2-新版卡片规格v2)
3. [字段变更清单](#3-字段变更清单)
4. [图片资产槽位变更](#4-图片资产槽位变更)
5. [数据库迁移方案](#5-数据库迁移方案)
6. [文件改动详情](#6-文件改动详情)
7. [研究提示词更新](#7-研究提示词更新)
8. [数据可得性风险说明](#8-数据可得性风险说明)
9. [执行清单与验收标准](#9-执行清单与验收标准)

---

## 1. 变更概述

### 1.1 核心变化

| 维度 | v1 | v2 |
|---|---|---|
| 卡片总数 | 8 张 | 7 张 |
| 废弃卡片 | — | card_3（时间线）、card_5（其他产品）、card_8（总结） |
| 新增字段 | — | 5 个（见第3节） |
| 新增资产槽位 | — | 1 个（founder_photo） |
| card_index 校验上限 | 8 | 7 |

### 1.2 卡片重组逻辑

```
旧 card_2（公司介绍）  →  拆分为  page2（公司概览）+ page4（创始人与团队）
旧 card_4（主产品）    →  合并入  page3（产品与定位），同时引入生态位图
旧 card_6（商业模式）  →  拆分为  page5（财务与市场）+ page6（GTM与增长）
旧 card_7（竞争格局）  →  延续为  page7，chart_ecosystem 同时挪至 page3
```

废弃的三张卡片（card_3/5/8）对应数据库列**保留不删**，防止历史数据读取报错，仅停止在研究提示词中强制提取、停止在排版层渲染。

---

## 2. 新版卡片规格（v2）

### 卡片定义表

| card_index | 主题 | 主要内容 | 触发的资产生成 |
|---|---|---|---|
| 1 | 封面 | 公司名、Logo | — |
| 2 | 公司概览 | 官网截图、公司地址、所属行业、主营业务、公司成就 | — |
| 3 | 产品与定位 | 生态位图（chart_ecosystem）、主要产品、技术栈 | 确认时触发 chart_ecosystem |
| 4 | 创始人与团队 | 创始人照片、姓名、工作背景、学历背景、团队规模、团队成员背景 | — |
| 5 | 财务与市场 | 典型客户及客户群体、公司营收、分地区市场、公司利润、融资情况 | — |
| 6 | GTM 与增长 | GTM 策略、增长飞轮图 | 确认时触发 flywheel SVG |
| 7 | 竞争格局 | 竞争格局图（chart_competitive）、行业 Top3 竞对、公司竞争优势 | 确认时触发 chart_competitive + chart_ecosystem（更新） |

### 图片资产槽位归属（v2）

| asset_key | 所属卡片 | 生成方式 | 是否必须 |
|---|---|---|---|
| logo | card_1 | collected | 是 |
| website_screenshot | card_2 | collected | 否 |
| founder_photo | card_4 | collected | 否 |
| chart_ecosystem | card_3 | generated / echarts | 否 |
| product_main | card_3 | collected | 否 |
| flywheel | card_6 | generated / svg | 否 |
| chart_competitive | card_7 | generated / echarts | 否 |
| competitors | card_7 | collected | 否 |
| competitors_logo_strip | card_7 | generated / composite | 否 |

> **已废弃槽位**（DB 行保留，不再渲染）：`office`、`timeline`、`products_other`

---

## 3. 字段变更清单

### 3.1 新增字段（5 个）

| field_key | field_label | type | 所属卡片 | 说明 |
|---|---|---|---|---|
| `company_achievement` | 公司成就 | long_text | card_2 | 公司级别成就，独立于产品级成就。如：融资里程碑、用户规模、媒体/奖项认可、知名客户签约 |
| `tech_stack` | 技术栈 | long_text | card_3 | 自由文字描述技术栈，参考 stack_layer/ai_model_dependency 枚举但展开为可读文字，100 字内 |
| `company_revenue` | 公司营收 | text | card_5 | 营收规模，如"ARR $12M（2024Q4，来源：TechCrunch）"；找不到填"暂缺" |
| `regional_markets` | 分地区市场 | long_text | card_5 | 主要市场地区及占比，如"美国 60%、欧洲 25%、亚太 15%"；找不到填"暂缺" |
| `company_profit` | 公司利润 | text | card_5 | 利润/毛利率数据；找不到填"暂缺"，严禁估算 |

### 3.2 废弃字段（保留数据列，停止提取）

| field_key | 原所属卡片 | 废弃原因 |
|---|---|---|
| `timeline_events` | card_3 | card_3（时间线）整张废弃 |
| `other_products` | card_5 | card_5（其他产品）整张废弃 |
| `hook_paragraph_1/2/3` | card_8 | card_8（总结）整张废弃 |
| `market_opportunity` | card_8 | card_8（总结）整张废弃 |
| `cold_start` | card_6 | 并入 page6 GTM 叙述，不再独立成字段 |

### 3.3 字段重映射（字段不变，卡片归属变化）

| field_key | v1 所属卡片 | v2 所属卡片 |
|---|---|---|
| `founder_name / founder_edu / founder_bg / founder_achievement` | card_2 | card_4 |
| `team_size / team_highlight` | card_2 | card_4 |
| `customer_segment / funding_info` | card_2 / card_6 | card_5 |
| `gtm_strategy / growth_flywheel` | card_6 | card_6（不变） |
| `ecosystem_niche / chart_ecosystem` | card_7 | card_3 |

---

## 4. 图片资产槽位变更

### 4.1 新增：founder_photo

```
asset_key:   founder_photo
card_index:  4
kind:        collected
required:    false
```

**图片来源策略（优先级从高到低）：**

1. Tavily 图片搜索：`{founder_name} {company_name} photo`
2. Playwright 抓取公司官网 About 页（`office_photo_hints.about_url`）
3. Playwright 抓取 LinkedIn 公开页（`office_photo_hints.linkedin_url`）
4. 无来源时标记 `status: failed`，排版层显示占位框

**过滤规则：** 须为人像图（aspect ratio 接近 1:1 或 3:4），宽度 ≥ 200px，非卡通/logo/产品截图。

### 4.2 废弃槽位处理

`office`、`timeline`、`products_other` 三个 asset_key：
- DB 行保留（不删除 `company_assets` 中的记录）
- `ASSET_KEYS` 列表中保留（防止 `ensure_assets_rows` 出错）
- `CARD_ASSET_SLOTS`（asset_resolver.py）中移除或置空对应卡片
- Image Studio UI 中可隐藏或标记"已废弃"

---

## 5. 数据库迁移方案

### 5.1 新建文件：`db/migrations/004_v2_fields.sql`

```sql
-- 004_v2_fields.sql — 卡片规格 v1 → v2 新增字段
-- 适用数据库：research_db.sqlite
-- 执行方式：python3 db/migrate.py db/research_db.sqlite --names 004_v2_fields.sql

-- 新增 page2：公司成就
ALTER TABLE research ADD COLUMN company_achievement TEXT;

-- 新增 page3：技术栈自由文字描述
ALTER TABLE research ADD COLUMN tech_stack TEXT;

-- 新增 page5：财务与市场
ALTER TABLE research ADD COLUMN company_revenue TEXT;
ALTER TABLE research ADD COLUMN regional_markets TEXT;
ALTER TABLE research ADD COLUMN company_profit TEXT;

-- 同步更新 research_fields（如使用 EAV 扩展表，视项目情况执行）
-- ALTER TABLE research_fields ... （见 001_research_fields.sql 格式）

-- 注：timeline_events / other_products / hook_paragraph_1~3 /
--     market_opportunity / cold_start 对应列保留，不做 DROP，
--     防止历史数据读取报错。
```

### 5.2 执行方法

```bash
python3 db/migrate.py db/research_db.sqlite --names 004_v2_fields.sql
```

若 `migrate.py` 不支持 `--names` 参数，直接执行：

```bash
sqlite3 /opt/ai/data/research_db.sqlite < db/migrations/004_v2_fields.sql
```

### 5.3 final_db 无需迁移

`final_content` 表采用 EAV 结构（`card_index, field_name, field_value`），新增字段和新卡片编号自动兼容，无需 ALTER TABLE。仅需更新业务层的 `card_index` 上限校验（见第6节）。

### 5.4 assets_db 更新

无需迁移 SQL，但需要在 `ASSET_KEYS` 列表末尾追加 `founder_photo`，`ensure_assets_rows()` 会在下次调用时自动为每家公司插入新行。

---

## 6. 文件改动详情

### 6.1 `contracts/fields.json`

在 `basic` 组末尾追加：

```json
{"field_key": "company_achievement", "field_label": "公司成就", "type": "long_text", "required": false}
```

在 `product` 组末尾追加：

```json
{"field_key": "tech_stack", "field_label": "技术栈", "type": "long_text", "required": false}
```

在 `business` 组末尾追加（3 个）：

```json
{"field_key": "company_revenue", "field_label": "公司营收", "type": "text", "required": false},
{"field_key": "regional_markets", "field_label": "分地区市场", "type": "long_text", "required": false},
{"field_key": "company_profit", "field_label": "公司利润", "type": "text", "required": false}
```

`cold_start` 字段加上 `"deprecated": true` 标记（不删除）：

```json
{"field_key": "cold_start", "field_label": "冷启动策略", "type": "long_text", "deprecated": true}
```

---

### 6.2 `contracts/media.json`

在 `media_types` 数组开头（logo 之后）插入：

```json
{
  "media_key": "founder_photo",
  "media_label": "创始人照片",
  "kind": "collected",
  "required": false
}
```

将 `timeline` 的 `required` 改为 `false`（已是 false，确认即可）：

```json
{
  "media_key": "timeline",
  "media_label": "发展时间线图",
  "kind": "generated",
  "required": false,
  "generator": "svg",
  "deprecated": true
}
```

---

### 6.3 `webapp/asset_store.py`

**改动 1：** `ASSET_KEYS` 列表追加 `founder_photo`

```python
# 修改前
ASSET_KEYS = [
    "logo", "website_screenshot", "office", "product_main", "products_other",
    "competitors", "competitors_logo_strip", "flywheel", "timeline",
    "chart_competitive", "chart_ecosystem",
]

# 修改后
ASSET_KEYS = [
    "logo", "website_screenshot", "founder_photo",
    "product_main",
    "competitors", "competitors_logo_strip", "flywheel",
    "chart_competitive", "chart_ecosystem",
    # 以下为废弃槽位，保留 DB 行但不再渲染
    "office", "products_other", "timeline",
]
```

**改动 2：** `CARD_ASSET_MAP` 更新为 v2 归属

```python
# 修改后
CARD_ASSET_MAP = {
    1: "logo",
    2: "website_screenshot",
    3: "product_main",       # chart_ecosystem 另行触发，不替代主资产
    4: "founder_photo",
    5: None,                 # page5 无单一主资产
    6: "flywheel",
    7: "competitors",
}

ASSET_TO_CARD = {v: k for k, v in CARD_ASSET_MAP.items() if v}
ASSET_TO_CARD["competitors_logo_strip"] = 7
ASSET_TO_CARD["chart_competitive"]      = 7
ASSET_TO_CARD["chart_ecosystem"]        = 3   # v2 改为 page3
```

---

### 6.4 `webapp/asset_resolver.py`

**改动 1：** 版本号升级

```python
# 修改前
CARD_SPEC_VERSION = "v1"

# 修改后
CARD_SPEC_VERSION = "v2"
```

**改动 2：** `CARD_ASSET_SLOTS` 更新为 v2

```python
# 修改后
CARD_ASSET_SLOTS = {
    1: ["logo"],
    2: ["website_screenshot"],
    3: ["chart_ecosystem", "product_main"],
    4: ["founder_photo"],
    5: [],
    6: ["flywheel"],
    7: ["competitors", "competitors_logo_strip", "chart_competitive"],
}
```

---

### 6.5 `webapp/app.py`

**改动 1（第 210 行）：** 前台卡片确认接口校验上限

```python
# 修改前
if card_index < 1 or card_index > 8:
    return jsonify({"error": "card_index 必须在 1-8 之间"}), 400

# 修改后
if card_index < 1 or card_index > 7:
    return jsonify({"error": "card_index 必须在 1-7 之间"}), 400
```

**改动 2（第 665 行）：** 同上，final confirm 接口

```python
# 修改前
if card_index < 1 or card_index > 8:

# 修改后
if card_index < 1 or card_index > 7:
```

**改动 3（第 676–685 行）：** 卡片确认后的自动图表触发逻辑

```python
# 修改前
# 预提取 SVG 数据（卡片3=timeline, 卡片6=flywheel）
if card_index in (3, 6):
    _pre_extract_svg_data(company_name, card_index)

# 卡片7确认时自动生成竞争格局图 + 产业链生态位图
if card_index == 7:
    threading.Thread(target=_generate_card7_charts,
                   args=(company_name,), daemon=True).start()

# 修改后
# 预提取 SVG 数据（卡片6=flywheel；timeline 已废弃）
if card_index == 6:
    _pre_extract_svg_data(company_name, card_index)

# 卡片3确认时生成生态位图（chart_ecosystem 移至 page3）
if card_index == 3:
    threading.Thread(
        target=_generate_ecosystem_chart,
        args=(company_name,), daemon=True
    ).start()

# 卡片7确认时生成竞争格局图（chart_competitive）
if card_index == 7:
    threading.Thread(target=_generate_card7_charts,
                   args=(company_name,), daemon=True).start()
```

同时新建 `_generate_ecosystem_chart` 辅助函数（在 `_generate_card7_charts` 旁边）：

```python
def _generate_ecosystem_chart(company_name: str):
    """卡片3确认后自动生成产业链生态位图（后台线程）"""
    try:
        init_assets_db(config.DB_PATH_ASSETS)
        ensure_assets_rows(config.DB_PATH_ASSETS, company_name)
        companies = _load_all_scored_companies(config.DB_PATH_RESEARCH)
        dest_dir = _company_image_dir(config.IMAGES_DIR, company_name)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, "chart_ecosystem.png")
        ok = render_stack_positioning(companies, company_name, dest)
        status = "ready" if ok else "failed"
        update_asset(config.DB_PATH_ASSETS, company_name, "chart_ecosystem",
                     local_path=dest if ok else None,
                     source_type="svg_render", status=status)
    except Exception as e:
        import logging
        logging.warning(f"[ecosystem_chart] {company_name}: {e}")
```

**改动 4（第 1873 行）：** 全卡片审稿提示词

```python
# 修改前
prompt = f"""你是专业编辑。以下是一家AI创业公司的8张知识卡片全部内容（{version}版）。

# 修改后
prompt = f"""你是专业编辑。以下是一家AI创业公司的7张知识卡片全部内容（{version}版）。
```

**改动 5（第 1212 行附近）：** Image Studio 槽位枚举

```python
# 修改前
for asset_key in ["logo", "website_screenshot", "office", "product_main",
                  "products_other", "competitors", "competitors_logo_strip",
                  "chart_competitive", "chart_ecosystem",
                  "flywheel", "timeline"]:

# 修改后
for asset_key in ["logo", "website_screenshot", "founder_photo",
                  "product_main",
                  "competitors", "competitors_logo_strip",
                  "chart_competitive", "chart_ecosystem", "flywheel"]:
```

**改动 6：** Image query hints — 新增 `founder_photo` 的 `card_topics` 条目和 fallback

在 `card_topics` 字典内追加：

```python
"founder_photo": "创始人照片/人物照",
```

在 `fallbacks` 字典内追加：

```python
"founder_photo": [
    {"en": f"{company} founder CEO portrait photo", "zh": f"{company} 创始人 CEO 照片"},
    {"en": "startup founder headshot professional", "zh": "创始人 头像 职业照"},
    {"en": "entrepreneur portrait tech company", "zh": "创业者 照片 科技公司"},
],
```

---

### 6.6 `webapp/db.py`

**改动（第 596 行）：** `field_to_card` 映射更新

```python
# 修改前
field_to_card = {"timeline_events": 3, "growth_flywheel": 6}

# 修改后
field_to_card = {
    "growth_flywheel": 6,     # page6 飞轮图
    "ecosystem_niche":  3,    # page3 生态位（用于 _pre_extract_svg_data 判断）
}
```

---

### 6.7 `docs/card-spec.md`

整体替换为以下内容：

```markdown
# 卡片与图片资产规范

当前规范版本：`card_spec_version = v2`

## 卡片规范 v2

| 卡片 | 主题 | 主要内容 |
| --- | --- | --- |
| `card_1` | 封面 | 公司名、Logo |
| `card_2` | 公司概览 | 官网截图、地址、所属行业、主营业务、公司成就 |
| `card_3` | 产品与定位 | 生态位图、主要产品、技术栈 |
| `card_4` | 创始人与团队 | 创始人照片、姓名、工作/学历背景、团队规模、团队背景 |
| `card_5` | 财务与市场 | 典型客户、公司营收、分地区市场、公司利润、融资情况 |
| `card_6` | GTM 与增长 | GTM 策略、增长飞轮 |
| `card_7` | 竞争格局 | 竞争格局图、行业 Top3 竞争对手、公司竞争优势 |

## 图片资产槽位

| asset_key | 用途 | 默认归属 | 生成方式 |
| --- | --- | --- | --- |
| `logo` | 公司 Logo | `card_1` | collected |
| `website_screenshot` | 官网首页截图 | `card_2` | collected |
| `founder_photo` | 创始人照片 | `card_4` | collected |
| `chart_ecosystem` | AI 产业链生态位图 | `card_3` | generated / echarts |
| `product_main` | 主产品截图 | `card_3` | collected |
| `flywheel` | 增长飞轮图 | `card_6` | generated / svg |
| `chart_competitive` | 竞争格局散点图 | `card_7` | generated / echarts |
| `competitors` | 竞品截图 | `card_7` | collected |
| `competitors_logo_strip` | 竞品 Logo 横排拼图 | `card_7` | generated / composite |

### 废弃资产槽位（DB 行保留，停止渲染）

| asset_key | 原归属 | 废弃版本 |
| --- | --- | --- |
| `office` | card_2 | v2 |
| `timeline` | card_3 | v2 |
| `products_other` | card_5 | v2 |

## 自动图表触发规则

| 触发时机 | 生成资产 |
| --- | --- |
| card_3 确认 | chart_ecosystem |
| card_6 确认 | flywheel |
| card_7 确认 | chart_competitive |

## 资产交付接口

排版中心读取：GET /api/assets/resolved?company=<company_name>

返回 card_spec_version = "v2"，card_assets 结构同 v1（card_N 为 key）。
```

---

### 6.8 `canvas/default-templates.json`

将 `"_sets"[0].cards` 的 key 从 `"1"~"8"` 改为 `"1"~"7"`，删除 key `"8"` 的占位条目：

```json
{
  "_sets": [
    {
      "name": "默认模板集",
      "cards": {
        "1": "<!-- card_1 封面模板 -->",
        "2": "<!-- 待粘贴模板 -->",
        "3": "<!-- 待粘贴模板 -->",
        "4": "<!-- 待粘贴模板 -->",
        "5": "<!-- 待粘贴模板 -->",
        "6": "<!-- 待粘贴模板 -->",
        "7": "<!-- 待粘贴模板 -->"
      },
      "createdAt": "2026-06-09"
    }
  ]
}
```

---

## 7. 研究提示词更新

### 7.1 `prompts/layer3-field-extraction.md`

在 JSON 输出模板的 `location` / `company_def` 区块下追加：

```json
"company_achievement": "公司级别成就（100字内）。区别于产品成就，聚焦公司整体里程碑：如融资轮次与金额、签约的知名客户、获得的奖项、媒体报道的关键数据、用户规模里程碑。找不到填"暂缺"。",
```

在 `main_product_achievement` 区块下追加：

```json
"tech_stack": "技术栈描述（100字内）。参考 stack_layer 枚举位置（infrastructure/foundation_model/middleware/vertical_app/distribution），结合 ai_model_dependency 展开为可读文字。说明核心技术选型、自研 vs 调用 API 的比例。",
```

在 `growth_flywheel` 区块后追加（财务与市场区块）：

```json
"company_revenue": "公司营收规模。格式：ARR/MRR $XM（时间，来源）。找不到公开数据填"暂缺"，严禁估算。",
"regional_markets": "主要市场地区及占比（100字内）。如"美国 60%、欧洲 25%、亚太 15%（2024年报）"。找不到填"暂缺"。",
"company_profit": "利润或毛利率。格式：净利润 $XM / 毛利率 X%（时间，来源）。找不到填"暂缺"。",
```

将 `competitors` 数组的说明更新为：

```json
"competitors": [
  {
    "name": "竞品名",
    "product": "核心产品",
    "data": "关键运营数据（含来源）",
    "url": "竞品官网URL",
    "rank": 1
  }
],
"top3_competitors_summary": "Top3竞争对手的一句话对比（150字内，格式：[竞品A]：... [竞品B]：... [竞品C]：...）"
```

将以下字段移出必填清单（保留在 JSON 输出格式中但标注为可选，`timeline_events`、`other_products`、`hook_paragraph_1/2/3`、`market_opportunity`、`cold_start`）：

```json
// 以下字段不再强制提取（v2卡片废弃）
// "timeline_events": [],
// "other_products": [],
// "hook_paragraph_1": "",
// "hook_paragraph_2": "",
// "hook_paragraph_3": "",
// "market_opportunity": "",
// "cold_start": ""
```

### 7.2 字段来源映射更新

在 `## 字段来源映射` 章节追加：

```
- company_achievement → Layer 0（融资信息、媒体引用）+ Layer 1（里程碑事件）
- tech_stack → Layer 0（技术描述）+ stack_layer/ai_model_dependency 枚举
- company_revenue / company_profit → Layer 1（新闻报道）+ Layer 0（官网公开数据）
- regional_markets → Layer 1（市场报告引用）+ Layer 0（官网地区信息）
- top3_competitors_summary → Layer 1 horizontal + competitors 数组合成
```

---

## 8. 数据可得性风险说明

### 8.1 财务字段（高风险）

`company_revenue`、`company_profit`、`regional_markets` 三个字段，针对早期 AI 初创公司（Pre-A 至 Series B）**预计超过 70% 的情况会返回"暂缺"**，因为这类公司不公开财务数据。

**排版层建议：** 在 page5 模板中对这三个字段实现**条件折叠**：

```
若 company_revenue == "暂缺" AND company_profit == "暂缺"
  → 将该区块替换为"融资时间线"（从 funding_info 解析）
  → 保留 customer_segment 和 regional_markets（即使后者也暂缺也展示占位）
```

### 8.2 founder_photo（中风险）

LinkedIn 反爬较强，建议**不**在研究阶段自动批量抓取，改为在用户进入 page4 排版时**按需触发**。

推荐实现路径：

1. Image Studio 的 `/api/image-studio/search` 接口已支持 Tavily 图片搜索
2. 新增 `founder_photo` 的 Tavily query 策略：`"{founder_name} {company_name} headshot photo"`
3. 来自 `office_photo_hints.about_url` 和 `office_photo_hints.linkedin_url` 的 Playwright 抓取作为备选
4. 全失败时 fallback 到"无图占位"（排版层显示灰色人物轮廓 SVG）

### 8.3 tech_stack 字段（低风险）

该字段可从现有枚举字段（`stack_layer`、`ai_model_dependency`、`workflow_integration_level`）直接转化，即使官网/新闻中没有明确技术栈说明，也能产出有效内容，极少出现"暂缺"。

---

## 9. 执行清单与验收标准

### 执行顺序

**第一轮（数据层，约 1–2 天）**

- [ ] 新建 `db/migrations/004_v2_fields.sql`
- [ ] 执行迁移脚本（research_db）
- [ ] 更新 `contracts/fields.json`（新增 5 字段）
- [ ] 更新 `contracts/media.json`（新增 founder_photo）
- [ ] 更新 `prompts/layer3-field-extraction.md`
- [ ] 用一家新公司跑完整研究流程，确认新字段被提取到 research 表

**第二轮（后端逻辑，约半天）**

- [ ] 更新 `webapp/app.py`（6 处，见 §6.5）
- [ ] 更新 `webapp/db.py`（field_to_card 映射）
- [ ] 更新 `webapp/asset_store.py`（ASSET_KEYS + CARD_ASSET_MAP + ASSET_TO_CARD）
- [ ] 更新 `webapp/asset_resolver.py`（CARD_SPEC_VERSION + CARD_ASSET_SLOTS）
- [ ] 运行 `python3 -m pytest tests/test_app.py` — 验证 card_index 校验
- [ ] 运行 `python3 -m pytest tests/test_static_contracts.py` — 验证 contracts 一致性

**第三轮（排版层，约 1–2 天）**

- [ ] 更新 `docs/card-spec.md`（全文替换为 v2）
- [ ] 更新 `canvas/default-templates.json`（改为 7 张）
- [ ] 开发 page2 模板（含 company_achievement 展示区块）
- [ ] 开发 page3 模板（含 chart_ecosystem 嵌入 + tech_stack 展示区块）
- [ ] 开发 page4 模板（含 founder_photo 图片区块 + 团队信息区块）
- [ ] 开发 page5 模板（含财务字段条件折叠逻辑）
- [ ] 端到端测试：一家公司从研究 → 定稿 → 排版全流程

### 验收标准

| 验收项 | 通过条件 |
|---|---|
| card_index 校验 | POST /api/final/confirm 传 card_index=8 返回 400 |
| 新字段写入 | 研究完成后 research 表中存在 company_achievement、tech_stack 等列且有值 |
| chart_ecosystem 触发 | 确认 card_3 后 company_assets 中 chart_ecosystem.status 变为 ready |
| founder_photo 槽位 | ensure_assets_rows 调用后 company_assets 含 founder_photo 行 |
| 资产解析版本号 | GET /api/assets/resolved 返回 card_spec_version = "v2" |
| 废弃字段兼容 | 历史公司（含旧 timeline_events 数据）在研究台正常加载不报错 |
| 7 张卡片渲染 | 排版台导出 ZIP 包含且仅包含 card_1 ~ card_7 |
