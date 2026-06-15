# 竞争格局定位图 & AI 栈生态位图改造技术文档

版本：v1.0
适用项目：GZHv2
目标输出：微信公众号知识卡片插图，宽版 800×600
关联诊断稿：chart_analysis.html

---

## 1. 背景与目标

当前项目中有两类图表：

1. 竞争格局定位图
2. AI 栈生态位图

它们原本更接近“内部分析图”，但实际用途是“知识卡片插图”。因此评价标准不是数据是否完整，而是：

- 800×600 尺寸内是否可读；
- 3 秒内是否能看出 1–2 个结论；
- 坐标含义是否稳定；
- 读者是否能识别目标公司和核心竞品；
- 图表能否作为文章中的辅助判断，而不是迫使读者重新分析。

最终目标：

> 把两张图从“分析型图表”改成“结论型插图”。

---

## 2. 当前主要问题

### 2.1 组内归一化导致坐标失真

当前图表把分数归一化到 0–1。问题是：

- 同一家公司在不同竞品组里位置会变化；
- 分数相近的公司也会被强行拉开；
- 原始分低的公司可能因为组内相对高而被放到“机会区”；
- 图表失去稳定语义。

结论：

> 知识卡片图表不应使用组内归一化，应使用原始 0–10 绝对分。

---

### 2.2 竞争格局图的 X/Y 轴语义需要统一

建议固定为：

| 轴 | 字段 | 含义 |
|---|---|---|
| X 轴 | score_incumbent_attention | 巨头关注度 / 大厂竞争压力 |
| Y 轴 | score_defensibility | 护城河强度 |

象限解释：

| 象限 | 含义 |
|---|---|
| 左上 | 战略机会区：低巨头压力 + 高护城河 |
| 右上 | 硬仗区：高巨头压力 + 高护城河 |
| 右下 | 高危区：高巨头压力 + 低护城河 |
| 左下 | 边缘区：低巨头压力 + 低护城河 |

不建议反过来使用 X=护城河、Y=巨头压力，因为读者更容易理解“向右压力更大、向上防守更强”。

---

### 2.3 AI 栈生态位图尺寸不匹配

当前生态位图默认更接近 1440×900，而知识卡片目标是 800×600。直接缩放后会产生：

- 标签字号过小；
- 泳道文字过挤；
- 气泡和 pin 重叠；
- 图表像报告截图，而不像卡片插图。

结论：

> 图表应原生按 800×600 生成，而不是大图缩小。

---

### 2.4 distribution 不应合并到应用层

当前可能把 distribution 合并进“应用层”。这会导致语义错误。

原因：

- distribution 是分发渠道、入口、插件市场、聚合平台；
- vertical_app 是垂直应用、工作流工具、行业软件；
- 二者商业逻辑不同：前者靠入口和流量，后者靠场景和工作流嵌入。

建议把 AI 栈分为 5 条泳道：

1. 分发渠道
2. 垂直应用
3. 中间件层
4. 模型层
5. 基础设施层

---

### 2.5 竞品匿名气泡价值低

知识卡片读者需要知道：

- 目标公司是谁；
- 它旁边是谁；
- 它比谁更靠右；
- 谁和它在同一层。

如果竞品只是匿名气泡，信息价值很低。

建议：

- 目标公司强高亮；
- 核心竞品全部显示名称；
- 竞品最多 5–6 个；
- 不展示过多小公司；
- 标签开启重叠避让。

---

### 2.6 AI 栈生态位图中的 markPoint pin 应删除

当前 pin 与目标气泡功能重复，并且容易遮挡标签。

建议：

- 删除 markPoint pin；
- 仅使用更大的目标气泡 + 白色描边 + 标签强调；
- 标题中直接输出目标公司的判断结论。

---

## 3. 改造后的图表设计原则

### 3.1 一图只表达一个判断

竞争格局图表达：

> 这家公司处在机会区、硬仗区、高危区还是边缘区？

AI 栈生态位图表达：

> 它处于 AI 产业链哪一层，价值捕获能力强不强？

---

### 3.2 标题必须直接给结论

不建议使用：

```text
竞争格局定位图
AI 栈生态位图
```

建议使用：

```text
Cursor：高护城河 × 中低巨头压力
Cursor：垂直应用层 / 中高价值捕获
```

标题应该先给答案，再让图表解释答案。

---

### 3.3 坐标必须稳定

所有分数统一使用 0–10 绝对分：

```text
0–3：低
4–6：中
7–10：高
```

不再使用组内 0–1 相对分。

---

### 3.4 图表元素控制

800×600 下建议限制：

| 元素 | 规则 |
|---|---|
| 目标公司 | 1 个，强高亮 |
| 竞品 | 3–6 个 |
| 标签 | 全部展示 |
| 网格线 | 少量、浅色 |
| tooltip | 可保留，但不作为主要信息 |
| 图例 | 简短 |
| 注释 | 最多 1 条结论注释 |

---

## 4. 评分体系改造方案

### 4.1 竞争格局图评分

#### 4.1.1 score_defensibility：护城河强度

建议公式：

```text
score_defensibility =
0.30 × data_lock_in
+ 0.25 × workflow_lock_in
+ 0.20 × technical_uniqueness
+ 0.15 × distribution_lock
+ 0.10 × brand_or_community
```

字段解释：

| 字段 | 含义 |
|---|---|
| data_lock_in | 是否有专有数据、客户数据、使用反馈数据 |
| workflow_lock_in | 是否嵌入客户核心流程 |
| technical_uniqueness | 技术是否难复制 |
| distribution_lock | 是否拥有渠道、入口、平台关系 |
| brand_or_community | 是否形成品牌、社区、开发者心智 |

评分标准：

```text
0–3：弱，主要靠功能差异
4–6：中，有一定流程或数据积累
7–10：强，有数据、流程、渠道或生态壁垒
```

---

#### 4.1.2 score_incumbent_attention：巨头关注度

建议公式：

```text
score_incumbent_attention =
0.40 × incumbent_overlap
+ 0.25 × market_size
+ 0.20 × strategic_dependency
+ 0.15 × user_visibility
```

字段解释：

| 字段 | 含义 |
|---|---|
| incumbent_overlap | 是否直接进入大厂核心产品范围 |
| market_size | 市场规模是否足够大 |
| strategic_dependency | 是否依赖大厂模型、云、系统、分发渠道 |
| user_visibility | 用户是否足够显性、增长是否容易被大厂观察到 |

incumbent_overlap 评分建议：

```text
none = 1
adjacent = 4
partial_overlap = 7
direct_overlap = 10
```

不建议继续把 funding_stage 作为主要权重。融资阶段只能说明市场验证，不等于巨头关注。

---

### 4.2 AI 栈生态位图评分

#### 4.2.1 stack_layer：AI 栈层级

建议枚举：

```python
STACK_LAYERS = {
    "distribution": "分发渠道",
    "vertical_app": "垂直应用",
    "middleware": "中间件层",
    "foundation_model": "模型层",
    "infrastructure": "基础设施层",
}
```

展示顺序：

```python
STACK_LANE_LABELS = [
    "分发渠道",
    "垂直应用",
    "中间件层",
    "模型层",
    "基础设施层",
]
```

说明：

- 分发渠道放最上方，因为它更接近用户入口；
- 基础设施放最下方，因为它更接近底层供给；
- 中间层不再被迫塞进应用层。

---

#### 4.2.2 score_value_capture：价值捕获能力

建议公式：

```text
score_value_capture =
0.35 × pricing_power
+ 0.25 × gross_margin
+ 0.25 × workflow_lock_in
+ 0.15 × customer_budget_level
```

字段解释：

| 字段 | 含义 |
|---|---|
| pricing_power | 是否有定价权 |
| gross_margin | 毛利空间是否高 |
| workflow_lock_in | 是否嵌入高频关键流程 |
| customer_budget_level | 客户是否有明确预算 |

不建议让 ai_model_dependency 同时影响护城河和价值捕获，否则两张图会被同一因素重复推高。

---

## 5. 数据结构设计

### 5.1 公司评分对象

建议统一输出以下结构：

```json
{
  "company_name": "Cursor",
  "is_target": true,
  "scores": {
    "defensibility": 7.2,
    "incumbent_attention": 4.1,
    "value_capture": 6.8
  },
  "stack_layer": "vertical_app",
  "display": {
    "label": "Cursor",
    "bubble_size": 16,
    "highlight": true
  },
  "evidence": {
    "defensibility_reason": "深度嵌入 IDE 工作流，有用户习惯与上下文积累",
    "incumbent_attention_reason": "与 GitHub Copilot 存在直接竞争",
    "value_capture_reason": "订阅制 + 高频开发场景 + 团队付费潜力"
  }
}
```

---

### 5.2 图表输入结构

#### 竞争格局图输入

```json
{
  "chart_type": "competitive_landscape",
  "target": "Cursor",
  "width": 800,
  "height": 600,
  "companies": [
    {
      "name": "Cursor",
      "x": 4.1,
      "y": 7.2,
      "is_highlight": true
    },
    {
      "name": "GitHub Copilot",
      "x": 9.0,
      "y": 7.0,
      "is_highlight": false
    }
  ]
}
```

#### AI 栈生态位图输入

```json
{
  "chart_type": "ai_stack_ecosystem",
  "target": "Cursor",
  "width": 800,
  "height": 600,
  "companies": [
    {
      "name": "Cursor",
      "x": 6.8,
      "y": "垂直应用",
      "is_highlight": true
    },
    {
      "name": "OpenAI",
      "x": 5.5,
      "y": "模型层",
      "is_highlight": false
    }
  ]
}
```

---

## 6. 渲染层改造方案

### 6.1 竞争格局图渲染规则

ECharts 配置建议：

```js
xAxis: {
  type: "value",
  min: 0,
  max: 10,
  name: "巨头关注度 →",
  axisLabel: {
    formatter: function (v) {
      if (v === 0) return "低";
      if (v === 5) return "中";
      if (v === 10) return "高";
      return "";
    }
  }
},
yAxis: {
  type: "value",
  min: 0,
  max: 10,
  name: "护城河强度 ↑",
  axisLabel: {
    formatter: function (v) {
      if (v === 0) return "低";
      if (v === 5) return "中";
      if (v === 10) return "高";
      return "";
    }
  }
}
```

分割线：

```js
markLine: {
  silent: true,
  symbol: "none",
  lineStyle: {
    type: "dashed",
    color: "rgba(27,42,74,0.18)",
    width: 1
  },
  data: [
    { xAxis: 5, label: { show: false } },
    { yAxis: 5, label: { show: false } }
  ]
}
```

象限背景：

```js
markArea: {
  silent: true,
  data: [
    [{ xAxis: 0, yAxis: 5 }, { xAxis: 5, yAxis: 10 }],   // 战略机会区
    [{ xAxis: 5, yAxis: 5 }, { xAxis: 10, yAxis: 10 }],  // 硬仗区
    [{ xAxis: 5, yAxis: 0 }, { xAxis: 10, yAxis: 5 }],   // 高危区
    [{ xAxis: 0, yAxis: 0 }, { xAxis: 5, yAxis: 5 }]     // 边缘区
  ]
}
```

---

### 6.2 AI 栈生态位图渲染规则

X 轴：

```js
xAxis: {
  type: "value",
  min: 0,
  max: 10,
  name: "",
  axisLabel: {
    formatter: function (v) {
      if (v === 0) return "低";
      if (v === 5) return "中";
      if (v === 10) return "高";
      return "";
    }
  }
}
```

Y 轴：

```js
yAxis: {
  type: "category",
  inverse: true,
  data: ["分发渠道", "垂直应用", "中间件层", "模型层", "基础设施层"]
}
```

高价值区：

```js
markArea: {
  silent: true,
  data: [
    [{ xAxis: 7 }, { xAxis: 10 }]
  ],
  itemStyle: {
    color: "rgba(40, 180, 100, 0.07)"
  }
}
```

标签：

```js
label: {
  show: true,
  formatter: function(params) {
    return params.data.name;
  },
  position: "right",
  backgroundColor: "rgba(255,255,255,0.92)",
  borderRadius: 4,
  padding: [3, 6]
}
```

删除：

```js
markPoint: {
  symbol: "pin"
}
```

---

## 7. 代码落点

### 7.1 infographic.py

重点修改：

1. 图表默认尺寸；
2. 去除 normalize_group_scores；
3. X/Y 轴 min/max 从 0–1 改为 0–10；
4. markLine 从 0.5 改为 5；
5. markArea 坐标从 0/0.5/1 改为 0/5/10；
6. label 默认显示公司名；
7. AI 栈生态位图删除 markPoint pin；
8. AI 栈增加“分发渠道”泳道；
9. 标题改成动态结论句。

---

### 7.2 competitive_scoring.py

重点修改：

1. 新增字段：
   - incumbent_overlap
   - workflow_lock_in
   - pricing_power
   - customer_budget_level
   - gross_margin
   - distribution_lock
   - brand_or_community

2. 重构三个核心分：
   - score_defensibility
   - score_incumbent_attention
   - score_value_capture

3. 保留旧字段兼容：
   - ai_model_dependency
   - company_type
   - funding_stage
   - inference_cost_exposure

但旧字段不再作为主要权重。

---

### 7.3 scoring-system.md

重点修改：

1. 明确竞争格局图坐标：
   - X = 巨头关注度
   - Y = 护城河强度

2. 明确 AI 栈图坐标：
   - X = 价值捕获能力
   - Y = AI 栈层级

3. 删除“组内归一化”作为默认展示策略；
4. 增加评分证据说明；
5. 增加示例公司评分样例。

---

## 8. 生成流程改造

建议流程：

```text
原始研究文本
   ↓
字段抽取
   ↓
评分因子抽取
   ↓
评分计算
   ↓
核心竞品筛选
   ↓
图表数据组装
   ↓
ECharts HTML 渲染
   ↓
截图 / PNG 导出
   ↓
进入知识卡片排版
```

---

## 9. 核心竞品筛选规则

最多展示 6 个点：

```text
1 个目标公司
2 个直接竞品
1 个大厂竞品
1 个同层代表公司
1 个上下游代表公司
```

排序优先级：

```text
same_category_direct_competitor
> incumbent_direct_overlap
> same_stack_layer
> high_value_capture
> high_defensibility
```

避免展示过多无关公司。

---

## 10. 图表标题生成规则

### 10.1 竞争格局图标题

```python
def get_competitive_title(company):
    x = company["score_incumbent_attention"]
    y = company["score_defensibility"]

    if x < 5 and y >= 5:
        zone = "战略机会区"
        desc = "高护城河 × 低巨头压力"
    elif x >= 5 and y >= 5:
        zone = "硬仗区"
        desc = "高护城河 × 高巨头压力"
    elif x >= 5 and y < 5:
        zone = "高危区"
        desc = "低护城河 × 高巨头压力"
    else:
        zone = "边缘区"
        desc = "低护城河 × 低巨头压力"

    return f"{company['name']}：{zone}｜{desc}"
```

---

### 10.2 AI 栈生态位图标题

```python
def get_stack_title(company):
    vc = company["score_value_capture"]

    if vc >= 7:
        level = "高价值捕获"
    elif vc >= 4:
        level = "中价值捕获"
    else:
        level = "低价值捕获"

    return f"{company['name']}：{company['stack_layer']} / {level}"
```

---

## 11. 视觉规范

### 11.1 尺寸

```text
width = 800
height = 600
```

不得再用大图缩小。

---

### 11.2 字号

| 元素 | 字号 |
|---|---|
| 标题 | 20–24px |
| 副标题 | 13–15px |
| 坐标轴 | 12–14px |
| 公司标签 | 11–13px |
| 象限标签 | 13–15px |
| 图例 | 11–12px |

---

### 11.3 配色

目标公司：

```text
#29B8D4
```

竞品：

```text
rgba(27,42,74,0.30–0.55)
```

背景：

```text
浅色卡片：#FFFFFF
深色卡片：#0B1629
```

象限背景透明度：

```text
0.06–0.12
```

---

## 12. 验收标准

### 12.1 功能验收

- 竞争格局图使用原始 0–10 分；
- AI 栈生态位图使用原始 0–10 分；
- 不再默认使用组内归一化；
- AI 栈图有 5 条泳道；
- distribution 不再进入应用层；
- 目标公司高亮；
- 核心竞品显示名称；
- 生态位图无 markPoint pin；
- 两张图默认输出 800×600。

---

### 12.2 视觉验收

在 800×600 下检查：

- 标题是否一眼给出结论；
- 标签是否可读；
- 目标公司是否最突出；
- 竞品是否能识别；
- 是否能在 3 秒内判断目标公司的位置；
- 是否没有无意义气泡；
- 是否没有严重重叠。

---

### 12.3 内容验收

每张图必须能回答一个问题：

竞争格局图：

```text
这家公司处于机会区、硬仗区、高危区还是边缘区？
```

AI 栈生态位图：

```text
这家公司在 AI 产业链哪一层？价值捕获能力强不强？
```

如果图表不能直接回答上述问题，则视为不合格。

---

## 13. 实施顺序

### P0：必须做

1. 图表尺寸统一为 800×600；
2. 去掉图表展示层的组内归一化；
3. 竞争格局图 X/Y 轴语义统一；
4. AI 栈生态位图增加“分发渠道”泳道；
5. 核心竞品全部显示标签；
6. 删除生态位图 markPoint pin。

---

### P1：建议做

1. 重构 score_value_capture；
2. 新增 incumbent_overlap；
3. 新增 workflow_lock_in；
4. 图表标题动态生成结论；
5. 竞品筛选限制为 3–6 个。

---

### P2：后续优化

1. 给每个分数保留 evidence；
2. 输出评分解释卡；
3. 对每个公司保留评分来源；
4. 增加人工校准入口；
5. 不同赛道建立不同评分模板。

---

## 14. 最终判断

两张图的方向是对的，但当前版本更像“内部研究图”，还不是“知识卡片插图”。

改造重点不是增加信息，而是减少信息、固定语义、强化结论。

最终标准：

> 读者不需要理解评分体系，也能从图上看出目标公司的位置判断。
