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

async function loadFromAPI(company) {
  const url = `/api/final/export/${encodeURIComponent(company)}?format=json`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`API 返回 ${resp.status}`);
  const json = await resp.json();

  const allCardData = {};
  for (const [ci, card] of Object.entries(json.cards || {})) {
    const idx = parseInt(ci);
    const data = {};
    for (const [enKey, value] of Object.entries(card.fields || {})) {
      const cnKey = FIELD_EN_TO_CN[enKey] || enKey;
      data[cnKey] = value;
    }
    // 图片路径
    for (const [enKey, path] of Object.entries(card.img_paths || {})) {
      const cnKey = FIELD_EN_TO_CN[enKey] || enKey;
      if (cnKey === '产品图片' || cnKey === 'main_product_img_src') {
        data._image = path;
      }
    }
    data._title = `卡片${idx}`;
    allCardData[idx] = data;
  }

  return { company_name: json.company_name, allCardData };
}
