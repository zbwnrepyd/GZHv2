# GZHv2 卡片规格 v2 — 完整技术改造文档（正式版）

**文档版本：** 2.0  
**目标 card_spec_version：** `v2`  
**基于代码库：** GZHv2-main（截止 2026-06-08）  
**核心变更：** 7 张新卡片规格 + 套卡系统 + 5 个新字段

---

## 目录

1. [变更概述](#1-变更概述)
2. [新版卡片规格（v2）](#2-新版卡片规格v2)
3. [字段变更清单](#3-字段变更清单)
4. [图片资产槽位变更](#4-图片资产槽位变更)
5. [套卡系统设计](#5-套卡系统设计)
6. [数据库迁移方案](#6-数据库迁移方案)
7. [文件改动详情](#7-文件改动详情)
8. [研究提示词更新](#8-研究提示词更新)
9. [数据可得性风险说明](#9-数据可得性风险说明)
10. [执行清单与验收标准](#10-执行清单与验收标准)

---

## 1. 变更概述

### 1.1 三条核心原则

**原则一：research 层全量保留。** 研究提示词只增不减，`timeline_events`、`other_products`、`hook_paragraph_1/2/3` 等字段继续被提取并存储在 research_db，不从 DB 删除列、不从提示词删除字段。v1 套卡仍可读取并渲染这些字段。

**原则二：财务字段扩展为运营指标。** 「营收」字段扩展为 `revenue_metrics`（ARR/MRR/GMV/总营收），「利润」字段扩展为 `growth_metrics`（MAU/DAU/付费用户数/企业客户数），均允许填入任何可公开获取的量化指标，找不到数据时统一填「暂缺」。

**原则三：套卡系统管理多版本卡片组。** 不替换旧卡片规格，而是在定稿台引入「套卡」概念：套卡1（v1·经典8张）和套卡2（v2·新7张）并存，用户可新建和删除自定义套卡。每家公司在每个套卡中独立维护确认状态。

### 1.2 变更范围一览

| 维度 | 变更内容 |
|---|---|
| 新增字段 | 5 个（research_db 加列） |
| 新增资产槽位 | 1 个（founder_photo） |
| 新增数据表 | 1 个（card_set_registry） |
| 改动数据表 | 3 个（card_compositions、card_items、final_content 加 card_set_key 列） |
| 改动数据表 | 1 个（default_card_configs 加 set_key 列，重建 UNIQUE 约束） |
| 新增 API 路由 | 4 个（套卡 CRUD + 套卡初始化） |
| 改动 API 路由 | 4 个（final/* 系列加 card_set_key 参数） |
| 改动的 Python 文件 | 5 个（app.py / db.py / asset_store.py / asset_resolver.py / card_config_repo.py） |
| 改动的合同文件 | 3 个（fields.json / media.json / card-spec.md） |
| 新建迁移文件 | 2 个（004_v2_fields.sql / 005_card_sets.sql） |

---

## 2. 新版卡片规格（v2）

### 2.1 卡片定义

| card_index | 主题 | 主要内容 | 触发的自动资产生成 |
|---|---|---|---|
| 1 | 封面 | 公司名、Logo | — |
| 2 | 公司概览 | 官网截图、地址、所属行业、主营业务、公司成就 | — |
| 3 | 产品与定位 | 生态位图、主要产品、技术栈 | 确认时触发 `chart_ecosystem` 渲染 |
| 4 | 创始人与团队 | 创始人照片、姓名、工作背景、学历背景、团队规模、团队背景 | — |
| 5 | 财务与市场 | 典型客户、营收/ARR/MRR、MAU/DAU/用户数、分地区市场、融资情况 | — |
| 6 | GTM 与增长 | GTM 策略、增长飞轮 | 确认时触发 `flywheel` SVG 渲染 |
| 7 | 竞争格局 | 竞争格局散点图、行业 Top3 竞对详情、公司竞争优势 | 确认时触发 `chart_competitive` 渲染 |

### 2.2 v1（套卡1）→ v2（套卡2）字段归属对比

| 字段 | v1 所在卡片 | v2 所在卡片 | 状态 |
|---|---|---|---|
| `company_name` | card_1 | card_1 | 不变 |
| `company_type` | card_1 | card_2 | 重映射 |
| `location` | card_2 | card_2 | 不变 |
| `company_def` | card_2 | card_2 | 不变 |
| `company_achievement` | — | card_2 | **新增** |
| `founder_name/edu/bg/achievement` | card_2 | card_4 | 重映射 |
| `team_size / team_highlight` | card_2 | card_4 | 重映射 |
| `funding_info` | card_2 | card_5 | 重映射 |
| `timeline_events` | card_3 | v1 only | research 层保留 |
| `main_product_*` | card_4 | card_3 | 重映射 |
| `tech_stack` | — | card_3 | **新增** |
| `ecosystem_niche` | card_7 | card_3 | 重映射 |
| `other_products` | card_5 | v1 only | research 层保留 |
| `customer_segment` | card_6 | card_5 | 重映射 |
| `revenue_metrics` | — | card_5 | **新增**（替代 revenue_model） |
| `growth_metrics` | — | card_5 | **新增** |
| `regional_markets` | — | card_5 | **新增** |
| `revenue_model` | card_6 | v1 only | research 层保留 |
| `gtm_strategy` | card_6 | card_6 | 不变 |
| `growth_flywheel` | card_6 | card_6 | 不变 |
| `cold_start` | card_6 | v1 only | research 层保留 |
| `moat` | card_7 | card_7 | 不变 |
| `competitors` | card_7 | card_7 | 不变 |
| `top3_competitors_summary` | — | card_7 | **新增**（从 competitors 数组合成） |
| `market_opportunity` | card_8 | v1 only | research 层保留 |
| `hook_paragraph_1/2/3` | card_8 | v1 only | research 层保留 |

---

## 3. 字段变更清单

### 3.1 新增字段（5 个，仅在 research_db 加列）

| field_key | field_label | type | v2 所属卡片 | 提取说明 |
|---|---|---|---|---|
| `company_achievement` | 公司成就 | long_text | card_2 | 公司整体里程碑：融资金额/轮次、知名客户签约、媒体引用数据、获奖。区别于 `main_product_achievement`（产品级）。100 字内，找不到填「暂缺」 |
| `tech_stack` | 技术栈 | long_text | card_3 | 结合 `stack_layer`/`ai_model_dependency` 枚举展开为可读描述：说明核心技术选型、自研 vs API 调用比例、使用的主要框架/模型。100 字内 |
| `revenue_metrics` | 营收指标 | text | card_5 | ARR / MRR / GMV / 总营收，任意财务规模数据。格式：「ARR $12M（2024Q4，TechCrunch）」。严禁估算，找不到填「暂缺」 |
| `growth_metrics` | 增长指标 | text | card_5 | MAU / DAU / 注册用户数 / 付费用户数 / 企业客户数，任意用户或增长规模数据。格式：「MAU 500万（2024Q3，官方公告）」。找不到填「暂缺」 |
| `regional_markets` | 分地区市场 | long_text | card_5 | 主要市场地区及占比，如「美国 60%、欧洲 25%、亚太 15%（2024年报）」。找不到填「暂缺」 |

> `top3_competitors_summary` 不是独立数据库字段，由提示词从 `competitors` 数组合成后作为独立 JSON 键输出，存入 research_db 的 `competitors_summary` 列（见第 8 节）。

### 3.2 v1 字段在 research 层的保留策略

以下字段**不从 research_db 删除列，不从提取提示词移除**，仅在 v2 套卡的 `default_card_configs` 中不出现（因此 v2 排版层不渲染）：

`timeline_events` / `other_products` / `hook_paragraph_1` / `hook_paragraph_2` / `hook_paragraph_3` / `market_opportunity` / `cold_start` / `revenue_model`

v1 套卡（套卡1）的 `default_card_configs` 继续引用这些字段，行为不变。

---

## 4. 图片资产槽位变更

### 4.1 新增：`founder_photo`

```
asset_key:   founder_photo
v2 归属:     card_4（创始人与团队）
kind:        collected
required:    false
```

**采集来源（优先级从高到低）：**

1. **Tavily 图片搜索**：query `"{founder_name} {company_name} headshot photo"`
2. **Playwright 抓取官网 About 页**：读取 `office_photo_hints.about_url`，抓取 `<img>` 中尺寸 ≥ 200×200 的人像图
3. **Playwright 抓取 LinkedIn 公开页**（需 stealth 模式）：读取 `office_photo_hints.linkedin_url`
4. 全部失败 → `status: failed`，排版层显示灰色人物轮廓占位 SVG

**过滤规则（与现有 image_quality 模块一致）：**
- aspect ratio 在 0.6 到 1.8 之间（排除横幅图）
- 宽度 ≥ 200px
- 非 logo / 产品截图（通过 `image_scorer.py` 的 content_type 分类）
- 不触发重复图检测（perceptual hash 对比现有资产）

> 建议：`founder_photo` 采集**不在研究阶段自动批量触发**，改为用户在定稿台打开 card_4 时按需触发（避免 LinkedIn 触发反爬）。

### 4.2 v2 资产槽位归属总表

| asset_key | v2 归属卡片 | 生成方式 | 必须 |
|---|---|---|---|
| `logo` | card_1 | collected | 是 |
| `website_screenshot` | card_2 | collected | 否 |
| `founder_photo` | card_4 | collected | 否 |
| `chart_ecosystem` | card_3 | generated/echarts | 否 |
| `product_main` | card_3 | collected | 否 |
| `flywheel` | card_6 | generated/svg | 否 |
| `chart_competitive` | card_7 | generated/echarts | 否 |
| `competitors` | card_7 | collected | 否 |
| `competitors_logo_strip` | card_7 | generated/composite | 否 |

**废弃槽位**（DB 行和 `ASSET_KEYS` 列表均保留，仅停止在 v2 套卡渲染）：
`office` / `timeline` / `products_other`

---

## 5. 套卡系统设计

### 5.1 核心概念

**套卡（Card Set）** 是一组卡片规格的集合，每个套卡对应一个 `card_spec_version`，并包含该版本下的默认卡片列表和字段映射。每家公司在每个套卡中独立维护确认状态（`final_content`）和编排结构（`card_compositions / card_items`）。

内置套卡由系统预置，不可删除：
- **套卡1（v1 · 经典8张）**：当前所有已确认内容默认归属此套卡
- **套卡2（v2 · 新7张）**：本次新增，按新规格提取与排版

用户可以在两个内置套卡基础上新建自定义套卡（基于 v1 或 v2 规格），并删除自定义套卡（内置套卡不可删）。

### 5.2 数据模型

#### 新建表：`card_set_registry`（建在 composition_db）

```sql
CREATE TABLE IF NOT EXISTS card_set_registry (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    set_key        TEXT    NOT NULL UNIQUE,        -- "v1" / "v2" / 用户自定义
    display_name   TEXT    NOT NULL,               -- "套卡1 · 经典8张"
    spec_version   TEXT    NOT NULL,               -- "v1" 或 "v2"（决定用哪套 default_card_configs）
    card_count     INTEGER NOT NULL,               -- 8 / 7
    is_system      INTEGER NOT NULL DEFAULT 0,     -- 1=内置不可删
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO card_set_registry
    (set_key, display_name, spec_version, card_count, is_system)
VALUES
    ('v1', '套卡1 · 经典8张', 'v1', 8, 1),
    ('v2', '套卡2 · 新版7张', 'v2', 7, 1);
```

#### 改动：`default_card_configs`（在 composition_db）

原 UNIQUE 为 `card_id`，改为 `(set_key, card_id)`，并新增 v2 套卡的 7 条默认配置：

```sql
-- 见 §6 迁移 SQL
```

#### 改动：`card_compositions`（在 composition_db）

原 UNIQUE 为 `(company_name, card_id)`，改为 `(company_name, card_set_key, card_id)`：

```sql
-- 新增列
card_set_key TEXT NOT NULL DEFAULT 'v1'
-- UNIQUE 约束重建（见 §6 迁移 SQL）
```

#### 改动：`card_items`（在 composition_db）

```sql
ALTER TABLE card_items ADD COLUMN card_set_key TEXT NOT NULL DEFAULT 'v1';
CREATE INDEX idx_card_items_set ON card_items(company_name, card_set_key, card_id);
```

#### 改动：`final_content`（在 final_db）

原 UNIQUE INDEX 为 `(company_name, card_index, field_name)`，改为 `(company_name, card_set_key, card_index, field_name)`：

```sql
-- 新增列
card_set_key TEXT NOT NULL DEFAULT 'v1'
-- UNIQUE INDEX 重建（见 §6 迁移 SQL）
```

### 5.3 API 接口

#### 新增路由

```
GET    /api/card-sets
       → 返回 card_set_registry 全部记录
       → Response: [{set_key, display_name, spec_version, card_count, is_system, created_at}, ...]

POST   /api/card-sets
       → Body: {display_name: "我的套卡", base_spec: "v1"|"v2"}
       → 在 card_set_registry 插入新行（is_system=0）
       → set_key 自动生成：user_{timestamp}
       → Response: {set_key, display_name, spec_version, card_count}

DELETE /api/card-sets/<set_key>
       → 校验 is_system=0（内置套卡返回 403）
       → 不删除某公司已确认数据，只删除 registry 条目（公司数据由下方接口清除）
       → Response: {status: "ok"}

POST   /api/final/<company>/init-set/<set_key>
       → 读取 card_set_registry 中 set_key 对应的 spec_version
       → 从 default_card_configs WHERE set_key=spec_version 读取默认配置
       → 批量写入 card_compositions + card_items（幂等，已有则跳过）
       → Response: {status: "ok", cards_created: N}

DELETE /api/final/<company>/set/<set_key>
       → 删除该公司在此套卡的所有已确认数据
       → DELETE FROM final_content WHERE company_name=? AND card_set_key=?
       → DELETE FROM card_compositions WHERE company_name=? AND card_set_key=?
       → DELETE FROM card_items WHERE company_name=? AND card_set_key=?
       → 仅在用户点击删除套卡时触发（确认弹窗后调用此接口，再调用 DELETE /api/card-sets/<set_key>）
       → Response: {status: "ok", deleted_cards: N}
```

#### 改动的现有路由

所有 `/api/final/*` 路由新增可选 query 参数 `?set=<set_key>`，默认值为 `"v1"`（向后兼容）：

```
POST /api/final/save
     → Body 新增字段：card_set_key（可选，默认 "v1"）

GET  /api/final/status/<company>?set=v2
     → 返回该公司在指定套卡中的确认进度
     → Response: {confirmed: [1,3,6], total: 7, set_key: "v2"}

GET  /api/final/card/<company>/<card_index>?set=v2
     → 读取指定套卡 + 卡片的 markdown_full

GET  /api/final/export/<company>?set=v2
     → 导出指定套卡的全部已确认卡片
```

> `/api/research/*` 路由**不受影响**（研究层无套卡概念，所有套卡共用同一份研究数据）。

### 5.4 前端 UI（定稿台）

#### 套卡选择器

在定稿台顶部卡片列表上方插入套卡选择器 Tab 栏：

```
┌─────────────────────────────────────────────────────────┐
│  [套卡1 · 经典8张]  [套卡2 · 新版7张 ×]  [+ 新建套卡]  │
└─────────────────────────────────────────────────────────┘
```

- 选中的 Tab 高亮显示
- 内置套卡（`is_system=1`）不显示 × 删除按钮
- 用户自定义套卡显示 × 删除按钮（灰色，hover 变红）
- Tab 右上角显示该套卡的确认进度角标（如「3/7」）

#### 切换套卡

切换时调用 `GET /api/final/status/<company>?set=<set_key>` 和 `GET /api/card-sets`，重新渲染卡片列表。

若该公司在目标套卡中**尚无 card_compositions 记录**，自动调用 `POST /api/final/<company>/init-set/<set_key>` 初始化默认配置（后台静默完成，不打断用户操作）。

#### 新建套卡

点击「+ 新建套卡」展开 Modal：

```
┌──────────────────────────────┐
│  新建套卡                    │
│                              │
│  套卡名称  [____________]    │
│                              │
│  基于规格  ○ v1（8张）       │
│            ● v2（7张）       │
│                              │
│       [取消]  [创建]         │
└──────────────────────────────┘
```

点击「创建」：
1. `POST /api/card-sets` → 获得新 `set_key`
2. `POST /api/final/<company>/init-set/<new_set_key>` → 初始化编排结构
3. 自动切换到新套卡 Tab

#### 删除套卡（用户自定义）

点击套卡 Tab 上的 × 按钮，展开确认弹窗：

```
┌──────────────────────────────────────────────┐
│  删除套卡「我的套卡」？                       │
│                                              │
│  将同时删除该公司在此套卡中所有已确认内容。   │
│  此操作不可撤销。                            │
│                                              │
│                    [取消]  [确认删除]        │
└──────────────────────────────────────────────┘
```

点击「确认删除」：
1. `DELETE /api/final/<company>/set/<set_key>` → 清除公司数据
2. `DELETE /api/card-sets/<set_key>` → 删除套卡注册
3. 切换回套卡1 Tab

---

## 6. 数据库迁移方案

### 6.1 迁移文件 004：`db/migrations/004_v2_fields.sql`（作用于 research_db）

```sql
-- GZHv2 Migration 004 — 新增 v2 字段到 research 表
-- 执行：sqlite3 /opt/ai/data/research_db.sqlite < db/migrations/004_v2_fields.sql

ALTER TABLE research ADD COLUMN company_achievement TEXT;
ALTER TABLE research ADD COLUMN tech_stack           TEXT;
ALTER TABLE research ADD COLUMN revenue_metrics      TEXT;
ALTER TABLE research ADD COLUMN growth_metrics       TEXT;
ALTER TABLE research ADD COLUMN regional_markets     TEXT;
ALTER TABLE research ADD COLUMN competitors_summary  TEXT;  -- top3 合成文本
```

### 6.2 迁移文件 005：`db/migrations/005_card_sets.sql`（作用于 composition_db + final_db）

```sql
-- GZHv2 Migration 005 — 套卡系统
-- 需对两个数据库分别执行：
--   sqlite3 /opt/ai/data/composition_db.sqlite < db/migrations/005_card_sets.sql
--   sqlite3 /opt/ai/data/final_db.sqlite < db/migrations/005_card_sets_final.sql
-- （实操时可拆分为两个文件，此处合并描述）

-- ─────────────────────────────────────────
-- A. composition_db 部分
-- ─────────────────────────────────────────

-- 1. 新建 card_set_registry
CREATE TABLE IF NOT EXISTS card_set_registry (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    set_key        TEXT    NOT NULL UNIQUE,
    display_name   TEXT    NOT NULL,
    spec_version   TEXT    NOT NULL,
    card_count     INTEGER NOT NULL,
    is_system      INTEGER NOT NULL DEFAULT 0,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO card_set_registry
    (set_key, display_name, spec_version, card_count, is_system)
VALUES
    ('v1', '套卡1 · 经典8张', 'v1', 8, 1),
    ('v2', '套卡2 · 新版7张', 'v2', 7, 1);

-- 2. 重建 default_card_configs（加 set_key，更新 UNIQUE 约束）
CREATE TABLE default_card_configs_new (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    set_key      TEXT    NOT NULL DEFAULT 'v1',
    card_id      TEXT    NOT NULL,
    card_index   INTEGER NOT NULL,
    card_title   TEXT    NOT NULL,
    config_json  TEXT    NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(set_key, card_id)
);

INSERT INTO default_card_configs_new
    (set_key, card_id, card_index, card_title, config_json, created_at)
SELECT 'v1', card_id, card_index, card_title, config_json, created_at
FROM default_card_configs;

DROP TABLE default_card_configs;
ALTER TABLE default_card_configs_new RENAME TO default_card_configs;

-- 插入 v2 套卡的 7 张默认配置
INSERT OR IGNORE INTO default_card_configs
    (set_key, card_id, card_index, card_title, config_json)
VALUES
('v2','v2_card_01',1,'封面',
 '{"fields":["company_name"],"media":["logo"],"template_id":"cover_v2"}'),
('v2','v2_card_02',2,'公司概览',
 '{"fields":["location","company_type","company_def","company_achievement","website_url"],"media":["website_screenshot"],"template_id":"overview_v2"}'),
('v2','v2_card_03',3,'产品与定位',
 '{"fields":["main_product_name","main_product_def","main_product_highlight","main_product_achievement","tech_stack","ecosystem_niche"],"media":["chart_ecosystem","product_main"],"template_id":"product_v2"}'),
('v2','v2_card_04',4,'创始人与团队',
 '{"fields":["founder_name","founder_edu","founder_bg","founder_achievement","team_size","team_highlight"],"media":["founder_photo"],"template_id":"founder_v2"}'),
('v2','v2_card_05',5,'财务与市场',
 '{"fields":["customer_segment","revenue_metrics","growth_metrics","regional_markets","funding_info"],"media":[],"template_id":"finance_v2"}'),
('v2','v2_card_06',6,'GTM与增长',
 '{"fields":["gtm_strategy","growth_flywheel"],"media":["flywheel"],"template_id":"gtm_v2"}'),
('v2','v2_card_07',7,'竞争格局',
 '{"fields":["moat","competitors","competitors_summary"],"media":["competitors_logo_strip","chart_competitive"],"template_id":"competitive_v2"}');

-- 3. 重建 card_compositions（加 card_set_key，更新 UNIQUE 约束）
CREATE TABLE card_compositions_new (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT    NOT NULL,
    card_set_key TEXT    NOT NULL DEFAULT 'v1',
    card_id      TEXT    NOT NULL,
    card_index   INTEGER NOT NULL,
    card_title   TEXT    NOT NULL,
    enabled      INTEGER DEFAULT 1,
    template_id  TEXT,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_name, card_set_key, card_id)
);

INSERT INTO card_compositions_new
    (id, company_name, card_set_key, card_id, card_index,
     card_title, enabled, template_id, created_at, updated_at)
SELECT id, company_name, 'v1', card_id, card_index,
       card_title, enabled, template_id, created_at, updated_at
FROM card_compositions;

DROP TABLE card_compositions;
ALTER TABLE card_compositions_new RENAME TO card_compositions;
CREATE INDEX idx_card_compositions_company
    ON card_compositions(company_name, card_set_key);

-- 4. card_items 加 card_set_key
ALTER TABLE card_items ADD COLUMN card_set_key TEXT NOT NULL DEFAULT 'v1';
CREATE INDEX idx_card_items_set
    ON card_items(company_name, card_set_key, card_id);

-- ─────────────────────────────────────────
-- B. final_db 部分（005_card_sets_final.sql）
-- ─────────────────────────────────────────

-- 重建 final_content（加 card_set_key，更新 UNIQUE 约束）
CREATE TABLE final_content_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name    TEXT    NOT NULL,
    card_set_key    TEXT    NOT NULL DEFAULT 'v1',
    card_index      INTEGER NOT NULL,
    field_name      TEXT    NOT NULL,
    field_value     TEXT,
    img_local_path  TEXT,
    confirmed_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO final_content_new
    (id, company_name, card_set_key, card_index,
     field_name, field_value, img_local_path, confirmed_at)
SELECT id, company_name, 'v1', card_index,
       field_name, field_value, img_local_path, confirmed_at
FROM final_content;

DROP TABLE final_content;
ALTER TABLE final_content_new RENAME TO final_content;

CREATE INDEX idx_final_company ON final_content(company_name);
CREATE INDEX idx_final_card
    ON final_content(company_name, card_set_key, card_index);
CREATE UNIQUE INDEX idx_final_unique_field
    ON final_content(company_name, card_set_key, card_index, field_name);
```

### 6.3 执行顺序

```bash
# Step 1: research_db（新增字段列）
sqlite3 /opt/ai/data/research_db.sqlite < db/migrations/004_v2_fields.sql

# Step 2: composition_db（套卡系统）
sqlite3 /opt/ai/data/composition_db.sqlite < db/migrations/005_card_sets.sql

# Step 3: final_db（套卡系统，final_content 部分）
sqlite3 /opt/ai/data/final_db.sqlite < db/migrations/005_card_sets_final.sql

# Step 4: 验证
sqlite3 /opt/ai/data/composition_db.sqlite ".tables"
sqlite3 /opt/ai/data/composition_db.sqlite "SELECT * FROM card_set_registry;"
sqlite3 /opt/ai/data/final_db.sqlite "PRAGMA table_info(final_content);"
```

---

## 7. 文件改动详情

### 7.1 `contracts/fields.json`

在 `basic` 组末尾追加：

```json
{"field_key": "company_achievement", "field_label": "公司成就",     "type": "long_text", "required": false}
```

在 `product` 组末尾追加：

```json
{"field_key": "tech_stack",          "field_label": "技术栈",       "type": "long_text", "required": false}
```

在 `business` 组末尾追加（4 个）：

```json
{"field_key": "revenue_metrics",     "field_label": "营收指标",     "type": "text",      "required": false},
{"field_key": "growth_metrics",      "field_label": "增长指标",     "type": "text",      "required": false},
{"field_key": "regional_markets",    "field_label": "分地区市场",   "type": "long_text", "required": false},
{"field_key": "competitors_summary", "field_label": "竞对Top3摘要", "type": "long_text", "required": false}
```

---

### 7.2 `contracts/media.json`

在 `logo` 条目后插入：

```json
{
  "media_key": "founder_photo",
  "media_label": "创始人照片",
  "kind": "collected",
  "required": false,
  "card_v2": 4
}
```

将 `timeline` / `office` / `products_other` 条目加上 `"deprecated": true`（不删除）：

```json
{"media_key": "timeline",        "deprecated": true, ...},
{"media_key": "office",          "deprecated": true, ...},
{"media_key": "products_other",  "deprecated": true, ...}
```

---

### 7.3 `webapp/asset_store.py`

**改动 1：** `ASSET_KEYS` 加入 `founder_photo`

```python
ASSET_KEYS = [
    "logo", "website_screenshot", "founder_photo",
    "product_main",
    "competitors", "competitors_logo_strip",
    "flywheel", "chart_competitive", "chart_ecosystem",
    # 废弃槽位：DB 行保留，停止在 v2 渲染
    "office", "products_other", "timeline",
]
```

**改动 2：** `CARD_ASSET_MAP` 更新（v2 归属）

```python
# v2 卡片→主资产映射（影响 CARD_ASSET_SLOTS 和图片采集调度）
CARD_ASSET_MAP_V2 = {
    1: "logo",
    2: "website_screenshot",
    3: "product_main",     # chart_ecosystem 由 card_3 确认事件单独触发
    4: "founder_photo",
    5: None,
    6: "flywheel",
    7: "competitors",
}

# 原 CARD_ASSET_MAP 保留（v1 仍使用）
CARD_ASSET_MAP = {
    1: "logo",
    2: "office",
    3: "timeline",
    4: "product_main",
    5: "products_other",
    6: "flywheel",
    7: "competitors",
}

ASSET_TO_CARD_V2 = {v: k for k, v in CARD_ASSET_MAP_V2.items() if v}
ASSET_TO_CARD_V2.update({
    "competitors_logo_strip": 7,
    "chart_competitive":      7,
    "chart_ecosystem":        3,   # v2 改为 card_3
})
```

---

### 7.4 `webapp/asset_resolver.py`

**改动 1：** 版本号升级

```python
CARD_SPEC_VERSION = "v2"
```

**改动 2：** `CARD_ASSET_SLOTS` 区分 v1/v2

```python
CARD_ASSET_SLOTS = {
    "v1": {
        1: ["logo"],
        2: ["office", "website_screenshot"],
        3: ["timeline"],
        4: ["product_main"],
        5: ["products_other"],
        6: ["flywheel"],
        7: ["competitors", "competitors_logo_strip", "chart_competitive",
            "chart_ecosystem"],
    },
    "v2": {
        1: ["logo"],
        2: ["website_screenshot"],
        3: ["chart_ecosystem", "product_main"],
        4: ["founder_photo"],
        5: [],
        6: ["flywheel"],
        7: ["competitors", "competitors_logo_strip", "chart_competitive"],
    },
}
```

---

### 7.5 `webapp/app.py`（6 处改动）

**改动 1 + 2（第 211、666 行）：** card_index 校验改为「根据套卡动态判断上限」

```python
# 修改前（两处相同）
if card_index < 1 or card_index > 8:
    return jsonify({"error": "card_index 必须在 1-8 之间"}), 400

# 修改后
card_set_key = data.get("card_set_key", "v1")
max_card = 7 if card_set_key == "v2" else 8
if card_index < 1 or card_index > max_card:
    return jsonify({"error": f"card_index 超出套卡 {card_set_key} 范围（1-{max_card}）"}), 400
```

**改动 3（save_final_card 路由，第 650 行）：** 透传 `card_set_key`

```python
@app.route("/api/final/save", methods=["POST"])
def save_final_card():
    data = request.get_json()
    company_name    = data.get("company_name")
    card_index      = data.get("card_index")
    card_set_key    = data.get("card_set_key", "v1")      # ← 新增
    markdown_content = data.get("markdown_content")
    fields          = data.get("fields", {})
    img_paths       = data.get("img_paths", {})

    # ... 校验同上 ...

    if markdown_content is not None:
        database.save_final_markdown(
            config.DB_PATH_FINAL, company_name, card_index,
            markdown_content, card_set_key=card_set_key   # ← 透传
        )
    else:
        database.save_final_card(
            config.DB_PATH_FINAL, company_name, card_index,
            fields, img_paths, card_set_key=card_set_key  # ← 透传
        )

    # 图表触发根据套卡版本判断
    spec = "v2" if card_set_key == "v2" else "v1"
    if spec == "v2" and card_index == 3:
        threading.Thread(target=_generate_ecosystem_chart,
                         args=(company_name,), daemon=True).start()
    if spec == "v1" and card_index in (3, 6):
        _pre_extract_svg_data(company_name, card_index)
    if card_index == 6 and spec == "v2":
        _pre_extract_svg_data(company_name, card_index)
    if card_index == 7:
        threading.Thread(target=_generate_card7_charts,
                         args=(company_name,), daemon=True).start()
```

**改动 4：** 新增 `_generate_ecosystem_chart` 函数（紧接 `_generate_card7_charts` 之后）

```python
def _generate_ecosystem_chart(company_name: str) -> None:
    """卡片3确认后（v2套卡）自动生成产业链生态位图，后台线程调用。"""
    try:
        init_assets_db(config.DB_PATH_ASSETS)
        ensure_assets_rows(config.DB_PATH_ASSETS, company_name)
        companies = _load_all_scored_companies(config.DB_PATH_RESEARCH)
        dest_dir = _company_image_dir(config.IMAGES_DIR, company_name)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, "chart_ecosystem.png")
        ok = render_stack_positioning(companies, company_name, dest)
        status = "ready" if ok else "failed"
        update_asset(
            config.DB_PATH_ASSETS, company_name, "chart_ecosystem",
            local_path=dest if ok else None,
            source_type="echarts_render", status=status,
        )
    except Exception as e:
        import logging
        logging.warning(f"[ecosystem_chart] {company_name}: {e}")
```

**改动 5（第 692 行）：** `get_final_status` 路由加 `set` 参数

```python
@app.route("/api/final/status/<company>")
def get_final_status(company: str):
    set_key = request.args.get("set", "v1")
    return jsonify(database.get_final_status(
        config.DB_PATH_FINAL, company, card_set_key=set_key
    ))
```

**改动 6（第 1873 行）：** 全卡片审稿提示词

```python
# 修改前
prompt = f"""你是专业编辑。以下是一家AI创业公司的8张知识卡片全部内容（{version}版）。

# 修改后（根据套卡动态）
total = 7 if card_set_key == "v2" else 8
prompt = f"""你是专业编辑。以下是一家AI创业公司的{total}张知识卡片全部内容（{version}版）。
```

---

### 7.6 `webapp/db.py`（3 处改动）

**改动 1（第 514 行）：** `save_final_card` 加 `card_set_key` 参数

```python
def save_final_card(
    db_path: str,
    company_name: str,
    card_index: int,
    fields: dict[str, str],
    img_paths: dict[str, str] = None,
    card_set_key: str = "v1",          # ← 新增
):
    img_paths = img_paths or {}
    with get_db(db_path) as conn:
        _ensure_final_unique_index(conn)
        for field_name, field_value in fields.items():
            img_local_path = img_paths.get(field_name)
            conn.execute(
                """INSERT INTO final_content
                   (company_name, card_set_key, card_index, field_name,
                    field_value, img_local_path)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(company_name, card_set_key, card_index, field_name)
                   DO UPDATE SET
                     field_value=excluded.field_value,
                     img_local_path=COALESCE(excluded.img_local_path,
                                             final_content.img_local_path),
                     confirmed_at=CURRENT_TIMESTAMP""",
                (company_name, card_set_key, card_index,
                 field_name, field_value, img_local_path),
            )
        conn.commit()
```

**改动 2（第 605 行）：** `get_final_status` 加 `card_set_key` 参数

```python
def get_final_status(db_path: str, company_name: str,
                     card_set_key: str = "v1") -> dict:
    cards = get_final_cards(db_path, company_name, card_set_key=card_set_key)
    confirmed = sorted({c["card_index"] for c in cards
                        if c["field_name"] == "markdown_full"} or
                       {c["card_index"] for c in cards})
    total = 7 if card_set_key == "v2" else 8
    return {
        "company_name": company_name,
        "card_set_key": card_set_key,
        "confirmed": confirmed,
        "total": total,
    }
```

**改动 3（第 596 行）：** `field_to_card` 映射更新

```python
# 修改前
field_to_card = {"timeline_events": 3, "growth_flywheel": 6}

# 修改后（仅保留仍有 final_content 回退需要的映射）
field_to_card = {
    "timeline_events": 3,   # v1 套卡仍需
    "growth_flywheel":  6,  # 两套卡共用
}
```

---

### 7.7 `webapp/repositories/card_config_repo.py`（4 处改动）

**改动 1：** `get_default_card_configs` 加 `set_key` 过滤

```python
def get_default_card_configs(db_path: str, set_key: str = "v1") -> list[dict]:
    with _get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM default_card_configs
               WHERE set_key=? ORDER BY card_index""",
            (set_key,)
        ).fetchall()
        # ... 解析 config_json 同原逻辑 ...
```

**改动 2：** `create_card` 加 `card_set_key` 参数

```python
def create_card(db_path: str, company_name: str, card_id: str,
                card_index: int, card_title: str, template_id: str = "",
                enabled: bool = True, card_set_key: str = "v1") -> int:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO card_compositions
               (company_name, card_set_key, card_id, card_index,
                card_title, template_id, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (company_name, card_set_key, card_id, card_index,
             card_title, template_id, 1 if enabled else 0))
        conn.commit()
        return cur.lastrowid
```

**改动 3：** `get_cards` / `get_enabled_cards` 加 `card_set_key` 过滤

```python
def get_cards(db_path: str, company_name: str,
              card_set_key: str = "v1") -> list[dict]:
    with _get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM card_compositions
               WHERE company_name=? AND card_set_key=?
               ORDER BY card_index""",
            (company_name, card_set_key)).fetchall()
        return [dict(r) for r in rows]
```

**改动 4：** 新增 `init_company_set` 函数（供 `POST /api/final/<company>/init-set/<set_key>` 调用）

```python
def init_company_set(composition_db: str, company_name: str,
                     set_key: str, spec_version: str) -> int:
    """
    从 default_card_configs 读取指定 spec_version 的默认配置，
    批量写入 card_compositions + card_items（幂等，已有则跳过）。
    返回实际创建的卡片数。
    """
    configs = get_default_card_configs(composition_db, set_key=spec_version)
    created = 0
    for cfg in configs:
        card_id   = cfg["card_id"]
        card_idx  = cfg["card_index"]
        card_title = cfg["card_title"]
        template_id = cfg["config"].get("template_id", "")
        # 幂等检查
        existing = get_card_by_set(composition_db, company_name,
                                   set_key, card_id)
        if existing:
            continue
        row_id = create_card(
            composition_db, company_name, card_id, card_idx,
            card_title, template_id, enabled=True,
            card_set_key=set_key,
        )
        # 写入 card_items
        fields = cfg["config"].get("fields", [])
        media  = cfg["config"].get("media", [])
        for i, fk in enumerate(fields):
            add_card_item(composition_db, company_name, card_id,
                          "field", fk, sort_order=i,
                          display_role="body", card_set_key=set_key)
        for i, mk in enumerate(media):
            add_card_item(composition_db, company_name, card_id,
                          "media", mk, sort_order=i,
                          display_role="hero_image", card_set_key=set_key)
        created += 1
    return created
```

---

### 7.8 `docs/card-spec.md`

全文替换为 v2 规格（版本号、卡片表、资产槽位表、触发规则均按第 2 节内容）。

---

### 7.9 `canvas/default-templates.json`

将 v2 套卡的 7 张模板占位加入（key 为 `"v2_1"` 到 `"v2_7"`，不替换原有 `"1"` 到 `"8"` 的 v1 模板）：

```json
{
  "_sets": [
    {
      "name": "套卡1 · 经典8张（v1）",
      "set_key": "v1",
      "cards": {
        "1": "<!-- 封面 -->",
        ...
        "8": "<!-- 总结 -->"
      }
    },
    {
      "name": "套卡2 · 新版7张（v2）",
      "set_key": "v2",
      "cards": {
        "1": "<!-- 封面 v2 -->",
        "2": "<!-- 公司概览 v2 -->",
        "3": "<!-- 产品与定位 v2 -->",
        "4": "<!-- 创始人与团队 v2 -->",
        "5": "<!-- 财务与市场 v2 -->",
        "6": "<!-- GTM与增长 v2 -->",
        "7": "<!-- 竞争格局 v2 -->"
      }
    }
  ]
}
```

---

## 8. 研究提示词更新

### 8.1 `prompts/layer3-field-extraction.md` — 新增字段（只增不减）

在 `company_def` 字段说明后追加：

```json
"company_achievement": "公司级别成就（100字内）。聚焦公司整体里程碑而非单一产品：已完成的融资轮次与金额、签约的知名客户名称、获得的媒体引用数据或奖项认可、用户规模里程碑。与 main_product_achievement 区分：前者写公司，后者写产品。找不到填「暂缺」。"
```

在 `main_product_achievement` 后追加：

```json
"tech_stack": "技术栈描述（100字内）。结合 stack_layer 和 ai_model_dependency 枚举展开为可读文字：核心技术选型是什么（如：基于 GPT-4o API + 自研 RAG 管道）、主要编程语言/框架、自研与调用第三方 API 的比例说明。"
```

在 `growth_flywheel` 后追加（整块财务/市场字段）：

```json
"revenue_metrics": "财务规模类量化指标（一句话）。包括但不限于：ARR（年度经常性收入）、MRR（月度经常性收入）、GMV、总营收、ACV（年度合同价值）。格式：「ARR $12M（2024Q4，来源：TechCrunch）」。严禁估算，找不到公开数据填「暂缺」。",

"growth_metrics": "用户/增长规模类量化指标（一句话）。包括但不限于：MAU（月活）、DAU（日活）、注册用户数、付费用户数、企业客户数、NPS 值、交易量。格式：「MAU 500万（2024Q3，官方公告）」。找不到填「暂缺」。",

"regional_markets": "主要市场地区及比例（100字内）。如「美国占 60%、欧洲 25%、亚太 15%（2024年报）」，或「主要服务北美企业客户，已进入欧洲市场（官网）」。找不到填「暂缺」。",

"competitors_summary": "Top3 竞争对手的一句话对比摘要（150字内）。从 competitors 数组中取排名前3，按格式输出：「【竞品A】核心产品 X，关键数据 Y；【竞品B】核心产品 X，关键数据 Y；【竞品C】...」。若 competitors 不足3个则据实填写。"
```

### 8.2 `competitors` 数组说明更新

```json
"competitors": [
  {
    "name":    "竞品公司名",
    "product": "核心产品名",
    "data":    "关键运营数据（含来源注明）",
    "url":     "竞品官网 URL",
    "rank":    1
  }
]
```

新增 `rank` 字段（整数 1~N，1 = 最直接竞争对手），用于 `competitors_summary` 合成时的排序依据。

### 8.3 保留原有字段（不从提示词删除）

以下字段继续出现在 JSON 输出模板中，提取逻辑不变：

`timeline_events` / `other_products` / `hook_paragraph_1/2/3` / `market_opportunity` / `cold_start` / `revenue_model`

在这些字段上方加注释说明：

```
// 以下字段归属套卡1（v1·经典8张），v2套卡不渲染但仍提取存储
```

---

## 9. 数据可得性风险说明

### 9.1 财务指标（中风险）

`revenue_metrics` 和 `growth_metrics` 对**Pre-A 至 Series B** 阶段的公司，公开数据获取率约 40%，大多数早期公司不主动披露。但相比纯财务指标，运营指标（MAU/付费用户数）在新闻报道和官网中的披露率更高，两个字段至少有一个能填出有效值的概率约 60%。

`regional_markets` 对中小型 AI 初创公司的数据获取率约 30%，大多数公司官网不明确列出市场分布。

**排版层建议（page5 条件折叠）：**

```
若 revenue_metrics == "暂缺" AND growth_metrics == "暂缺"：
  → 财务指标区块折叠，改展示「融资时间线」（从 funding_info 解析）

若 regional_markets == "暂缺"：
  → 分地区市场区块折叠，用 customer_segment 的典型客户地区信息补位
```

### 9.2 创始人照片（中风险）

不在研究阶段批量抓取（避免 LinkedIn 反爬触发封禁）。建议在排版台 card_4 首次打开时按需触发 Tavily 图搜 → 官网 About 页 → LinkedIn 三级策略。预计约 70% 的公司能获取到满足质量要求的照片（宽度 ≥ 200px，人像图）。

### 9.3 `tech_stack` 字段（低风险）

可从现有 `stack_layer`（枚举）和 `ai_model_dependency`（枚举）转化补充，即使官网无明确技术说明，也能产出有用内容，预计「暂缺」率低于 5%。

---

## 10. 执行清单与验收标准

### 10.1 三轮执行计划

**第一轮：数据层（1–2 天）**

- [ ] 新建 `db/migrations/004_v2_fields.sql` 并执行
- [ ] 新建 `db/migrations/005_card_sets.sql` + `005_card_sets_final.sql` 并执行
- [ ] 验证 `research_db` 的 5 个新列存在
- [ ] 验证 `card_set_registry` 有 v1/v2 两条记录
- [ ] 验证 `final_content` 含 `card_set_key` 列且历史数据 `card_set_key='v1'`
- [ ] 更新 `contracts/fields.json`（4 个新字段）
- [ ] 更新 `contracts/media.json`（founder_photo + deprecated 标记）
- [ ] 更新 `prompts/layer3-field-extraction.md`（新增字段，保留原字段）
- [ ] 用一家新公司跑研究流程，验证 `company_achievement`、`revenue_metrics` 等被提取写入

**第二轮：后端逻辑（半天–1 天）**

- [ ] 更新 `webapp/app.py`（6 处）
- [ ] 更新 `webapp/db.py`（3 处）
- [ ] 更新 `webapp/asset_store.py`
- [ ] 更新 `webapp/asset_resolver.py`
- [ ] 更新 `webapp/repositories/card_config_repo.py`（4 处 + 新函数）
- [ ] 在 `app.py` 新增套卡 CRUD 路由（4 个）
- [ ] 运行 `python3 -m pytest tests/test_db.py` — 验证 save_final_card 签名变化
- [ ] 运行 `python3 -m pytest tests/test_static_contracts.py`

**第三轮：前端与排版层（1–3 天）**

- [ ] 定稿台：套卡选择器 Tab 栏（从 `/api/card-sets` 加载）
- [ ] 定稿台：新建套卡 Modal
- [ ] 定稿台：删除套卡确认弹窗
- [ ] 定稿台：所有卡片操作调用加 `card_set_key` 参数
- [ ] 更新 `docs/card-spec.md`（v2 规格）
- [ ] 更新 `canvas/default-templates.json`（加 v2 套卡结构）
- [ ] 开发 page3 模板（含 `chart_ecosystem` 嵌入 + `tech_stack` 展示）
- [ ] 开发 page4 模板（含 `founder_photo` 图片区块）
- [ ] 开发 page5 模板（含财务字段条件折叠）
- [ ] 端到端测试：同一公司在套卡1和套卡2分别完成 → 导出 → 验证两份导出互不干扰

### 10.2 验收标准

| 验收项 | 通过条件 |
|---|---|
| 套卡注册表 | `GET /api/card-sets` 返回 v1、v2 两条内置记录 |
| 套卡新建 | `POST /api/card-sets` 后 card_set_registry 新增一行，is_system=0 |
| 套卡删除 | 删除用户套卡后，该公司在此套卡的 final_content 和 card_compositions 全部清除 |
| 内置套卡保护 | `DELETE /api/card-sets/v1` 返回 403 |
| 独立确认状态 | 套卡1 card_3 已确认，套卡2 card_3 未确认，两者 status 互不影响 |
| 历史数据兼容 | 迁移后所有旧公司的 final_content.card_set_key 均为 'v1'，定稿台正常加载 |
| v2 chart_ecosystem | 套卡2 card_3 确认后，company_assets 中 chart_ecosystem.status 变为 ready |
| founder_photo 槽位 | ensure_assets_rows 调用后，company_assets 含 founder_photo 行 |
| card_index 校验 | v2 套卡传 card_index=8 返回 400；v1 套卡传 card_index=8 返回 200 |
| 7张卡片导出 | v2 套卡导出 ZIP 含且仅含 card_1～card_7 |
| 8张卡片导出 | v1 套卡导出 ZIP 含且仅含 card_1～card_8 |
| 财务字段暂缺 | page5 条件折叠正常工作：营收/增长均为「暂缺」时显示融资时间线 |
