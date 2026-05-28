// Markdown → 卡片数据解析器
// 解析 Module 2 输出的 Markdown，按 ## 卡片N 标题分割为8个卡片数据对象

function parseCardMarkdown(markdown) {
  const sections = [];
  const lines = markdown.split('\n');
  let currentSection = null;
  let currentLines = [];

  for (const line of lines) {
    const h2Match = line.match(/^##\s*卡片(\d+)/);
    if (h2Match) {
      if (currentSection !== null) {
        sections.push({ index: currentSection, content: currentLines.join('\n') });
      }
      currentSection = parseInt(h2Match[1]);
      currentLines = [line];
    } else if (currentSection !== null) {
      currentLines.push(line);
    }
  }
  if (currentSection !== null && currentLines.length > 0) {
    sections.push({ index: currentSection, content: currentLines.join('\n') });
  }

  return sections;
}

const FIELD_LABELS = {
  company_name: '公司名',
  company_type: '类型',
  类型: '类型',
  location: '地理位置',
  位置: '地理位置',
  company_def: '公司定义',
  founder_name: '创始人',
  founder_edu: '学历背景',
  founder_bg: '工作背景',
  founder_achievement: '过往成就',
  team_size: '团队规模',
  team_highlight: '团队亮点',
  funding_info: '融资信息',
  融资: '融资信息',
  website_url: '官网',
  timeline_events: '发展沿袭时间线',
  main_product_name: '主产品名',
  main_product_def: '产品定义',
  main_product_highlight: '亮点功能',
  亮点: '亮点功能',
  main_product_achievement: '产品成就',
  成就: '产品成就',
  main_product_img_src: '产品图片',
  other_products: '其他产品',
  revenue_model: '盈利方式',
  盈利: '盈利方式',
  cold_start: '冷启动策略',
  冷启动: '冷启动策略',
  gtm_strategy: 'GTM与增长策略',
  GTM: 'GTM与增长策略',
  customer_segment: '客户群体',
  growth_flywheel: '增长飞轮',
  飞轮: '增长飞轮',
  moat: '竞争壁垒',
  壁垒: '竞争壁垒',
  competitors: '竞争格局',
  market_opportunity: '赛道契机',
  机遇: '赛道契机',
};

const CANONICAL_CARD_TITLES = {
  1: '首页',
  2: '公司介绍',
  3: '发展沿袭',
  4: '主产品',
  5: '其他产品',
  6: '商业模式',
  7: '竞争格局',
  8: '总结',
};

function normalizeLabel(label) {
  return FIELD_LABELS[label] || label;
}

function normalizeValue(label, value) {
  if (!value) return value;
  if (label === '发展沿袭时间线') {
    return formatTimelineValue(value);
  }
  if (label === '竞争格局') {
    return formatCompetitorsValue(value);
  }
  return value;
}

function stripInlineMarkdown(value) {
  return String(value || '')
    .trim()
    .replace(/^\*\*(.+?)\*\*$/, '$1')
    .replace(/^\*(.+?)\*$/, '$1')
    .trim();
}

function getMarkdownTitle(markdown, cardIndex) {
  const headingMatch = String(markdown || '').match(/^#{1,6}\s*(?:卡片\d+[：:]?\s*)?(.+)$/m);
  return headingMatch ? headingMatch[1].trim() : `卡片${cardIndex}`;
}

function stripMarkdownHeading(markdown) {
  return String(markdown || '')
    .split('\n')
    .filter((line) => !/^#{1,6}\s+/.test(line.trim()))
    .join('\n')
    .trim();
}

function hasVisibleCardData(data) {
  return Object.keys(data || {}).some((key) => !key.startsWith('_') && data[key]);
}

function parseJsonArray(value) {
  const trimmed = String(value || '').trim();
  if (!trimmed.startsWith('[')) return null;
  try {
    const parsed = JSON.parse(trimmed);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function formatTimelineValue(value) {
  const items = parseJsonArray(value);
  if (!items) return value;
  return items.map((item) => {
    const date = item.date || item.time || item.year || '暂缺';
    const event = item.event || item.title || item.desc || item.description || '暂缺';
    const impact = item.impact || item.significance || item.result || '';
    return impact ? `- **${date}** ${event} — *${impact}*` : `- **${date}** ${event}`;
  }).join('\n');
}

function formatCompetitorsValue(value) {
  const items = parseJsonArray(value);
  if (!items) return value;
  return items.map((item, idx) => {
    const name = item.name || item.company || item.competitor || `竞品${idx + 1}`;
    const product = item.product || item.description || item.positioning || '暂缺';
    const data = item.data || item.metric || item.evidence || item.note || '暂缺';
    return `**TOP${idx + 1}**：${name} — ${product}（${data}）`;
  }).join('\n');
}

/**
 * 从 Markdown 段落中提取键值对
 * 支持的格式：
 *   **标签**：值
 *   # 标题
 *   - 列表项
 *   ![图片](path)
 */
function extractCardData(section, cardIndex) {
  const data = {};
  const lines = section.content.split('\n');
  const bodyLines = [];
  const competitorLines = [];

  // 提取卡片标题
  const titleMatch = lines[0]?.match(/卡片\d+：(.+)/);
  if (titleMatch) {
    data._title = titleMatch[1].trim();
  }
  if (CANONICAL_CARD_TITLES[cardIndex]) {
    data._title = CANONICAL_CARD_TITLES[cardIndex];
  }

  // 提取键值对
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || /^##\s*卡片\d+/.test(trimmed)) continue;

    const h1Match = trimmed.match(/^#\s+(.+)/);
    if (h1Match && cardIndex === 1) {
      data['公司名'] = h1Match[1].trim();
      continue;
    }

    const h2Match = trimmed.match(/^##\s+(.+)/);
    if (h2Match && cardIndex === 4) {
      data['主产品名'] = h2Match[1].trim();
      continue;
    }
    if (/^#{1,6}\s+/.test(trimmed)) continue;

    const boldOnlyMatch = trimmed.match(/^\*\*(.+?)\*\*$/);
    if (boldOnlyMatch && cardIndex === 1 && !data['类型']) {
      data['类型'] = stripInlineMarkdown(trimmed);
      continue;
    }

    const kvMatch = trimmed.match(/^(?:-\s*)?\*\*(.+?)\*\*[：:]\s*(.*)/);
    if (kvMatch) {
      const rawKey = kvMatch[1].trim();
      const value = kvMatch[2].trim();
      if (/^TOP\d+$/i.test(rawKey)) {
        competitorLines.push(trimmed);
      } else if (cardIndex === 5 && !FIELD_LABELS[rawKey] && rawKey !== '其他产品') {
        bodyLines.push(trimmed);
      } else {
        const label = normalizeLabel(rawKey);
        data[label] = normalizeValue(label, value);
      }
    } else {
      bodyLines.push(trimmed);
    }

    // 提取图片
    const imgMatch = line.match(/!\[.*?\]\((.+?)\)/);
    if (imgMatch) {
      data._image = imgMatch[1].trim();
    }

  }

  if (cardIndex === 1 && !data['类型'] && bodyLines.length > 0) {
    data['类型'] = stripInlineMarkdown(bodyLines.join('\n'));
  }
  if (cardIndex === 2 && !data['公司定义'] && bodyLines.length > 0) {
    data['公司定义'] = bodyLines.join('\n');
  }
  if (cardIndex === 3 && !data['发展沿袭时间线'] && bodyLines.length > 0) {
    data['发展沿袭时间线'] = bodyLines.join('\n');
  }
  if (cardIndex === 4 && !data['产品定义'] && bodyLines.length > 0) {
    data['产品定义'] = bodyLines.join('\n');
  }
  if (cardIndex === 5 && !data['其他产品'] && bodyLines.length > 0) {
    data['其他产品'] = bodyLines.join('\n');
  }
  if (cardIndex === 7 && !data['竞争格局'] && competitorLines.length > 0) {
    data['竞争格局'] = competitorLines.join('\n');
  }
  if (!data._body && bodyLines.length > 0) {
    data._body = bodyLines.join('\n');
  }

  return data;
}

/**
 * 解析完整 Markdown，返回 { 1: {...data}, 2: {...data}, ... }
 */
function parseFullMarkdown(markdown) {
  const sections = parseCardMarkdown(markdown);
  const result = {};
  for (const section of sections) {
    result[section.index] = extractCardData(section, section.index);
  }
  if (sections.length === 0 && String(markdown || '').trim()) {
    result[1] = parseSingleCardMarkdown(markdown, 1);
  }
  return result;
}

function parseSingleCardMarkdown(markdown, cardIndex) {
  const content = String(markdown || '').trim();
  if (!content) return {};

  const sections = parseCardMarkdown(content);
  const section = sections.find((item) => item.index === cardIndex) || sections[0] || { index: cardIndex, content };
  const data = extractCardData(section, cardIndex);

  data._title = CANONICAL_CARD_TITLES[cardIndex] || data._title || getMarkdownTitle(section.content, cardIndex);
  if (!hasVisibleCardData(data)) {
    data._body = stripMarkdownHeading(section.content) || section.content;
  }

  return data;
}
