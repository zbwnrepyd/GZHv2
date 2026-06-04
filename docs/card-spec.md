# 卡片与图片资产规范

当前规范版本：`card_spec_version = v1`

本文档冻结当前系统的卡片数量、卡片主题和图片资产槽位。排版中心只消费后端返回的 resolved assets，不负责判断图片来源、候选优先级或兜底策略。

## 卡片规范 v1

| 卡片 | 主题 | 主要内容 |
| --- | --- | --- |
| `card_1` | 首页 | 公司名、公司类型、核心定位 |
| `card_2` | 公司介绍 | 位置、定义、创始人、团队、融资 |
| `card_3` | 发展沿袭 | 时间线和关键里程碑 |
| `card_4` | 主产品 | 主产品名、定义、亮点、成就 |
| `card_5` | 其他产品 | 其他产品线和产品矩阵 |
| `card_6` | 商业模式 | 盈利方式、冷启动、GTM、客户群体、增长飞轮 |
| `card_7` | 竞争格局 | 壁垒、竞品、竞争格局、生态位 |
| `card_8` | 总结 | 赛道契机、机会判断和建议 |

## 图片资产槽位

资产槽位不等于卡片数量。一张卡可以使用多个资产，一个资产也可以被多张卡复用。

| asset_key | 用途 | 默认归属 |
| --- | --- | --- |
| `logo` | 公司 Logo | `card_1` |
| `website_screenshot` | 官网首页或官网关键截图 | `card_2` |
| `office` | 公司位置、办公室或地图 | `card_2` |
| `timeline` | 发展沿袭时间线图 | `card_3` |
| `product_main` | 主产品截图 | `card_4` |
| `products_other` | 其他产品截图或产品矩阵图 | `card_5` |
| `flywheel` | 增长飞轮图 | `card_6` |
| `competitors` | 竞品截图、广告图或竞品页面图 | `card_7` |
| `competitors_logo_strip` | 三个竞品 Logo 的 16:9 横排拼图 | `card_7` |
| `chart_competitive` | AI 创业公司竞争格局图 | `card_7` |
| `chart_ecosystem` | AI 产业链生态位图 | `card_7` |

## 资产交付接口

排版中心优先读取：

```text
GET /api/assets/resolved?company=<company_name>
```

返回结构以卡片为第一层，资产槽位为第二层：

```json
{
  "company_name": "DemoCo",
  "card_spec_version": "v1",
  "card_assets": {
    "card_4": {
      "product_main": {
        "url": "/images/DemoCo/variants/product.png",
        "local_path": "/images/DemoCo/variants/product.png",
        "kind": "image",
        "variant_type": "ratio_16_9",
        "format": "png",
        "scale": 1,
        "width": 1600,
        "height": 900,
        "status": "fallback"
      }
    }
  }
}
```

Resolver 选择优先级：

```text
selected_variant_id / is_selected
↓
final_score 最高且未被 reject 的候选
↓
company_assets.local_path
↓
placeholder
```

`canvas/` 目录当前仍作为代码路径保留；产品语义上称为“排版中心”。后续如需目录改名，应作为单独迁移处理。
