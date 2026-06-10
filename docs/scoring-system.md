# 评分体系

本文档完整描述 AI 创业公司竞争评分系统的设计逻辑、计算方法和数据流。评分体系的目的是：将「壁垒」「巨头关注度」「价值截留」三个抽象概念量化为 0–10 的可比分数，用于生成两张竞争散点图（竞争格局矩阵 + 产业链生态位图）。

## 设计哲学

核心问题：如何把主观的商业判断转化为客观的量化评分？

回答：**把评分问题转化为分类问题。** LLM 不直接打分数，只做枚举分类（从互斥选项中选最接近的一个）。分类任务比连续值评分稳定得多——这是 LLM prompt engineering 的基本经验，也得到学术研究支持（Arize AI 的研究发现 GPT-4 在数值评分上表现出极端的全有或全无行为，Claude 稍好但不稳定）。

整个体系遵循三条原则：

1. **LLM 不做数字判断，只做分类** — 不向 LLM 提问「壁垒打几分」，只问「它用什么模型？proprietary / fine-tuned / multi-model / openai-only / no-ai-core」。分类有明确边界，枚举值互斥且覆盖全集。
2. **规则层做锚点** — 确定性高的路径（关键词匹配、pricing 页爬取）走规则不走 LLM，成本为零、方差为零、完全可复现。
3. **提取与评分解耦** — LLM 全程不知道评分公式和权重。它只看到「判断它是哪一类」，看不到「这类值几分」。这是评分者盲法——防止 LLM 为「高分」而扭曲分类。

## 评分维度

### 3 个最终得分

| 得分 | 含义 | Y 轴 |
|---|---|---|
| `score_defensibility` | 壁垒强度 — 公司能在多大程度上抵御竞争侵蚀 | 竞争格局矩阵 X 轴 |
| `score_incumbent_attention` | 巨头关注度 — OpenAI/Google/Microsoft 等巨头对该领域的重视程度 | 竞争格局矩阵 Y 轴 |
| `score_value_capture` | 价值截留能力 — 公司能在创造的价值中截留多少利润 | 生态位图 Y 轴 |

### 辅助得分

| 得分 | 含义 | 用途 |
|---|---|---|
| `funding_stage_score` | 融资阶段映射值（pre_seed=1 → series_c_plus=9） | 散点图气泡大小 |

## 10 个枚举字段

### 枚举→数值映射表

**AI 模型依赖** `ai_model_dependency`（壁垒子项，权重 35%）

| 枚举值 | 分数 | 说明 |
|---|---|---|
| `proprietary_model` | 10 | 自研模型，完全掌控 |
| `fine_tuned` | 7 | 在开源模型上精调 |
| `multi_model` | 5 | 使用多种模型 |
| `openai_only` | 2 | 仅调用 OpenAI API |
| `no_ai_core` | 0 | AI 不是核心竞争力 |

**工作流集成层级** `workflow_integration_level`（壁垒子项，权重 30%）

| 枚举值 | 分数 | 说明 |
|---|---|---|
| `system_of_record` | 10 | 客户核心系统，迁移成本极高 |
| `workflow_embedded` | 7 | 嵌入日常工作流，有切换成本 |
| `plugin_addon` | 4 | 插件/附加功能 |
| `standalone_tool` | 1 | 独立工具，切换成本低 |

**数据飞轮** `data_flywheel`（壁垒子项，权重 20%）

| 枚举值 | 分数 |
|---|---|
| `yes` | 10 |
| `partial` | 5 |
| `no` | 0 |

**专有数据资产** `proprietary_data_asset`（壁垒子项，权重 15%）

| 枚举值 | 分数 |
|---|---|
| `yes_core` | 10 |
| `yes_supplementary` | 5 |
| `no` | 0 |

**巨头直接竞争** `incumbent_direct_competitor`（巨头关注子项，权重 50%）

| 枚举值 | 分数 | 说明 |
|---|---|---|
| `openai` | 10 | OpenAI 是主要竞争对手 |
| `google` | 10 | Google/DeepMind 是主要竞争对手 |
| `multiple` | 9 | 与多个巨头直接竞争 |
| `microsoft` | 8 | Microsoft/GitHub 是主要竞争对手 |
| `other` | 5 | 竞争对手是其他大公司 |
| `none` | 1 | 不与巨头直接竞争 |

**客户细分类型** `customer_segment_type`（巨头关注子项 30% + 价值截留子项 20%）

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

**定价模式** `pricing_model`（价值截留子项，权重 35%）

| 枚举值 | 分数 |
|---|---|
| `outcome_based` | 10 |
| `enterprise_contract` | 8 |
| `subscription` | 6 |
| `usage_based` | 4 |
| `freemium` | 2 |
| `free` | 0 |

**推理成本敞口** `inference_cost_exposure`（价值截留子项，权重 30%）

| 枚举值 | 分数 | 说明 |
|---|---|---|
| `none` | 10 | 无推理成本（非模型层公司） |
| `low` | 7 | 推理成本低（小模型或高效推理） |
| `medium` | 4 | 中等推理成本 |
| `high` | 1 | 高推理成本（依赖大模型推理） |

**技术栈层级** `stack_layer` — 不参与评分计算，仅在生态位图中作为 X 轴离散坐标

| 枚举值 | X 轴位置 | 颜色 |
|---|---|---|
| `infrastructure` | 0 | `#4FC3F7` 浅蓝 |
| `foundation_model` | 1 | `#BA68C8` 紫色 |
| `middleware` | 2 | `#FFB74D` 橙色 |
| `vertical_app` | 3 | `#81C784` 绿色 |
| `distribution` | 4 | `#E57373` 红色 |

## 评分公式

### 壁垒分 (Defensibility)

```
score_defensibility = 0.35 × AI_MODEL_MAP[ai_model_dependency]
                    + 0.30 × WORKFLOW_MAP[workflow_integration_level]
                    + 0.20 × FLYWHEEL_MAP[data_flywheel]
                    + 0.15 × DATA_ASSET_MAP[proprietary_data_asset]
```

权重逻辑：技术壁垒（自研模型 35%）+ 锁定效应（工作流嵌入 30%）+ 数据飞轮（20%）+ 专有数据（15%）。

### 巨头关注度 (Incumbent Attention)

```
score_incumbent_attention = 0.50 × INCUMBENT_MAP[incumbent_direct_competitor]
                          + 0.30 × CUSTOMER_MAP[customer_segment_type]
                          + 0.20 × FUNDING_MAP[funding_stage]
```

权重逻辑：是否与巨头正面竞争占 50%——这是最硬的信号。客户类型 + 融资阶段反映「这块肉有多大」，占 50%。

### 价值截留 (Value Capture)

```
score_value_capture = 0.35 × PRICING_MAP[pricing_model]
                    + 0.30 × INFERENCE_MAP[inference_cost_exposure]
                    + 0.20 × CUSTOMER_MAP[customer_segment_type]
                    + 0.15 × AI_MODEL_MAP[ai_model_dependency]
```

权重逻辑：定价能力（35%）+ 推理成本结构（30%）是价值截留的核心。客户类型和技术依赖的影响相对次要。

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
  competitive_scoring.py       ← 枚举→数值映射 + 3 个加权公式
        │
        ▼
  research 表写入
        │
        ▼
  infographic.py               ← ECharts HTML → Playwright PNG (800×600 @2x)
```

## 图表输出

两张散点图由 `webapp/infographic.py` 生成 ECharts HTML。浏览器预览和 Playwright PNG 渲染都可以内联 `webapp/static/vendor/echarts.min.js`，因此不依赖外部 CDN 可用性。

| 图 | asset_key | X 轴 | Y 轴 | 气泡大小 | 图表类型 |
|---|---|---|---|---|---|
| 竞争格局矩阵 | `chart_competitive` | score_defensibility (0-10) | score_incumbent_attention (0-10) | funding_stage_score × 4 + 6 | ECharts 四象限散点图 |
| 产业链生态位图 | `chart_ecosystem` | stack_layer (离散 5 层) | score_value_capture (0-10) | funding_stage_score × 4 + 6 | ECharts 离散轴散点图 |

### 竞争格局矩阵特性

- 四象限分割线在 x=5 / y=5
- 象限标签：Sweet Spot / Kill Zone / Waiting Room / Battlefield
- 主公司用 `#29B8D4` 青色高亮，其他公司半透明
- 默认暗色主题 `#0B1629` 背景

### 生态位图特性

- X 轴：5 层离散标签（基础设施/基础模型/中间件/垂直应用/分发渠道），每层独立颜色
- y≥7 区域标记为「高价值截留区」（绿色虚线 + 半透明绿色背景）
- 主公司 2.5px 白色边框高亮

## 相关文件

| 文件 | 职责 |
|---|---|
| `webapp/competitive_scoring.py` | 全部分数映射表和计算公式 |
| `webapp/field_rules.py` | Layer 1 规则层，零 LLM 成本 |
| `webapp/field_validator.py` | Layer 3 Pydantic 白名单验证 |
| `webapp/competitive_batch.py` | 批处理 CLI 工具，支持 extract/score/distribution 命令 |
| `webapp/pipeline.py` | 研究流水线中调度三层管道（`_extract_enum_fields`） |
| `webapp/db.py` | 入库前自动 normalize + compute_scores |
| `webapp/infographic.py` | ECharts 图表 HTML 生成 + Playwright PNG 渲染 |
| `prompts/layer3-group-a-technical.md` | LLM 组 A Prompt |
| `prompts/layer3-group-b-competitive.md` | LLM 组 B Prompt |
| `prompts/layer3-group-c-business.md` | LLM 组 C Prompt |

## 已知局限

1. **权重未经过经验校准** — 当前权重基于商业逻辑推理，未使用公开市场数据（如已知结果的 20 家公司）做 ground-truth 对齐
2. **壁垒框架覆盖不全** — 当前 4 个子项侧重技术架构特征，未纳入 Helmer 7 Powers 中的反定位（counter-positioning）、规模经济、品牌等维度
3. **6 个非关键字段无多数投票** — 仅 3 个关键字段做 ensemble，其余 6 个字段单次调用直接入库
4. **评分分布未做敏感性分析** — 权重 ±20% 变动对各公司排名的影响未经测试
