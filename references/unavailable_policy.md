# 不可得字段策略 — 哪些字段不该补，以及为什么

## 核心原则

**字段"暂缺"不是失败，是信息不对称的正常结果。** 私有公司的经营数据在公开网络上不存在。强行补字段比空着更糟糕——LLM 编造的数据看起来很合理，但会污染评分体系和卡片内容。

## 五类不可得场景

### 1. 私有经营指标 (D 类)

**字段**: cac, ltv, churn_rate, retention_rate, gross_margin, burn_rate, runway_months, revenue_metrics, growth_metrics, arr（部分公司）

**原因**: 这些是公司内部经营数据。SaaS 公司不公开披露 CAC、churn rate、毛利率。B2B 私有公司尤其如此。

**处理**:
- 状态: `unavailable`
- 评分: 不参与评分（依赖这些字段的评分公式自动跳过）
- 卡片: 不进入正文
- 补搜: **禁止**。再搜也搜不到，浪费 API 额度

**例外**: 以下情况可以补：
- 公司已上市（有财报/S-1）
- Latka / Sacra / GetLatka 数据库已收录
- 创始人公开发言明确说了数字
- 知名科技媒体（TechCrunch / The Information）披露了具体数字

### 2. B2B 不适配字段 (E 类)

**字段**: active_users, registered_users, paying_users

**原因**: 这些字段隐含 B2C 假设（"用户"= 个人用户）。B2B 企业用的是 account / customer / logo 数。API 公司用的是 developer / API call 数。Marketplace 用的是 GMV / supplier / buyer 数。

**处理**:
- 状态: `not_applicable`
- 评分: 不参与
- 卡片: 不进入正文
- 补搜: **禁止**

**公司类型 → 替代字段**:
| 公司类型 | 不适配字段 | 替代字段 |
|---------|-----------|---------|
| B2B SaaS | active_users, registered_users | paying_customers, account_count |
| B2B Enterprise | active_users | logo_count, enterprise_customers |
| Developer API | active_users, paying_users | developer_count, api_call_volume |
| Marketplace | active_users | gmv, supplier_count, buyer_count |

### 3. 市场估算字段 (C 类，部分不可得)

**字段**: tam, sam, som, market_cagr

**原因**: 这些字段需要市场报告支撑。没有报告时，LLM 推测的数字没有可靠性。

**处理**:
- 状态: `proxy`（有公开市场数据但需确认边界）或 `manual_needed`（无公开数据）
- 评分: `proxy` 值谨慎参与；`manual_needed` 不参与
- 卡片: 标注"估算"
- 补搜: 最多 1 轮定向搜索

### 4. 公式字段（输入缺失）

**字段**: mrr（无 arr）, ltv_cac_ratio（无 ltv/cac）

**原因**: 公式依赖的输入字段 unavailable，公式无法计算。

**处理**:
- 状态: `derived`
- 不可得原因: "依赖字段 X 缺失，公式无法计算"
- 评分: 不参与
- 补搜: **禁止**（补充输入字段走对应类别策略）

### 5. 公开信息但本次未搜到 (A 类部分缺失)

**字段**: founder_bg, team_highlight, cold_start, gtm_strategy 等

**原因**: 公开存在，但本次搜索未覆盖。可能是搜索词不精确、来源覆盖不全。

**处理**:
- 状态: `unavailable`
- 补搜: 允许，最多 1 轮定向 query
- 补搜后仍无: 标记 `unavailable`，不再重试

## 补搜决策矩阵

| Category | 默认策略 | 补搜上限 | 补搜后仍无 |
|----------|---------|---------|-----------|
| A (公开事实) | 1轮定向搜索 | 1轮 | unavailable |
| B (公式) | 不补搜 | 0 | 等输入字段确认 |
| C (市场) | 1轮定向搜索 | 1轮 | manual_needed |
| D (私有) | 不补搜 | 0 | unavailable |
| E (不适配) | 不补搜 | 0 | not_applicable |

## 实现

当前 `gap_detector.py` 的 `CRITICAL_GAPS` 字典包含所有 13 类缺口。
配合 `source_policy.md` 的 Gap Refetch 策略表，在管道中自动跳过 D/E 类字段的补搜。
