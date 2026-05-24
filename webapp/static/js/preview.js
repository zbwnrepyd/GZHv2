// Markdown 预览生成

// 卡片字段到 Markdown 的映射
const CARD_FIELD_MAP = {
  1: [
    { key: 'company_name', label: '公司名', format: v => `# ${v}` },
    { key: 'company_type', label: '公司类型', format: v => `**类型**：${v}` },
  ],
  2: [
    { key: 'location', label: '地理位置', format: v => `**地理位置**：${v}` },
    { key: 'company_def', label: '公司定义', format: v => `**公司定义**：${v}` },
    { key: 'founder_name', label: '创始人', format: v => `**创始人**：${v}` },
    { key: 'founder_edu', label: '学历背景', format: v => `**学历背景**：${v}` },
    { key: 'founder_bg', label: '工作背景', format: v => `**工作背景**：${v}` },
    { key: 'founder_achievement', label: '过往成就', format: v => `**过往成就**：${v}` },
    { key: 'team_size', label: '团队规模', format: v => `**团队规模**：${v}` },
    { key: 'team_highlight', label: '团队亮点', format: v => `**团队亮点**：${v}` },
    { key: 'funding_info', label: '融资信息', format: v => `**融资信息**：${v}` },
    { key: 'website_url', label: '官网', format: v => v ? `**官网**：${v}` : null },
  ],
  3: [
    { key: 'timeline_events', label: '发展沿袭时间线', format: v => formatTimeline(v) },
  ],
  4: [
    { key: 'main_product_name', label: '主产品名', format: v => `## ${v}` },
    { key: 'main_product_def', label: '产品定义', format: v => `**产品定义**：${v}` },
    { key: 'main_product_highlight', label: '亮点功能', format: v => `**亮点功能**：${v}` },
    { key: 'main_product_achievement', label: '产品成就', format: v => `**产品成就**：${v}` },
    { key: 'main_product_img_src', label: '产品图片', format: (v, imgPath) => imgPath ? `![产品图片](${imgPath})` : (v ? `*图片来源：${v}*` : null) },
  ],
  5: [
    { key: 'other_products', label: '其他产品', format: v => formatOtherProducts(v) },
  ],
  6: [
    { key: 'revenue_model', label: '盈利方式', format: v => `**盈利方式**：${v}` },
    { key: 'cold_start', label: '冷启动策略', format: v => `**冷启动策略**：${v}` },
    { key: 'gtm_strategy', label: 'GTM与增长策略', format: v => `**GTM与增长策略**：${v}` },
    { key: 'customer_segment', label: '客户群体', format: v => `**客户群体**：${v}` },
    { key: 'growth_flywheel', label: '增长飞轮', format: v => `**增长飞轮**：${v}` },
  ],
  7: [
    { key: 'moat', label: '竞争壁垒', format: v => `**竞争壁垒**：${v}` },
    { key: 'competitors', label: '竞争格局', format: v => formatCompetitors(v) },
    { key: 'market_opportunity', label: '赛道契机', format: v => `**赛道契机**：${v}` },
  ],
};

const CARD_TITLES = {
  1: '首页', 2: '公司介绍', 3: '发展沿袭',
  4: '产品线（主产品）', 5: '其他产品', 6: '商业模式', 7: '总结'
};

function formatTimeline(val) {
  if (!val || val === '暂缺') return `**发展沿袭时间线**：暂缺`;
  try {
    const events = typeof val === 'string' ? JSON.parse(val) : val;
    if (!Array.isArray(events) || events.length === 0) return `**发展沿袭时间线**：暂无数据`;
    return events.map(e => `- **${e.date}** ${e.event}${e.impact ? ` — *${e.impact}*` : ''}`).join('\n');
  } catch {
    return `**发展沿袭时间线**：\n${val}`;
  }
}

function formatOtherProducts(val) {
  if (!val || val === '暂缺' || val === '[]') return '';
  try {
    const products = typeof val === 'string' ? JSON.parse(val) : val;
    if (!Array.isArray(products) || products.length === 0) return '';
    return products.map(p => `- **${p.name}**：${p.def}（${p.highlight}）`).join('\n');
  } catch {
    return `**其他产品**：\n${val}`;
  }
}

function formatCompetitors(val) {
  if (!val || val === '暂缺') return `**竞争格局**：暂缺`;
  try {
    const comps = typeof val === 'string' ? JSON.parse(val) : val;
    if (!Array.isArray(comps) || comps.length === 0) return `**竞争格局**：暂无数据`;
    return comps.map((c, i) => `**TOP${i + 1}**：${c.name} — ${c.product}（${c.data}）`).join('\n');
  } catch {
    return `**竞争格局**：\n${val}`;
  }
}

function buildCardMarkdown(cardIndex, fields, imgPaths = {}) {
  const fieldDefs = CARD_FIELD_MAP[cardIndex] || [];
  const lines = [];
  lines.push(`## 卡片${cardIndex}：${CARD_TITLES[cardIndex]}`);
  lines.push('');

  for (const def of fieldDefs) {
    const val = fields[def.key];
    let imgPath = imgPaths[def.key] || null;
    if (!val || val === '暂缺') {
      // 有图片路径时仍然显示
      if (imgPath) {
        lines.push(`**${def.label}**：暂缺`);
        lines.push(`![](${imgPath})`);
        continue;
      }
      // 完全空则跳过可选字段
      continue;
    }
    const result = def.format(val, imgPath);
    if (result !== null) {
      lines.push(result);
    }
  }
  lines.push('');
  return lines.join('\n');
}

function buildFullMarkdown(allCards, imgPaths = {}) {
  const parts = [];
  for (let i = 1; i <= 7; i++) {
    const card = allCards[i];
    if (card && Object.keys(card).length > 0) {
      parts.push(buildCardMarkdown(i, card, imgPaths[i] || {}));
    }
  }
  // 添加钩子段落
  if (allCards._hooks) {
    parts.push('---');
    parts.push('');
    parts.push('## 传播钩子段落');
    parts.push('');
    if (allCards._hooks.hook_paragraph_1) parts.push(allCards._hooks.hook_paragraph_1);
    if (allCards._hooks.hook_paragraph_2) parts.push(allCards._hooks.hook_paragraph_2);
    if (allCards._hooks.hook_paragraph_3) parts.push(allCards._hooks.hook_paragraph_3);
    parts.push('');
  }
  return parts.join('\n');
}
