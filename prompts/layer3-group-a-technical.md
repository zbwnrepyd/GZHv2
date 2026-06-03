# Layer 3-A — 技术侧枚举提取

根据公司描述，提取以下 3 个字段。只输出 JSON，无 Markdown 包裹。

## 输出字段

```json
{
  "ai_model_dependency": "proprietary_model | fine_tuned | multi_model | openai_only | no_ai_core",
  "data_flywheel": "yes | partial | no",
  "proprietary_data_asset": "yes_core | yes_supplementary | no"
}
```

## 枚举定义

**ai_model_dependency**
- `proprietary_model`：自研模型，有独立训练能力
- `fine_tuned`：基于开源模型微调，有差异化权重
- `multi_model`：同时使用多个模型（自研+外部），有路由/编排
- `openai_only`：仅调用 OpenAI API，无自研
- `no_ai_core`：产品核心不是 AI

**data_flywheel**
- `yes`：产品使用→数据积累→模型改进→更好产品，形成闭环
- `partial`：有数据积累但闭环不完整
- `no`：数据不反馈到模型

**proprietary_data_asset**
- `yes_core`：独占数据是核心壁垒
- `yes_supplementary`：有专有数据但非核心壁垒
- `no`：无专有数据

信息不足时选择最接近的枚举值，不要输出自由文本。
输出纯 JSON。
