// API 自动加载：从 URL 参数 ?company=xxx 拉取 final_db 数据

// 英文字段名 → 中文（canvas 布局使用中文键）
const FIELD_EN_TO_CN = {
  company_name: '公司名', company_type: '类型',
  location: '地理位置', company_def: '公司定义',
  founder_name: '创始人', founder_edu: '学历背景',
  founder_bg: '工作背景', founder_achievement: '过往成就',
  team_size: '团队规模', team_highlight: '团队亮点',
  funding_info: '融资信息', website_url: '官网',
  timeline_events: '发展沿袭时间线',
  main_product_name: '主产品名', main_product_def: '产品定义',
  main_product_highlight: '亮点功能', main_product_achievement: '产品成就',
  main_product_img_src: '产品图片',
  other_products: '其他产品',
  revenue_model: '盈利方式', cold_start: '冷启动策略',
  gtm_strategy: 'GTM与增长策略', customer_segment: '客户群体',
  growth_flywheel: '增长飞轮',
  moat: '竞争壁垒', competitors: '竞争格局',
  market_opportunity: '赛道契机',
};

function mapLegacyFields(card) {
  const data = {};
  for (const [enKey, value] of Object.entries(card.fields || {})) {
    const cnKey = FIELD_EN_TO_CN[enKey] || enKey;
    data[cnKey] = value;
  }
  return data;
}

function applyImagePaths(data, card) {
  for (const [enKey, path] of Object.entries(card.img_paths || {})) {
    const cnKey = FIELD_EN_TO_CN[enKey] || enKey;
    if (cnKey === '产品图片' || cnKey === 'main_product_img_src') {
      data._image = path;
    }
  }
}

function parseMarkdownCardData(markdownContent, cardIndex) {
  if (typeof parseSingleCardMarkdown === 'function') {
    return parseSingleCardMarkdown(markdownContent, cardIndex);
  }
  if (typeof parseFullMarkdown !== 'function') {
    return {};
  }

  const parsed = parseFullMarkdown(markdownContent);
  return parsed[cardIndex] || Object.values(parsed)[0] || {};
}

async function loadFromAPI(company) {
  const url = `/api/final/export/${encodeURIComponent(company)}?format=json`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`API 返回 ${resp.status}`);
  const json = await resp.json();

  const allCardData = {};
  for (const [ci, card] of Object.entries(json.cards || {})) {
    const idx = parseInt(ci);
    const hasMarkdown = typeof card.markdown_content === 'string' && card.markdown_content.trim();
    const data = hasMarkdown ? parseMarkdownCardData(card.markdown_content, idx) : {};
    if (hasMarkdown) data._markdown = card.markdown_content;
    const legacyData = mapLegacyFields(card);

    for (const [key, value] of Object.entries(legacyData)) {
      if (!data[key]) {
        data[key] = value;
      }
    }
    applyImagePaths(data, card);
    data._title = data._title || `卡片${idx}`;
    allCardData[idx] = data;
  }

  return { company_name: json.company_name, allCardData };
}

async function loadSingleCardFromAPI(company, cardIndex) {
  const result = await loadFromAPI(company);
  const cardData = result.allCardData[cardIndex] || {};
  const resolved = await loadResolvedAssetsFromAPI(company);
  const assets = resolved ? flattenResolvedAssets(resolved) : await loadAssetsFromAPI(company);
  cardData._assets = assets;
  cardData._allAssets = assets;
  cardData._resolvedCardAssets = resolved?.card_assets?.[`card_${cardIndex}`] || {};
  return cardData;
}

// ─── 资产加载 ──────────────────────────────────────────────────

// card_index → asset_key 映射（与后端 CARD_ASSET_MAP 一致）
const CARD_ASSET_MAP = {
  1: "logo",
  2: "office",
  3: "timeline",
  4: "product_main",
  5: "products_other",
  6: "flywheel",
  7: "competitors",
};

const DEMAND_ASSET_KEYS = [
  "logo", "website_screenshot", "office", "product_main", "products_other",
  "competitors", "competitors_logo_strip", "chart_competitive", "chart_ecosystem", "flywheel", "timeline",
];

async function loadAssetsFromAPI(company) {
  const resolved = await loadResolvedAssetsFromAPI(company);
  if (resolved) {
    return flattenResolvedAssets(resolved);
  }
  try {
    const resp = await fetch(`/api/assets/${encodeURIComponent(company)}`);
    if (!resp.ok) return {};
    const json = await resp.json();
    return json.assets || {};
  } catch {
    return {};
  }
}

async function loadResolvedAssetsFromAPI(company) {
  try {
    const resp = await fetch(`/api/assets/resolved?company=${encodeURIComponent(company)}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

function flattenResolvedAssets(resolved) {
  const out = {};
  const cardAssets = resolved?.card_assets || {};
  Object.values(cardAssets).forEach((slots) => {
    Object.entries(slots || {}).forEach(([assetKey, asset]) => {
      if (!asset) return;
      const localPath = asset.local_path || asset.url || '';
      out[assetKey] = { ...asset, local_path: localPath, url: asset.url || localPath };
    });
  });
  return out;
}

// asset_key → 中文标签
const ASSET_LABELS = {
  logo: "Logo",
  website_screenshot: "官网截图",
  office: "办公室或地图",
  product_main: "主产品截图",
  products_other: "其他产品截图",
  competitors: "竞品截图",
  competitors_logo_strip: "三个竞品 Logo 横排图",
  chart_competitive: "AI 创业公司竞争格局图",
  chart_ecosystem: "AI 产业链生态位图",
  flywheel: "飞轮图",
  timeline: "时间线图",
};
