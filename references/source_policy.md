# 来源策略 — 每个字段类型应从哪里获取

## A 类：直接事实字段

**示例**: company_name, location, founder_name, team_size, funding_info, website_url, main_product_name, competitors, tech_stack

| 来源 | 优先级 | 可靠性 | 适用字段 |
|------|--------|--------|---------|
| 官网 About / Team / Product 页 | 1 | High | company_def, main_product, team_size, tech_stack |
| Crunchbase / PitchBook | 2 | High | funding_info, founder_name, competitors |
| LinkedIn (公司页 / 创始人页) | 2 | Medium | founder_bg, founder_edu, team_size |
| 新闻稿 / PR Newswire | 2 | Medium | company_achievement, funding_info |
| G2 / Gartner / Product Hunt | 3 | Medium | competitors, main_product_highlight |
| Tavily 搜索 (高置信匹配) | 3 | Low-Medium | location, team_highlight |

**原则**: 官方来源 > 聚合数据库 > 媒体 > 搜索推测。至少一个官方来源才标 `confirmed`。

---

## B 类：公式字段

**示例**: mrr, ltv_cac_ratio, funding_stage_score

| 输入字段 | 公式 | 输出 | 条件 |
|---------|------|------|------|
| arr | arr / 12 | mrr | arr confirmed |
| ltv, cac | ltv / cac | ltv_cac_ratio | 两者 confirmed |
| funding_stage | FUNDING_MAP 映射 | funding_stage_score | funding_stage confirmed |

**原则**: 输入字段缺失或状态为 unavailable 时，不输出任何数值。状态标 `derived`，不标 `confirmed`。

---

## C 类：市场估算字段

**示例**: tam, sam, som, market_cagr, market_size_source_note

| 来源 | 优先级 | 可靠性 |
|------|--------|--------|
| 行业报告 (Gartner / IDC / CB Insights) | 1 | High |
| 公司 S-1 / 招股书引用 | 1 | High |
| 分析师报告 (Dealroom / PitchBook) | 2 | Medium |
| 媒体引用 ("$X billion market") | 3 | Low |
| 自下而上估算 (company ARR / share %) | 4 | Proxy |

**必须记录市场边界**: region (global / US / APAC), segment, customer type。无边界参数的市场规模数字不可用。

**原则**: 大多标 `proxy` 或 `manual_needed`。不要标 `confirmed` 除非能追溯到具体行业报告。

---

## D 类：私有经营指标

**示例**: cac, ltv, churn_rate, gross_margin, burn_rate, runway_months, arr, revenue_metrics

| 来源 | 可靠性 | 要求 |
|------|--------|------|
| 公司财报 / S-1 / 招股书 | High | 明确数字，不推测 |
| 投资人材料 / 路演资料 | High | 需标注来源文件 |
| 创始人访谈 / 播客 / 博客 | Medium | 需标注原文，>6 个月需重验证 |
| Latka / Sacra / GetLatka | Medium | 需标注数据库名与更新日期 |
| 媒体披露 | Low | 仅限知名媒体，需交叉验证 |
| Tavily 搜索推测 | Do Not Use | 不允许用搜索文章推断经营数字 |

**原则**: 默认标 `unavailable`。只有上述来源出现明确披露才标 `confirmed`。禁止从竞品数据反推。

---

## E 类：B2B 不适配字段

**示例**: active_users, registered_users, paying_users

| 公司类型 | 应使用的字段 | 不适配字段 |
|---------|-------------|-----------|
| B2C | active_users | — |
| B2B SaaS | paying_customers / account_count | active_users, registered_users |
| Developer API | api_calls / developer_count | active_users, paying_users |
| Marketplace | gmv / supplier_count / buyer_count | active_users |

**原则**: 
1. 先判定 business_type
2. 对不适配字段标 `not_applicable` + 带解释
3. 不适配字段不参与评分计算
4. 不适配字段不进入卡片正文

---

## Gap Refetch 策略

缺口补采时，不同类别的字段有不同的处理优先级：

| Category | Refetch Priority | 策略 |
|----------|-----------------|------|
| A | High | 生成定向 Tavily query，重跑 L3 |
| B | None | 只在输入字段 confirmed 后自动计算，不补搜 |
| C | Medium | 生成市场报告搜索 query，最多 3 轮 |
| D | Skip | 不补搜。mark unavailable 即可 |
| E | Skip | 不补搜。mark not_applicable |

**补搜上限**: 每公司最多 2 轮 gap refetch（含 pre-gap 和 post-gap）。超过后剩余 gap 标记为 unavailable/manual_needed，不无限重试。
