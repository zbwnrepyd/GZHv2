# GZHv2 研究链路全面采集修复技术文档

## 0. 核心结论

`Limitless` 和 `limitless` 结果不一致，不应只用“首字母大写搜一次、小写搜一次”解决。那只能提高一部分召回，但会放大重复公司、重复字段、重复图片资产的问题。

必须同时做 5 件事：

1. **公司身份归一化**：展示名保留 `Limitless`，数据库主身份使用稳定的 `company_key`，优先取官网域名，例如 `limitless.ai`。
2. **搜索词扩展**：同时搜原始名、小写名、首字母大写名、域名、去后缀域名、引号精确组合。
3. **多意图采集**：按创始人、融资、产品、定价、竞品、GTM、访谈、官方资料等意图生成 query，而不是只搜两条通用 query。
4. **URL 去重与来源打分**：多搜之后必须合并证据池，按 URL 去重，按官方/媒体/社区来源分级。
5. **缺口补采**：初次清洗后发现创始人、融资、定价、竞品、时间线等字段缺失，要自动二次补采。

当前代码中，`webapp/pipeline.py:54-61` 的 Tavily 只生成 2 条查询，`webapp/pipeline.py:137-149` 的 GitHub 只搜一次，`webapp/pipeline.py:152-169` 的 YouTube 只搜一次且只支持单 key，`webapp/db.py:272-299` 写库只按 `company_name` 插入，不做归一化去重。这是问题根源。

---

## 1. 当前链路问题定位

### 1.1 采集层问题

当前 `_collect_all()` 是 4 路并行：Tavily、GitHub、YouTube、官网抓取，位置在 `webapp/pipeline.py:245-281`。

问题是 4 路里有 3 路都直接使用用户输入的 `company_name`：

- Tavily：`f"{company_name} AI startup overview funding founders"`
- GitHub：`f"{company_name} in:name"`
- YouTube：`f"{company_name} founder interview"`

这会导致：

- `Limitless` 与 `limitless` 可能命中不同搜索排序。
- `limitless` 是普通英文词，泛词噪声大。
- `Limitless` 如果没有绑定 `limitless.ai`，容易搜到无关品牌。
- 只搜两条 Tavily query，不足以覆盖融资、创始人、竞品、定价、访谈、用户评论、GTM。

### 1.2 数据层问题

当前主表 `research` 只有 `company_name`，没有 `company_key`。`research_fields`、`final_fields`、`company_assets`、`image_variants`、`card_compositions` 也都以 `company_name` 作为公司身份。

这会导致：

```text
Limitless
limitless
LIMITLESS
limitless.ai
```

在系统里可能变成 4 个不同公司。

### 1.3 分析层问题

当前 Layer 0 只接受原始采集结果，没有明确的“证据池”结构。多来源信息没有统一排序、去重、来源权重和命中意图说明。

结果是：

- L0 可能优先读到噪声。
- 好来源可能被长内容截断。
- 官方来源、媒体来源、社区来源没有明确优先级。
- 某些字段缺失后，没有自动反向补采。

---

## 2. 目标架构

### 2.1 新链路

```text
用户输入
  ↓
公司身份识别 company_identity
  ↓
搜索计划生成 search_plan
  ↓
多源并行采集 Tavily / GitHub / YouTube / Website
  ↓
证据池标准化 evidence_pool
  ↓
URL 去重 + 来源打分 + 实体匹配过滤
  ↓
Layer 0 初次清洗
  ↓
缺口识别 gap_detector
  ↓
定向补采 gap_collection
  ↓
Layer 0 最终清洗
  ↓
Layer 1 横纵分析
  ↓
Layer 2 商业结构分析
  ↓
Layer 3 字段提取
  ↓
写入 research / research_fields / assets
```

### 2.2 新核心对象

```python
@dataclass
class CompanyIdentity:
    input_name: str          # 用户输入，如 limitless
    display_name: str        # 展示名，如 Limitless
    company_key: str         # 数据库主身份，如 limitless.ai
    website_url: str         # https://www.limitless.ai
    website_host: str        # limitless.ai
    root_domain: str         # limitless
    aliases: list[str]       # 搜索别名
```

`company_key` 是系统内部主键；`display_name` 是界面显示名。不要再让展示名承担数据库身份职责。

---

## 3. 数据库改造方案

### 3.1 新增迁移文件

新增：

```text
db/migrations/003_company_identity.sql
```

内容：

```sql
-- research
ALTER TABLE research ADD COLUMN company_key TEXT;
ALTER TABLE research ADD COLUMN display_name TEXT;
ALTER TABLE research ADD COLUMN input_name TEXT;
ALTER TABLE research ADD COLUMN website_host TEXT;
ALTER TABLE research ADD COLUMN source_chain_version TEXT DEFAULT 'collection_v2';

CREATE INDEX IF NOT EXISTS idx_research_company_key
  ON research(company_key, version, created_at);

-- research_jobs
ALTER TABLE research_jobs ADD COLUMN company_key TEXT;
ALTER TABLE research_jobs ADD COLUMN display_name TEXT;
ALTER TABLE research_jobs ADD COLUMN website_host TEXT;

CREATE INDEX IF NOT EXISTS idx_research_jobs_company_key
  ON research_jobs(company_key, created_at);
```

`ALTER TABLE ADD COLUMN` 在 SQLite 中如果重复执行会报错，所以实际落地要通过现有 `db/migrate.py` 幂等执行，不要在启动路径手工重复执行。

### 3.2 字段库改造

`research_fields` 和 `final_fields` 都要新增 `company_key`：

```sql
ALTER TABLE research_fields ADD COLUMN company_key TEXT;
CREATE INDEX IF NOT EXISTS idx_research_fields_company_key
  ON research_fields(company_key, version);

ALTER TABLE final_fields ADD COLUMN company_key TEXT;
CREATE INDEX IF NOT EXISTS idx_final_fields_company_key
  ON final_fields(company_key);
```

后续唯一约束建议从：

```text
UNIQUE(company_name, version, field_key)
```

升级为逻辑唯一：

```text
UNIQUE(company_key, version, field_key)
```

SQLite 不方便直接改约束，建议新建表迁移，或先保留旧约束，代码层优先按 `company_key` 查询和写入。

### 3.3 图片资产库改造

`company_assets` 和 `image_variants` 都要新增 `company_key`：

```sql
ALTER TABLE company_assets ADD COLUMN company_key TEXT;
ALTER TABLE image_variants ADD COLUMN company_key TEXT;

CREATE INDEX IF NOT EXISTS idx_assets_company_key
  ON company_assets(company_key);

CREATE INDEX IF NOT EXISTS idx_variants_company_key_asset
  ON image_variants(company_key, asset_key);
```

后续资产唯一逻辑应从：

```text
UNIQUE(company_name, asset_key)
```

迁移为：

```text
UNIQUE(company_key, asset_key)
```

### 3.4 卡片编排库改造

`composition_db.sqlite` 中：

```sql
ALTER TABLE card_compositions ADD COLUMN company_key TEXT;
ALTER TABLE card_items ADD COLUMN company_key TEXT;

CREATE INDEX IF NOT EXISTS idx_card_compositions_company_key
  ON card_compositions(company_key);

CREATE INDEX IF NOT EXISTS idx_card_items_company_key_card
  ON card_items(company_key, card_id);
```

### 3.5 历史数据合并脚本

新增：

```text
db/merge_company_identity.py
```

功能：

```bash
python3 db/merge_company_identity.py --dry-run
python3 db/merge_company_identity.py --apply
```

合并规则：

1. 优先从 `website_url` 解析 host，去掉 `www.`，作为 `company_key`。
2. 没有官网时，用 `lower(trim(company_name))`。
3. 同一个 `company_key` 下多个展示名时，选择最新记录的 `display_name`。
4. `research` 不删除历史行，只统一 `company_key`。
5. `research_fields` 冲突时保留 `updated_at` 最新的字段。
6. `final_fields` 冲突时优先保留 `status='confirmed'`，再按 `updated_at` 最新。
7. `company_assets` 冲突时优先保留 `status='ready'`，再按 `final_score` 高的。
8. `image_variants` 不删除，只补齐 `company_key`。

---

## 4. 公司身份模块

新增：

```text
webapp/company_identity.py
```

代码骨架：

```python
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse
import re


@dataclass(frozen=True)
class CompanyIdentity:
    input_name: str
    display_name: str
    company_key: str
    website_url: str
    website_host: str
    root_domain: str
    aliases: list[str]


def _normalize_host(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.netloc or parsed.path).lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host.strip("/")


def _root_domain(host: str) -> str:
    if not host:
        return ""
    return host.split(".")[0]


def _display_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    if name.islower():
        return name[:1].upper() + name[1:]
    return name


def build_company_identity(company_name: str, company_url: str = "") -> CompanyIdentity:
    input_name = (company_name or "").strip()
    host = _normalize_host(company_url)
    root = _root_domain(host)
    display = _display_name(input_name or root)
    key = host or input_name.lower()

    aliases = build_company_aliases(input_name=input_name, display_name=display, host=host, root=root)

    return CompanyIdentity(
        input_name=input_name,
        display_name=display,
        company_key=key,
        website_url=company_url.strip(),
        website_host=host,
        root_domain=root,
        aliases=aliases,
    )


def build_company_aliases(input_name: str, display_name: str, host: str, root: str) -> list[str]:
    terms = set()
    for item in [input_name, display_name, input_name.lower(), display_name.lower(), root, host]:
        item = (item or "").strip()
        if item:
            terms.add(item)

    if display_name and host:
        terms.add(f'"{display_name}" "{host}"')
    if root and host:
        terms.add(f'"{root}" "{host}"')
    if display_name:
        terms.add(f"{display_name} AI")
        terms.add(f"{display_name} startup")
    if root:
        terms.add(f"{root} AI")
        terms.add(f"{root} startup")

    return [t for t in terms if len(t) >= 2]
```

---

## 5. 搜索计划模块

新增：

```text
webapp/search_plan.py
```

### 5.1 搜索意图枚举

```python
SEARCH_INTENTS = {
    "overview": "公司概览、定位、官网、产品定义",
    "founders": "创始人、教育背景、工作经历、过往成就",
    "funding": "融资轮次、金额、投资方、估值",
    "product": "产品功能、截图、宣传页、文档",
    "pricing": "价格、订阅、套餐、付费触发点",
    "competitors": "竞品、替代品、对标产品",
    "gtm": "冷启动、增长、渠道、客户案例",
    "timeline": "发展沿袭、发布时间、转型节点",
    "community": "Product Hunt、Hacker News、Reddit、X 讨论",
    "interview": "创始人访谈、播客、YouTube 视频",
}
```

### 5.2 Tavily query 模板

```python
TAVILY_QUERY_TEMPLATES = {
    "overview": [
        "{term} AI startup overview product company",
        "{term} official website about product",
    ],
    "founders": [
        "{term} founder education background LinkedIn",
        "{term} founder interview biography",
    ],
    "funding": [
        "{term} funding seed series investors valuation",
        "{term} raised funding TechCrunch Crunchbase PitchBook",
    ],
    "product": [
        "{term} product features screenshot demo docs",
        "{term} use cases customers product tour",
    ],
    "pricing": [
        "{term} pricing plans subscription",
        "site:{host} pricing plans",
    ],
    "competitors": [
        "{term} competitors alternatives vs",
        "{term} market map competitors",
    ],
    "gtm": [
        "{term} go to market growth strategy customers",
        "{term} Product Hunt launch users growth",
    ],
    "timeline": [
        "{term} launch history timeline founded",
        "{term} announcement rebrand acquisition",
    ],
    "community": [
        "{term} Product Hunt Hacker News Reddit Twitter review",
    ],
}
```

### 5.3 预算控制

新增配置：

```python
RESEARCH_DEPTH = os.environ.get("RESEARCH_DEPTH", "deep")
TAVILY_QUERY_BUDGET_STANDARD = int(os.environ.get("TAVILY_QUERY_BUDGET_STANDARD", "8"))
TAVILY_QUERY_BUDGET_DEEP = int(os.environ.get("TAVILY_QUERY_BUDGET_DEEP", "18"))
TAVILY_RESULTS_PER_QUERY = int(os.environ.get("TAVILY_RESULTS_PER_QUERY", "8"))
COLLECTION_MIN_UNIQUE_URLS = int(os.environ.get("COLLECTION_MIN_UNIQUE_URLS", "18"))
```

`deep` 模式用于你现在的目标：尽可能全面收集信息。

---

## 6. 证据池标准化、去重、打分

新增：

```text
webapp/evidence_pool.py
```

### 6.1 标准证据结构

```python
@dataclass
class EvidenceItem:
    source: str              # tavily | github | youtube | website
    intent: str              # founders | funding | product 等
    title: str
    url: str
    normalized_url: str
    content: str
    raw_content: str
    source_score: float
    entity_score: float
    final_score: float
    query: str
    collected_at: str
```

### 6.2 URL 规范化

```python
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

DROP_QUERY_PREFIXES = ("utm_",)
DROP_QUERY_KEYS = {"fbclid", "gclid", "ref", "ref_src"}


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/")

    kept = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=False):
        lk = k.lower()
        if lk in DROP_QUERY_KEYS or any(lk.startswith(p) for p in DROP_QUERY_PREFIXES):
            continue
        kept.append((k, v))

    return urlunparse((scheme, netloc, path, "", urlencode(kept), ""))
```

### 6.3 来源打分

来源权重：

| 来源 | 分数 |
|---|---:|
| 官网 / 官方博客 / 官方文档 | 1.00 |
| YC / Product Hunt / GitHub 官方组织 | 0.85 |
| TechCrunch / The Verge / VentureBeat / Forbes 等媒体 | 0.75 |
| Crunchbase / PitchBook 摘要页 | 0.70 |
| YouTube 创始人访谈 | 0.65 |
| Hacker News / Reddit / X | 0.40 |
| SEO 聚合站 / 无来源转载 | 0.20 |

实体匹配分：

```python
def entity_score(item, identity):
    text = f"{item.title} {item.url} {item.content}".lower()
    score = 0.0
    if identity.website_host and identity.website_host in text:
        score += 0.55
    if identity.display_name.lower() in text:
        score += 0.25
    if identity.root_domain and identity.root_domain in text:
        score += 0.10
    if any(anchor in text for anchor in ["ai", "startup", "founder", "funding", "pricing", "product"]):
        score += 0.10
    return min(score, 1.0)
```

最终分：

```python
final_score = source_score * 0.6 + entity_score * 0.4
```

过滤规则：

```text
final_score < 0.35：丢弃
0.35 <= final_score < 0.55：保留但低优先级
final_score >= 0.55：进入 LLM 证据池
```

### 6.4 去重规则

同一个 `normalized_url` 只保留一条，保留 `final_score` 最高的那条，同时合并 `query` 和 `intent`：

```python
def dedupe_evidence(items: list[EvidenceItem]) -> list[EvidenceItem]:
    by_url = {}
    for item in items:
        key = item.normalized_url
        if not key:
            continue
        old = by_url.get(key)
        if old is None or item.final_score > old.final_score:
            by_url[key] = item
        else:
            old.intent = ",".join(sorted(set(old.intent.split(",") + item.intent.split(","))))
    return sorted(by_url.values(), key=lambda x: x.final_score, reverse=True)
```

---

## 7. 采集函数改造

### 7.1 修改 `_collect_all()`

原函数签名：

```python
def _collect_all(company_name: str, company_url: str, progress_callback=None, job_id: str = None) -> dict:
```

改为内部构造身份对象：

```python
def _collect_all(company_name: str, company_url: str, progress_callback=None, job_id: str = None) -> dict:
    identity = build_company_identity(company_name, company_url)
    plan = build_search_plan(identity, depth=config.RESEARCH_DEPTH)

    tasks = {
        "tavily": lambda: _search_tavily_plan(identity, plan),
        "github": lambda: _search_github_plan(identity, plan),
        "youtube": lambda: _search_youtube_plan(identity, plan),
        "website": lambda: _scrape_website(identity.website_url),
    }

    raw = {
        "company_name": identity.display_name,
        "company_key": identity.company_key,
        "display_name": identity.display_name,
        "input_name": identity.input_name,
        "company_url": identity.website_url,
        "website_host": identity.website_host,
        "aliases": identity.aliases,
        "search_plan": plan.to_dict(),
    }
```

### 7.2 Tavily 多 query

新增函数：

```python
def _search_tavily_plan(identity: CompanyIdentity, plan: SearchPlan):
    batches = []
    for q in plan.tavily_queries:
        result = _search_tavily_query(q.query, include_images=False)
        result["_query"] = q.query
        result["_intent"] = q.intent
        batches.append(result)
    return batches
```

`_search_tavily_query()` 保留多 key 重试逻辑，但 `max_results` 改为配置项：

```python
"max_results": config.TAVILY_RESULTS_PER_QUERY
```

### 7.3 GitHub 多 query

原逻辑只搜：

```text
{company_name} in:name
```

改为：

```python
def _search_github_plan(identity: CompanyIdentity, plan: SearchPlan):
    queries = [
        f'{identity.root_domain} in:name,description,readme',
        f'{identity.display_name} in:name,description,readme',
        f'{identity.website_host} in:readme',
    ]
    queries = [q for q in dict.fromkeys(queries) if q.strip()]

    merged = []
    errors = []
    for q in queries[:4]:
        resp = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": q, "sort": "stars", "per_page": 5},
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=(15, 45),
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", []):
                item["_query"] = q
                merged.append(item)
        else:
            errors.append({"query": q, "error": resp.status_code})

    return {"items": dedupe_github_repos(merged), "errors": errors}
```

### 7.4 YouTube 多 query

原逻辑只搜：

```text
{company_name} founder interview
```

改为：

```python
def _search_youtube_plan(identity: CompanyIdentity, plan: SearchPlan):
    if not config.YOUTUBE_API_KEY:
        return {"items": [], "note": "no API key"}

    queries = [
        f"{identity.display_name} founder interview",
        f"{identity.root_domain} founder interview",
        f"{identity.website_host} founder interview",
        f"{identity.display_name} product demo",
    ]

    merged = []
    errors = []
    for q in dict.fromkeys([x for x in queries if x.strip()]):
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": q,
                "type": "video",
                "maxResults": 5,
                "key": config.YOUTUBE_API_KEY,
            },
            timeout=(15, 45),
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", []):
                item["_query"] = q
                merged.append(item)
        else:
            errors.append({"query": q, "error": resp.status_code})

    return {"items": dedupe_youtube_items(merged), "errors": errors}
```

---

## 8. 缺口补采机制

### 8.1 缺口字段

Layer 0 初次输出后，检查这些字段：

```python
CRITICAL_GAPS = {
    "founders": ["founder_name", "founder_edu", "founder_bg", "founder_achievement"],
    "funding": ["funding_info"],
    "pricing": ["pricing_model", "revenue_model"],
    "competitors": ["competitors"],
    "timeline": ["timeline_events"],
    "product": ["main_product_name", "main_product_def", "main_product_achievement"],
}
```

判断缺失：

```python
def is_missing(value):
    if value is None:
        return True
    text = str(value).strip()
    return text in ("", "暂缺", "未知", "无可信信息")
```

### 8.2 二次补采 query

如果 `funding_info` 缺失：

```text
"{display_name}" "{website_host}" funding investors raised
"{display_name}" seed round series valuation
```

如果创始人字段缺失：

```text
"{display_name}" founder LinkedIn education background
"{display_name}" founder interview biography
```

如果竞品缺失：

```text
"{display_name}" competitors alternatives vs
"{root_domain}" market map competitors
```

如果定价缺失：

```text
site:{website_host} pricing
"{display_name}" pricing plans subscription
```

### 8.3 LLM 调用顺序

将 `llm_analysis()` 调整为：

```python
# 1. 初次 L0
l0_draft = run_layer0(raw_data)

# 2. 解析 L0 JSON
l0_json = safe_extract_json(l0_draft)

# 3. 检查缺口
missing_intents = detect_gaps(l0_json)

# 4. 如有缺口，补采
if missing_intents:
    supplement_raw = collect_gap_sources(identity, missing_intents)
    merged_raw = merge_raw_sources(raw_data, supplement_raw)
    l0_result = run_layer0(merged_raw)
else:
    l0_result = l0_draft

# 5. 后续 L1/L2/L3 不变
```

这是最稳的方案，因为补采发生在 L1/L2/L3 之前，不会污染后续分析。

---

## 9. L0 Prompt 修改

当前 `prompts/layer0-cleaner.md` 说输入来自 4 个数据源，但没有要求使用证据池优先级。需要改成：

```markdown
## 输入结构

输入包含：
- company_identity：公司标准身份，包括 display_name、company_key、website_host、aliases
- evidence_pool：已去重、已打分的证据列表
- raw_sources：Tavily/GitHub/YouTube/官网原始结果
- source_audit：每路采集数量、失败原因、低召回警告

## 使用规则

1. 优先使用 evidence_pool 中 final_score 高的来源。
2. 官网、官方博客、官方文档、官方 GitHub 优先于媒体。
3. 媒体优先于社区讨论。
4. 对 generic name 公司，例如 limitless、linear、cursor，必须优先验证 URL 是否匹配 website_host。
5. 每个关键字段尽量给出 source_url。
6. 不要因为社区传言补全创始人、融资、收入等硬事实。
7. 如果同一字段多个来源冲突，输出最可信来源，并在 confidence 中降级。
```

---

## 10. 写库改造

### 10.1 `run_pipeline()`

当前 `run_pipeline()` 在写字段级表时使用：

```python
field_record = {**record, "company_name": company_name}
```

应改为：

```python
identity = build_company_identity(company_name, company_url)

field_record = {
    **record,
    "company_name": identity.display_name,
    "display_name": identity.display_name,
    "company_key": identity.company_key,
    "website_host": identity.website_host,
}
```

图片采集也要传 `company_key`：

```python
company_data = {
    "company_name": identity.display_name,
    "company_key": identity.company_key,
    "company_url": identity.website_url,
    "website_url": identity.website_url,
    ...
}
```

### 10.2 `save_research_records()`

当前 `save_research_records()` 只是插入新行。可以继续保留历史版本，但要写入身份字段：

```python
values = [
    rec.get("company_key"),
    rec.get("company_name"),
    rec.get("display_name"),
    rec.get("input_name"),
    rec.get("website_host"),
    rec.get("version", "standard"),
]
```

建议短期保留 append-only，因为你需要对比多次研究质量。公司列表只展示每个 `company_key` 的最新 standard 版本。

### 10.3 `get_companies()`

当前按 `company_name` 聚合：

```sql
SELECT DISTINCT company_name, MAX(created_at) as created_at
FROM research GROUP BY company_name
```

改为按 `company_key` 聚合：

```sql
SELECT
  COALESCE(company_key, lower(company_name)) AS company_key,
  MAX(created_at) AS created_at
FROM research
GROUP BY COALESCE(company_key, lower(company_name))
ORDER BY created_at DESC
```

查询 latest 时：

```sql
SELECT * FROM research
WHERE COALESCE(company_key, lower(company_name))=?
ORDER BY created_at DESC,
  CASE version WHEN 'standard' THEN 0 ELSE 1 END
LIMIT 1
```

返回给前端：

```json
{
  "company_key": "limitless.ai",
  "company_name": "Limitless",
  "display_name": "Limitless",
  "company_url": "https://www.limitless.ai"
}
```

---

## 11. 前端和 API 兼容

### 11.1 启动研究接口

`/api/research/start` 保持兼容：

```json
{
  "company_name": "limitless",
  "company_url": "https://www.limitless.ai"
}
```

返回增加：

```json
{
  "job_id": "xxxx",
  "status": "running",
  "company_key": "limitless.ai",
  "display_name": "Limitless"
}
```

### 11.2 读取研究接口

现有：

```text
/api/research/<company>/<version>
```

兼容保留，但内部先按 `company_key` 查，再按 `company_name` 回退。

新增推荐接口：

```text
/api/research/by-key/<company_key>/<version>
```

例如：

```text
/api/research/by-key/limitless.ai/standard
```

### 11.3 图片与定稿接口

所有现有传 `company_name` 的地方短期兼容。内部统一解析：

```python
def resolve_company_ref(company_ref: str) -> CompanyIdentityRef:
    # 如果包含点号或能在 company_key 中查到，按 key
    # 否则按 display/company_name 查最新 key
```

---

## 12. 采集审计与可视化

### 12.1 source_audit 结构

```json
{
  "company_key": "limitless.ai",
  "display_name": "Limitless",
  "search_terms": ["Limitless", "limitless", "limitless.ai"],
  "query_count": 18,
  "unique_url_count": 34,
  "sources": {
    "tavily": {"status": "ok", "query_count": 18, "raw_count": 103, "unique_count": 31},
    "github": {"status": "ok", "query_count": 3, "raw_count": 4, "unique_count": 2},
    "youtube": {"status": "skipped", "reason": "no API key"},
    "website": {"status": "ok", "chars": 5321}
  },
  "warnings": [
    "youtube_api_key_missing",
    "pricing_page_not_found"
  ]
}
```

### 12.2 研究台展示

研究台当前已经展示来源状态。需要增加：

- query 数量
- raw 结果数
- unique URL 数
- 被丢弃噪声数
- 缺口补采次数
- 最高分来源 Top 5

这样你能看到“到底是哪一路采少了”。

---

## 13. 测试计划

### 13.1 单元测试

新增：

```text
tests/test_company_identity.py
tests/test_search_plan.py
tests/test_evidence_pool.py
tests/test_pipeline_case_insensitive.py
```

### 13.2 必测用例

#### 用例 1：大小写同公司

```python
def test_limitless_case_variants_share_company_key():
    a = build_company_identity("Limitless", "https://www.limitless.ai")
    b = build_company_identity("limitless", "https://limitless.ai")
    assert a.company_key == b.company_key == "limitless.ai"
```

#### 用例 2：搜索词覆盖

```python
def test_search_terms_include_case_and_domain_variants():
    identity = build_company_identity("Limitless", "https://www.limitless.ai")
    terms = identity.aliases
    assert "Limitless" in terms
    assert "limitless" in terms
    assert "limitless.ai" in terms
    assert '"Limitless" "limitless.ai"' in terms
```

#### 用例 3：Tavily query 不少于核心意图

```python
def test_deep_search_plan_has_core_intents():
    identity = build_company_identity("Limitless", "https://www.limitless.ai")
    plan = build_search_plan(identity, depth="deep")
    intents = {q.intent for q in plan.tavily_queries}
    assert {"overview", "founders", "funding", "product", "pricing", "competitors"}.issubset(intents)
```

#### 用例 4：URL 去重

```python
def test_dedupe_url_removes_utm_and_trailing_slash():
    assert normalize_url("https://www.limitless.ai/?utm_source=x") == "https://limitless.ai"
```

#### 用例 5：写库不生成两家公司

```python
def test_run_pipeline_case_variants_one_company_key():
    run_pipeline("Limitless", "https://www.limitless.ai")
    run_pipeline("limitless", "https://limitless.ai")
    companies = database.get_companies(DB_PATH_RESEARCH)
    rows = [c for c in companies if c["company_key"] == "limitless.ai"]
    assert len(rows) == 1
```

---

## 14. 分阶段实施计划

### P0：当天必须修

目标：先解决 `Limitless` / `limitless` 不一致。

改动：

1. 新增 `company_identity.py`。
2. `_search_tavily()` 改为大小写 + 域名多 query。
3. `_search_github()` 和 `_search_youtube()` 改为多 query。
4. Tavily 结果按 URL 去重。
5. `raw` 中加入 `company_key`、`display_name`、`website_host`。
6. `run_pipeline()` 写字段表和图片采集时使用统一 display/key。

验收：

```text
输入 Limitless 与 limitless，采集 query 不同但 company_key 一致。
研究台只展示一个公司。
Tavily unique URL 数明显增加。
```

### P1：1-2 天修

目标：完整解决重复公司和历史数据。

改动：

1. 新增 `003_company_identity.sql`。
2. 所有主表增加 `company_key`。
3. `get_companies()` 改为按 `company_key` 聚合。
4. `get_research()` 支持按 key 查询。
5. 新增 `merge_company_identity.py`，合并历史大小写重复数据。

验收：

```text
历史 limitless / Limitless 合并为 limitless.ai。
final_fields / assets / composition 不丢。
```

### P2：2-4 天修

目标：尽可能全面收集信息。

改动：

1. 新增 `search_plan.py`。
2. 新增 `evidence_pool.py`。
3. Layer 0 输入改为 evidence_pool。
4. 增加 source_score、entity_score、final_score。
5. 研究台展示采集审计。
6. 加缺口补采。

验收：

```text
founder/funding/pricing/competitors/timeline 不再大面积暂缺。
每个字段可追溯 source_url。
研究台能看出是哪一路采集不足。
```

### P3：后续增强

目标：更像研究系统，而不是一次性搜索脚本。

改动：

1. 给每个字段保存 evidence 引用。
2. 支持手动追加来源 URL 后重新清洗。
3. 支持按公司别名管理，如旧品牌名、产品名、域名变更。
4. 支持 LinkedIn、Product Hunt、YC、Crunchbase 等专门 connector 或解析器。
5. 支持缓存同一个 URL 的抓取内容，避免重复调用。

---

## 15. 最小代码修改清单

必须改：

```text
webapp/pipeline.py
webapp/db.py
webapp/repositories/field_repo.py
webapp/asset_store.py
webapp/app.py
prompts/layer0-cleaner.md
```

必须新增：

```text
webapp/company_identity.py
webapp/search_plan.py
webapp/evidence_pool.py
webapp/gap_detector.py
db/migrations/003_company_identity.sql
db/merge_company_identity.py
tests/test_company_identity.py
tests/test_search_plan.py
tests/test_evidence_pool.py
tests/test_pipeline_case_insensitive.py
```

建议新增配置：

```text
RESEARCH_DEPTH=deep
TAVILY_QUERY_BUDGET_STANDARD=8
TAVILY_QUERY_BUDGET_DEEP=18
TAVILY_RESULTS_PER_QUERY=8
COLLECTION_MIN_UNIQUE_URLS=18
COLLECTION_ENABLE_GAP_REFETCH=1
```

---

## 16. 验收标准

### 16.1 功能验收

- `Limitless`、`limitless`、`LIMITLESS`、`limitless.ai` 都归到同一个 `company_key=limitless.ai`。
- 研究台公司库只显示一条 `Limitless`。
- Tavily 至少覆盖 6 类意图：overview、founders、funding、product、pricing、competitors。
- 多次运行不会产生重复字段池。
- 图片资产不会因为大小写不同生成两套目录或两套资产记录。

### 16.2 数据质量验收

- `source_audit.unique_url_count >= 18`，否则标记 `low_recall`。
- 官网抓取正文字符数小于 500 时标记 `website_low_content`。
- YouTube 未配置 key 时明确标记 `youtube_api_key_missing`，不要静默为空。
- 关键字段若仍为暂缺，必须能看到补采 query 和失败原因。

### 16.3 回归验收

运行：

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile webapp/*.py
python3 db/migrate.py --help
```

额外人工验收：

```bash
# 第一次
company_name=Limitless
company_url=https://www.limitless.ai

# 第二次
company_name=limitless
company_url=https://limitless.ai
```

预期：

```text
companies API 返回 1 条公司
research 表可以有多次历史 run
research_fields 按 company_key 查询只有一组最新字段
assets 只绑定 limitless.ai
```

---

## 17. 不建议做的事

1. **不要只把 company_name 全部 lower 后展示。** 展示名会变丑，且品牌大小写可能有意义。
2. **不要只加大小写两条搜索。** 会提高召回，但不能解决身份重复。
3. **不要把所有搜索结果直接塞给 LLM。** 噪声会增加，成本也会上升。
4. **不要按 company_name 建新图片目录。** 应按 `company_key` 或安全化后的 key 建目录。
5. **不要删除历史 research 行。** 研究结果需要可追溯，可以按 company_key 聚合展示。

---

## 18. 最终形态

修完后的系统应该是：

```text
用户输入：limitless + https://www.limitless.ai
系统身份：company_key = limitless.ai
展示名称：Limitless
搜索别名：Limitless / limitless / limitless.ai / "Limitless" "limitless.ai"
采集策略：多意图 query + 多源并行 + 缺口补采
证据处理：去重、打分、过滤、审计
分析链路：L0-L3 使用高质量证据池
数据落库：按 company_key 归一，按 display_name 展示
```

这才是完整修复。
