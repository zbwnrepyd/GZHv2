# Layer 3-B — 竞争侧枚举提取

根据公司描述，提取以下 3 个字段。只输出 JSON，无 Markdown 包裹。

## 输出字段

```json
{
  "incumbent_direct_competitor": "openai | google | microsoft | multiple | other | none",
  "workflow_integration_level": "system_of_record | workflow_embedded | plugin_addon | standalone_tool",
  "inference_cost_exposure": "high | medium | low | none"
}
```

## 枚举定义

**incumbent_direct_competitor**
- `openai`：OpenAI 是主要竞争对手
- `google`：Google/DeepMind 是主要竞争对手
- `microsoft`：Microsoft/GitHub 是主要竞争对手
- `multiple`：与多个巨头直接竞争
- `other`：竞争对手是其他大公司（非以上三家）
- `none`：不与巨头直接竞争

**workflow_integration_level**
- `system_of_record`：嵌为客户核心系统，迁移成本极高
- `workflow_embedded`：嵌入日常工作流，有一定切换成本
- `plugin_addon`：作为插件/附加功能存在
- `standalone_tool`：独立工具，切换成本低

**inference_cost_exposure**
- `high`：核心成本是推理，利润对模型定价极度敏感
- `medium`：推理是成本之一，但有缓存/优化对冲
- `low`：推理占比低，或有自建推理能力
- `none`：不依赖模型推理

信息不足时选择最接近的枚举值，不要输出自由文本。
输出纯 JSON。
