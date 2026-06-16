# 卡片与图片资产规范

当前规范版本：`card_spec_version = v2`

## 套卡系统

系统支持多套卡片规格并存，通过 `card_set_key` 区分：

| 套卡 | set_key | 卡片数 | 说明 |
| --- | --- | --- | --- |
| 套卡1 · 经典8张 | `v1` | 8 | 内置，不可删除 |
| 套卡2 · 新版7张 | `v2` | 7 | 内置，不可删除 |
| 用户自定义 | `user_{timestamp}` | 7 或 8 | 基于 v1 或 v2 规格创建 |

每家公司在每个套卡中独立维护卡片编排（`card_compositions` / `card_items`，由 `card_set_key` 区分）；文字定稿仍按字段写入 `final_fields`，不绑定卡片索引。旧 `final_content` 仅保留兼容读取。

## 卡片规范 v2（套卡2）

| 卡片 | 主题 | 主要内容 |
| --- | --- | --- |
| `card_1` | 封面 | 公司名、公司类型、Logo |
| `card_2` | 公司概览 | 官网截图、公司定义、地点、融资、主产品、产品亮点、ARR、注册用户 |
| `card_3` | 生态位与变现 | 生态位图、生态位、错位竞争、成本优势、TAM/SAM/SOM、市场 CAGR |
| `card_4` | 创始人与团队 | 创始人照片、姓名、工作/学历背景、团队规模、团队背景 |
| `card_5` | 核心客户 | 主产品图、理想客户画像、主/次客户细分、留存或付费相关指标 |
| `card_6` | GTM 与增长 | 增长策略、GTM motion、增长飞轮、CAC/LTV/获客效率 |
| `card_7` | 竞争格局 | 竞争格局图、竞品摘要、技术壁垒、迁移成本、巨头压力/壁垒评分 |

## 图片资产槽位（v2）

| asset_key | 用途 | 默认归属 | 生成方式 |
| --- | --- | --- | --- |
| `logo` | 公司 Logo | `card_1` | collected |
| `website_screenshot` | 官网首页截图 | `card_2` | collected |
| `founder_photo` | 创始人照片 | `card_4` | collected |
| `chart_ecosystem` | AI 产业链生态位图 | `card_3` | generated / echarts |
| `product_main` | 主产品截图 | `card_3` | collected |
| `flywheel` | 增长飞轮图 | `card_6` | generated / svg |
| `chart_competitive` | 竞争格局散点图 | `card_7` | generated / echarts |
| `competitors` | 竞品截图 | `card_7` | collected |
| `competitors_logo_strip` | 竞品 Logo 横排拼图 | `card_7` | generated / composite |

### 废弃资产槽位（DB 行保留，停止在 v2 渲染）

| asset_key | 原归属 | 废弃版本 |
| --- | --- | --- |
| `office` | card_2 | v2 |
| `timeline` | card_3 | v2 |
| `products_other` | card_5 | v2 |

## 自动图表触发规则

| 套卡 | 触发时机 | 生成资产 |
| --- | --- | --- |
| v1 | card_3 确认 | timeline |
| v1 | card_6 确认 | flywheel |
| v1 | card_7 确认 | chart_competitive + chart_ecosystem |
| v2 | card_3 确认 | chart_ecosystem |
| v2 | card_6 确认 | flywheel |
| v2 | card_7 确认 | chart_competitive |

## 资产交付接口

排版中心读取：`GET /api/assets/resolved?company=<company_name>&spec=v1|v2`

返回 `card_spec_version = "v2"`，`card_assets` 结构以 `card_N` 为 key。

## 套卡 API

```
GET    /api/card-sets                          — 列出所有套卡
POST   /api/card-sets                          — 新建用户套卡
DELETE /api/card-sets/<set_key>                — 删除用户套卡
POST   /api/final/<company>/init-set/<set_key> — 初始化公司编排结构
DELETE /api/final/<company>/set/<set_key>       — 删除公司套卡数据
```
