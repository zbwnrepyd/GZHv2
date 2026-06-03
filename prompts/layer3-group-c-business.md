# Layer 3-C — 商业侧枚举提取

根据公司描述，提取以下字段。规则层已有结果的字段请跳过（直接使用规则层值，不要覆盖）。只输出 JSON，无 Markdown 包裹。

## 输出字段

```json
{
  "pricing_model": "outcome_based | enterprise_contract | subscription | usage_based | freemium | free",
  "customer_segment_type": "b2b_enterprise | b2b_smb | developer_api | b2b2c | b2c",
  "stack_layer": "infrastructure | foundation_model | middleware | vertical_app | distribution"
}
```

## 枚举定义

**pricing_model**
- `outcome_based`：按效果/结果付费
- `enterprise_contract`：企业合同制，Contact Sales
- `subscription`：订阅制，按月/年付费
- `usage_based`：按用量付费（token/call）
- `freemium`：免费增值，免费版+付费版
- `free`：完全免费

**customer_segment_type**
- `b2b_enterprise`：大型企业客户
- `b2b_smb`：中小企业/团队
- `developer_api`：开发者/API 优先
- `b2b2c`：通过企业触达终端用户
- `b2c`：直接面向消费者

**stack_layer**
- `infrastructure`：底层算力/存储/向量数据库
- `foundation_model`：基础模型/API 层
- `middleware`：中间件/工具链/编排
- `vertical_app`：垂直应用层
- `distribution`：分发/平台/搜索引擎

## 规则层已有字段（跳过不输出）
{rule_fields_hint}

信息不足时选择最接近枚举值。已有规则层结果的字段直接从输出中省略。
输出纯 JSON。
