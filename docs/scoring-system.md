# 评分体系

本文档完整描述 AI 创业公司竞争评分系统的设计逻辑、计算方法和数据流。评分体系的目的是：将「壁垒」「巨头关注度」「价值捕获」三个抽象概念量化为 0–10 的可比分数，用于生成两张竞争散点图（竞争格局矩阵 + AI 栈生态位图）。

## 设计哲学

核心问题：如何把主观的商业判断转化为客观的量化评分？

回答：**把评分问题转化为分类问题。** LLM 不直接打分数，只做枚举分类（从互斥选项中选最接近的一个）。分类任务比连续值评分稳定得多——这是 LLM prompt engineering 的基本经验，也得到学术研究支持（Arize AI 的研究发现 GPT-4 在数值评分上表现出极端的全有或全无行为，Claude 稍好但不稳定）。

整个体系遵循三条原则：

1. **LLM 不做数字判断，只做分类** — 不向 LLM 提问「壁垒打几分」，只问「它用什么模型？proprietary / fine-tuned / multi-model / openai-only / no-ai-core」。分类有明确边界，枚举值互斥且覆盖全集。
2. **规则层做锚点** — 确定性高的路径（关键词匹配、pricing 页爬取）走规则不走 LLM，成本为零、方差为零、完全可复现。
3. **提取与评分解耦** — LLM 全程不知道评分公式和权重。它只看到「判断它是哪一类」，看不到「这类值几分」。这是评分者盲法——防止 LLM 为「高分」而扭曲分类。

## 评分维度

### 3 个最终得分

| 得分 | 含义 | 竞争格局图 X/Y | AI 栈生态位图 X/Y |
|---|---|---|---|
| `score_defensibility` | 护城河强度 | Y 轴（0-10） | — |
| `score_incumbent_attention` | 巨头关注度 | X 轴（0-10） | — |
| `score_value_capture` | 价值捕获能力 | — | X 轴（0-10） |
| `stack_layer` | AI 栈层级 | — | Y 轴（5 条泳道） |

### 辅助得分

| 得分 | 含义 | 用途 |
|---|---|---|
| `funding_stage_score` | 融资阶段映射值（pre_seed=1 → series_c_plus=9） | 参考值，不再决定气泡大小 |

## 10 个枚举字段

### 枚举→数值映射表

**AI 模型依赖** `ai_model_dependency`（护城河子项，映射为 technical_uniqueness）

| 枚举值 | 分数 | 说明 |
|---|---|---|
| `proprietary_model` | 10 | 自研模型，完全掌控 |
| `fine_tuned` | 7 | 在开源模型上精调 |
| `multi_model` | 5 | 使用多种模型 |
| `openai_only` | 2 | 仅调用 OpenAI API |
| `no_ai_core` | 0 | AI 不是核心竞争力 |

**工作流集成层级** `workflow_integration_level`（护城河子项，映射为 workflow_lock_in）

| 枚举值 | 分数 | 说明 |
|---|---|---|
| `system_of_record` | 10 | 客户核心系统，迁移成本极高 |
| `workflow_embedded` | 7 | 嵌入日常工作流，有切换成本 |
| `plugin_addon` | 4 | 插件/附加功能 |
| `standalone_tool` | 1 | 独立工具，切换成本低 |

**数据飞轮** `data_flywheel`（护城河子项，合并入 data_lock_in）

| 枚举值 | 分数 |
|---|---|
| `yes` | 10 |
| `partial` | 5 |
| `no` | 0 |

**专有数据资产** `proprietary_data_asset`（护城河子项，合并入 data_lock_in）

| 枚举值 | 分数 |
|---|---|
| `yes_core` | 10 |
| `yes_supplementary` | 5 |
| `no` | 0 |

**巨头直接竞争** `incumbent_direct_competitor`（巨头关注子项，映射为 incumbent_overlap）

| 枚举值 | 分数 | 说明 |
|---|---|---|
| `openai` | 10 | OpenAI 是主要竞争对手 |
| `google` | 10 | Google/DeepMind 是主要竞争对手 |
| `multiple` | 9 | 与多个巨头直接竞争 |
| `microsoft` | 8 | Microsoft/GitHub 是主要竞争对手 |
| `other` | 5 | 竞争对手是其他大公司 |
| `none` | 1 | 不与巨头直接竞争 |

**客户细分类型** `customer_segment_type`（多用途：user_visibility / customer_budget_level）

| 枚举值 | 分数 |
|---|---|
| `b2b_enterprise` | 9 |
| `developer_api` | 7 |
| `b2b2c` | 6 |
| `b2b_smb` | 5 |
| `b2c` | 3 |

**融资阶段** `funding_stage`

| 枚举值 | 分数 |
|---|---|
| `series_c_plus` | 9 |
| `series_b` | 7 |
| `series_a` | 5 |
| `seed` | 3 |
| `pre_seed` | 1 |

融资阶段走两段式推断：先匹配中文关键词（种子轮→seed, B轮→series_b, C轮→series_c_plus），再英文正则兜底，默认 pre_seed。

**定价模式** `pricing_model`（价值捕获子项，映射为 pricing_power）

| 枚举值 | 分数 |
|---|---|
| `outcome_based` | 10 |
| `enterprise_contract` | 8 |
| `subscription` | 6 |
| `usage_based` | 4 |
| `freemium` | 2 |
| `free` | 0 |

**推理成本敞口** `inference_cost_exposure`（价值捕获子项，映射为 gross_margin）

| 枚举值 | 分数 | 说明 |
|---|---|---|
| `none` | 10 | 无推理成本（非模型层公司） |
| `low` | 7 | 推理成本低（小模型或高效推理） |
| `medium` | 4 | 中等推理成本 |
| `high` | 1 | 高推理成本（依赖大模型推理） |

**技术栈层级** `stack_layer` — 在 AI 栈生态位图中作为 Y 轴泳道，在竞争格局图中不参与绘图

| 枚举值 | 泳道 | 说明 |
|---|---|---|
| `distribution` | 分发渠道 | 分发/入口/插件市场/聚合平台 |
| `vertical_app` | 垂直应用 | 面向终端用户的应用/工作流 |
| `middleware` | 中间件层 | 连接模型与业务场景 |
| `foundation_model` | 模型层 | 提供核心智能能力 |
| `infrastructure` | 基础设施层 | 算力、数据与底层平台 |

## 评分公式（v2 改造版）

### 护城河强度 (Defensibility) — 竞争格局图 Y 轴

```
score_defensibility =
  0.30 × data_lock_in
+ 0.25 × workflow_lock_in
+ 0.20 × technical_uniqueness
+ 0.15 × distribution_lock
+ 0.10 × brand_or_community
```

字段说明：

| 子项 | 权重 | 含义 | 新字段 |
|---|---|---|---|
| data_lock_in | 30% | 专有数据 + 数据飞轮 | data_lock_in（综合 proprietary_data_asset + data_flywheel） |
| workflow_lock_in | 25% | 是否嵌入客户核心流程 | workflow_lock_in（综合 workflow_integration_level） |
| technical_uniqueness | 20% | 技术是否难复制 | technical_uniqueness（综合 ai_model_dependency） |
| distribution_lock | 15% | 是否拥有渠道/入口/平台关系 | distribution_lock |
| brand_or_community | 10% | 是否形成品牌/社区/开发者心智 | brand_or_community |

### 巨头关注度 (Incumbent Attention) — 竞争格局图 X 轴

```
score_incumbent_attention =
  0.40 × incumbent_overlap
+ 0.25 × market_size
+ 0.20 × strategic_dependency
+ 0.15 × user_visibility
```

字段说明：

| 子项 | 权重 | 含义 | 新字段 |
|---|---|---|---|
| incumbent_overlap | 40% | 是否直接进入大厂核心产品范围 | incumbent_overlap（综合 incumbent_direct_competitor） |
| market_size | 25% | 市场规模是否足够大 | market_size |
| strategic_dependency | 20% | 是否依赖大厂模型/云/系统/分发渠道 | strategic_dependency |
| user_visibility | 15% | 用户是否显性、增长是否易被大厂观察 | user_visibility（综合 customer_segment_type） |

### 价值捕获能力 (Value Capture) — AI 栈生态位图 X 轴

```
score_value_capture =
  0.35 × pricing_power
+ 0.25 × gross_margin
+ 0.25 × workflow_lock_in
+ 0.15 × customer_budget_level
```

字段说明：

| 子项 | 权重 | 含义 | 新字段 |
|---|---|---|---|
| pricing_power | 35% | 是否有定价权 | pricing_power（综合 pricing_model） |
| gross_margin | 25% | 毛利空间是否高 | gross_margin（综合 inference_cost_exposure） |
| workflow_lock_in | 25% | 是否嵌入高频关键流程 | workflow_lock_in（综合 workflow_integration_level） |
| customer_budget_level | 15% | 客户是否有明确预算 | customer_budget_level（综合 customer_segment_type） |

### 向后兼容

当数据库中不存在 v2 新字段时，评分函数自动从旧字段映射：
- `data_lock_in` ← 0.6 × proprietary_data_asset + 0.4 × data_flywheel
- `workflow_lock_in` ← workflow_integration_level
- `technical_uniqueness` ← ai_model_dependency
- `incumbent_overlap` ← incumbent_direct_competitor
- `pricing_power` ← pricing_model
- `gross_margin` ← inference_cost_exposure（逆映射）
- 其他新字段使用默认中性值

## 枚举字段提取：三层解耦管道

### Layer 1 — 规则层 `field_rules.py`

不调用 LLM，零成本，零方差。

- **`infer_stack_layer()`** — 91 个关键词按优先级匹配 `company_type` 文本，映射到 5 层枚举
- **`scrape_pricing_signals()`** — 爬 `官网/pricing` 页面，22 个关键词 + 兜底逻辑 → `pricing_model` + `customer_segment_type`
- **入口**: `run_rule_layer(website, company_type)` → 返回命中字段 dict

### Layer 2 — LLM 三组调用 `pipeline.py`

| 组 | Prompt 文件 | 提取字段 | 调用方式 |
|---|---|---|---|
| A | `layer3-group-a-technical.md` | `ai_model_dependency`, `data_flywheel`, `proprietary_data_asset` | 与 B 并行 |
| B | `layer3-group-b-competitive.md` | `incumbent_direct_competitor`, `workflow_integration_level`, `inference_cost_exposure` | 与 A 并行 |
| C | `layer3-group-c-business.md` | `pricing_model`, `customer_segment_type`, `stack_layer` | 串行，注入规则层命中结果 |

组 C 接收规则层提示（如「stack_layer 已确定为 vertical_app，跳过」），避免 LLM 覆盖确定性结果。

### 多数投票

3 个关键字段（`ai_model_dependency`, `incumbent_direct_competitor`, `pricing_model`）额外调 2–3 轮，取众数。不一致时 temperature 调至 0.25 加第三轮。这本质上是 ensemble 抽样降低单次推理方差。

### Layer 3 — 验证层 `field_validator.py`

Pydantic `BaseModel`，10 个 `@field_validator`，白名单枚举校验。值不在白名单 → `ValueError` → 任务失败，不写假数据。

### 合并优先级

```
规则层命中 > LLM 三组合并结果
```

## 数据流

```
公司官网爬取 + company_type 文本
        │
        ▼
  field_rules.py (Layer 1)     ← 规则命中 stack_layer / customer_segment_type / pricing_model
        │
        ▼
  3 组 DeepSeek 调用 (Layer 2)  ← layer3-group-a/b/c，关键字段多数投票
        │
        ▼
  field_validator.py (Layer 3) ← Pydantic 白名单校验
        │
        ▼
  competitive_scoring.py       ← 枚举→数值映射 + 3 个加权公式（v2 新公式）
        │
        ▼
  research 表写入
        │
        ▼
  infographic.py               ← ECharts HTML → Playwright PNG (800×600 @2x)
```

## 图表输出（v2 改造版）

两张散点图由 `webapp/infographic.py` 生成 ECharts HTML。浏览器预览和 Playwright PNG 渲染都内联 `webapp/static/vendor/echarts.min.js`，不依赖外部 CDN。

**关键变更：不再使用组内归一化。所有坐标使用原始 0–10 绝对分。**

| 图 | asset_key | X 轴 | Y 轴 | 气泡 | 图表类型 | 默认尺寸 |
|---|---|---|---|---|---|---|
| 竞争格局矩阵 | `chart_competitive` | score_incumbent_attention 0-10 | score_defensibility 0-10 | 固定（目标 22px / 竞品 14px） | ECharts 四象限散点图 | 800×600 |
| AI 栈生态位图 | `chart_ecosystem` | score_value_capture 0-10 | stack_layer 5 泳道 | 固定（目标 22px / 竞品 12px） | ECharts category 轴散点图 | 800×600 |

### 竞争格局矩阵特性

- 四象限分割线在 x=5 / y=5（语义中点，不随数据漂移）
- 象限标签：战略机会区 / 硬仗区 / 高危区 / 边缘区
- 目标公司用 `#29B8D4` 青色高亮，竞品用 `rgba(27,42,74,0.35)` 半透明
- 所有公司显示名称标签（`labelLayout.hideOverlap` + `moveOverlap:shiftY` 避让）
- **标题动态给出结论**：`{公司名}：{象限区}｜{高/低护城河 × 高/低巨头压力}`
- 坐标轴 formatter：0→低, 5→中, 10→高

### AI 栈生态位图特性

- Y 轴：5 条泳道（分发渠道 → 垂直应用 → 中间件层 → 模型层 → 基础设施层）
- X 轴：0–10 绝对分，formatter：0→低, 5→中, 10→高
- x≥7 区域标记为「高价值捕获区」（浅绿色背景）
- 目标公司 2px 白色边框高亮，所有公司显示标签
- **无 markPoint pin**（已删除，目标公司通过气泡大小+描边+标签强调）
- **标题动态给出结论**：`{公司名}：{层级} / {高/中/低}价值捕获`

## 图表设计原则

1. **一图只表达一个判断** — 竞争格局图回答「在哪个象限」；生态位图回答「在产业链哪一层，价值捕获能力如何」
2. **标题先给答案** — 不再用「竞争格局定位图」等静态标题，改为动态结论句
3. **坐标稳定** — 0–10 绝对分，分界线固定，图表含义不随组内数据变化
4. **元素控制** — 目标公司 1 个强高亮，竞品 3–6 个，所有标签展示，网格线浅色少量
5. **800×600 原生生成** — 不作为大图缩小，标签字号在知识卡片中可读

## 相关文件

| 文件 | 职责 |
|---|---|
| `webapp/competitive_scoring.py` | 全部分数映射表和计算公式（v2 改造版） |
| `webapp/field_rules.py` | Layer 1 规则层，零 LLM 成本 |
| `webapp/field_validator.py` | Layer 3 Pydantic 白名单验证 |
| `webapp/competitive_batch.py` | 批处理 CLI 工具，支持 extract/score/distribution 命令 |
| `webapp/pipeline.py` | 研究流水线中调度三层管道（`_extract_enum_fields`） |
| `webapp/db.py` | 入库前自动 normalize + compute_scores |
| `webapp/infographic.py` | ECharts 图表 HTML 生成 + Playwright PNG 渲染（v2 改造版） |
| `prompts/layer3-group-a-technical.md` | LLM 组 A Prompt |
| `prompts/layer3-group-b-competitive.md` | LLM 组 B Prompt |
| `prompts/layer3-group-c-business.md` | LLM 组 C Prompt |

## 已知局限

1. **权重未经过经验校准** — 当前权重基于商业逻辑推理，未使用公开市场数据做 ground-truth 对齐
2. **壁垒框架覆盖不全** — 当前 5 个子项侧重技术和商业壁垒，未纳入 Helmer 7 Powers 的反定位（counter-positioning）、规模经济等维度
3. **新字段未接入 LLM 提取** — v2 新增的 `incumbent_overlap`、`distribution_lock`、`brand_or_community` 等字段尚未加入 L3 Prompt 提取，目前通过旧字段映射获得
4. **6 个非关键字段无多数投票** — 仅 3 个关键字段做 ensemble，其余 6 个字段单次调用直接入库
5. **评分分布未做敏感性分析** — 权重 ±20% 变动对各公司排名的影响未经测试
