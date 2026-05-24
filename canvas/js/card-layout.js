// 7张卡片布局定义
// 画布尺寸：1080×1920 px
// 品牌色：Navy #1B2A4A, Cyan #29B8D4

const W = 1080;
const H = 1920;
const PADDING = 60;
const CONTENT_WIDTH = W - PADDING * 2;

const COLORS = {
  navy: '#1B2A4A',
  cyan: '#29B8D4',
  white: '#FFFFFF',
  lightGray: '#F5F6F8',
  mediumGray: '#9E9E9E',
  darkText: '#1a1a2e',
  accent: '#E8F4FD',
};

const FONTS = {
  title: 'bold 68px "PingFang SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif',
  subtitle: 'bold 36px "PingFang SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif',
  heading: 'bold 42px "PingFang SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif',
  body: '28px "PingFang SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif',
  bodyBold: 'bold 28px "PingFang SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif',
  small: '22px "PingFang SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif',
  tiny: '18px "PingFang SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif',
  huge: 'bold 96px "PingFang SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif',
};

// 通用元素工厂
function el(type, props = {}) {
  return { type, ...props };
}

function titleEl(text, y) {
  return el('text', { text, x: PADDING, y, font: FONTS.heading, fill: COLORS.navy });
}

function labelEl(label, y) {
  return el('text', { text: label, x: PADDING, y, font: FONTS.bodyBold, fill: COLORS.navy });
}

function valueEl(text, y, maxWidth = CONTENT_WIDTH) {
  return el('text', { text, x: PADDING + 160, y, font: FONTS.body, fill: COLORS.darkText, maxWidth: maxWidth - 160 });
}

function labelValueRow(label, text, y, maxW = CONTENT_WIDTH) {
  return [labelEl(label, y), valueEl(text, y, maxW)];
}

function accentBar(y) {
  return el('rect', { x: PADDING - 20, y, w: 6, h: 36, fill: COLORS.cyan, rx: 3 });
}

function separatorLine(y) {
  return el('line', { x1: PADDING, y1: y, x2: W - PADDING, y2: y, stroke: '#E2E4E9', strokeWidth: 1 });
}

// ── 卡片1：首页 ──────────────────────────────────
function card1Layout(data) {
  const elements = [];
  const cx = W / 2, cy = H / 2;

  // 背景渐变条
  elements.push(el('rect', { x: 0, y: 0, w: W, h: H, fill: COLORS.white }));
  elements.push(el('rect', { x: 0, y: 0, w: 8, h: H, fill: COLORS.cyan }));

  // 顶部品牌区
  elements.push(el('text', { text: 'aistartups.cn', x: PADDING, y: 80, font: FONTS.tiny, fill: COLORS.mediumGray }));

  // 公司名（巨大居中）
  const name = data['公司名'] || data['company_name'] || '未知公司';
  elements.push(el('text', { text: name, x: cx, y: cy - 140, font: FONTS.huge, fill: COLORS.navy, textAlign: 'center', maxWidth: W - 120 }));

  // 分隔线
  elements.push(el('line', { x1: cx - 80, y1: cy - 40, x2: cx + 80, y2: cy - 40, stroke: COLORS.cyan, strokeWidth: 3 }));

  // 公司类型标签
  const typeData = data['类型'] || data['company_type'] || '';
  if (typeData) {
    elements.push(el('text', { text: typeData, x: cx, y: cy + 20, font: FONTS.subtitle, fill: COLORS.cyan, textAlign: 'center' }));
  }

  // 底部
  elements.push(el('text', { text: '三分钟认识一家AI初创公司', x: cx, y: H - 120, font: FONTS.small, fill: COLORS.mediumGray, textAlign: 'center' }));
  elements.push(el('text', { text: '卡片 1/7', x: cx, y: H - 80, font: FONTS.tiny, fill: COLORS.mediumGray, textAlign: 'center' }));

  return elements;
}

// ── 卡片2：公司介绍 ──────────────────────────────
function card2Layout(data) {
  const elements = [];
  elements.push(el('rect', { x: 0, y: 0, w: W, h: H, fill: COLORS.white }));
  elements.push(bgHeader('公司介绍'));

  let y = 180;
  const fields = ['地理位置', '公司定义', '创始人', '学历背景', '工作背景', '过往成就', '团队规模', '团队亮点', '融资信息'];

  for (const f of fields) {
    if (data[f] && data[f] !== '暂缺') {
      elements.push(accentBar(y + 6));
      const rows = labelValueRow(f, data[f], y);
      elements.push(...rows);
      y += Math.max(60, estimateTextHeight(data[f], FONTS.body, rows[1].maxWidth || CONTENT_WIDTH));
    }
  }

  // 官网
  const website = data['官网'] || data['website_url'];
  if (website && website !== '暂缺') {
    y += 20;
    elements.push(separatorLine(y));
    y += 20;
    elements.push(el('text', { text: `官网：${website}`, x: PADDING, y, font: FONTS.small, fill: COLORS.cyan }));
    y += 50;
  }

  elements.push(cardFooter(2));
  return elements;
}

// ── 卡片3：发展沿袭 ──────────────────────────────
function card3Layout(data) {
  const elements = [];
  elements.push(el('rect', { x: 0, y: 0, w: W, h: H, fill: COLORS.white }));
  elements.push(bgHeader('发展沿袭'));

  let y = 180;
  const timelineRaw = data['发展沿袭时间线'] || '';

  if (timelineRaw && timelineRaw !== '暂缺') {
    // 尝试解析时间线
    const events = parseTimeline(timelineRaw);
    if (events.length > 0) {
      events.forEach((evt, i) => {
        const dateX = PADDING + 20;
        const dotY = y + 20;
        const contentX = PADDING + 160;

        // 时间线圆点+竖线
        elements.push(el('circle', { cx: dateX, cy: dotY, r: 8, fill: i === 0 ? COLORS.cyan : COLORS.navy }));
        if (i < events.length - 1) {
          elements.push(el('line', { x1: dateX, y1: dotY + 12, x2: dateX, y2: dotY + 90, stroke: COLORS.cyan, strokeWidth: 2 }));
        }

        // 日期
        elements.push(el('text', { text: evt.date || '', x: dateX + 30, y: dotY - 4, font: FONTS.bodyBold, fill: COLORS.navy }));

        // 事件描述
        elements.push(el('text', { text: evt.event || '', x: contentX, y: dotY - 4, font: FONTS.body, fill: COLORS.darkText, maxWidth: W - contentX - PADDING }));

        // 影响
        if (evt.impact) {
          elements.push(el('text', { text: evt.impact, x: contentX, y: dotY + 38, font: FONTS.small, fill: COLORS.mediumGray, maxWidth: W - contentX - PADDING }));
          y += 80;
        } else {
          y += 60;
        }
      });
    } else {
      elements.push(el('text', { text: '发展沿袭时间线：暂缺', x: PADDING, y, font: FONTS.body, fill: COLORS.mediumGray }));
    }
  }

  elements.push(cardFooter(3));
  return elements;
}

// ── 卡片4：主产品 ────────────────────────────────
function card4Layout(data) {
  const elements = [];
  elements.push(el('rect', { x: 0, y: 0, w: W, h: H, fill: COLORS.white }));

  let y = 80;
  const productName = data['主产品名'] || data['main_product_name'] || '';
  if (productName) {
    elements.push(el('text', { text: productName, x: PADDING, y, font: FONTS.title, fill: COLORS.navy }));
    y += 90;
  }
  elements.push(bgHeader('产品线 — 主产品', y));
  y += 110;

  const fields = ['产品定义', '亮点功能', '产品成就'];
  for (const f of fields) {
    if (data[f] && data[f] !== '暂缺') {
      elements.push(accentBar(y + 6));
      const rows = labelValueRow(f, data[f], y, CONTENT_WIDTH - 100);
      elements.push(...rows);
      y += Math.max(70, estimateTextHeight(data[f], FONTS.body, CONTENT_WIDTH - 260) + 20);
    }
  }

  // 产品图片
  const imgPath = data['_image'] || data['产品图片'] || '';
  if (imgPath) {
    y += 20;
    elements.push(el('image', { src: imgPath, x: PADDING, y, w: CONTENT_WIDTH, h: 500, fit: 'cover' }));
    y += 520;
  }

  elements.push(cardFooter(4));
  return elements;
}

// ── 卡片5：其他产品 ──────────────────────────────
function card5Layout(data) {
  const elements = [];
  elements.push(el('rect', { x: 0, y: 0, w: W, h: H, fill: COLORS.white }));
  elements.push(bgHeader('其他产品线'));

  let y = 180;
  const otherRaw = data['其他产品'] || '';
  if (otherRaw && otherRaw !== '暂缺') {
    const products = parseOtherProducts(otherRaw);
    if (products.length > 0) {
      products.forEach((p, i) => {
        const cardY = y;
        elements.push(el('rect', { x: PADDING, y: cardY, w: CONTENT_WIDTH, h: 160, fill: COLORS.lightGray, rx: 12 }));
        elements.push(el('text', { text: p.name || `产品${i + 1}`, x: PADDING + 30, y: cardY + 40, font: FONTS.subtitle, fill: COLORS.navy }));
        elements.push(el('text', { text: p.def || '', x: PADDING + 30, y: cardY + 90, font: FONTS.small, fill: COLORS.darkText, maxWidth: CONTENT_WIDTH - 60 }));
        if (p.highlight) {
          elements.push(el('text', { text: `亮点：${p.highlight}`, x: PADDING + 30, y: cardY + 130, font: FONTS.tiny, fill: COLORS.cyan }));
        }
        y += 190;
      });
    } else {
      elements.push(el('text', { text: '暂无其他产品数据', x: PADDING, y, font: FONTS.body, fill: COLORS.mediumGray }));
    }
  } else {
    elements.push(el('text', { text: '暂无其他产品', x: PADDING, y, font: FONTS.body, fill: COLORS.mediumGray }));
  }

  elements.push(cardFooter(5));
  return elements;
}

// ── 卡片6：商业模式 ──────────────────────────────
function card6Layout(data) {
  const elements = [];
  elements.push(el('rect', { x: 0, y: 0, w: W, h: H, fill: COLORS.white }));
  elements.push(bgHeader('商业模式'));

  let y = 180;
  const fields = ['盈利方式', '冷启动策略', 'GTM与增长策略', '客户群体', '增长飞轮'];

  for (const f of fields) {
    if (data[f] && data[f] !== '暂缺') {
      elements.push(accentBar(y + 6));
      const rows = labelValueRow(f, data[f], y);
      elements.push(...rows);
      y += Math.max(70, estimateTextHeight(data[f], FONTS.body, rows[1].maxWidth || CONTENT_WIDTH) + 30);
    }
  }

  elements.push(cardFooter(6));
  return elements;
}

// ── 卡片7：总结 ──────────────────────────────────
function card7Layout(data) {
  const elements = [];
  elements.push(el('rect', { x: 0, y: 0, w: W, h: H, fill: COLORS.white }));
  elements.push(bgHeader('总结与展望'));

  let y = 180;
  const fields = ['竞争壁垒', '竞争格局', '赛道契机'];

  for (const f of fields) {
    if (data[f] && data[f] !== '暂缺') {
      elements.push(el('rect', { x: PADDING, y: y - 4, w: CONTENT_WIDTH, h: 6, fill: COLORS.accent, rx: 3 }));
      const rows = labelValueRow(f, data[f], y + 12);
      elements.push(...rows);
      y += Math.max(80, estimateTextHeight(data[f], FONTS.body, rows[1].maxWidth || CONTENT_WIDTH) + 40);
    }
  }

  elements.push(cardFooter(7));
  return elements;
}

// ── 布局注册表 ──────────────────────────────────
const CARD_LAYOUTS = {
  1: card1Layout,
  2: card2Layout,
  3: card3Layout,
  4: card4Layout,
  5: card5Layout,
  6: card6Layout,
  7: card7Layout,
};

// ── 辅助函数 ────────────────────────────────────

function bgHeader(title, y = 80) {
  return el('text', {
    text: title,
    x: PADDING + 40,
    y: y || 80,
    font: FONTS.title,
    fill: COLORS.navy,
  });
}

function cardFooter(cardIndex) {
  return el('text', {
    text: `${cardIndex}/7 · aistartups.cn`,
    x: W - PADDING,
    y: H - 60,
    font: FONTS.tiny,
    fill: COLORS.mediumGray,
    textAlign: 'right',
  });
}

function estimateTextHeight(text, font, maxWidth) {
  // 粗略估计：每行约 18px（body字体）+ 约25个中文字符/行
  if (!text) return 40;
  const charsPerLine = maxWidth ? Math.floor(maxWidth / 18) : 35;
  const lines = Math.ceil(String(text).length / charsPerLine);
  return Math.max(40, lines * 34 + 10);
}

function parseTimeline(raw) {
  if (!raw || raw === '暂缺') return [];
  // 支持 - **date** event — *impact* 格式
  const events = [];
  const regex = /-\s*\*\*(.+?)\*\*\s+(.+?)(?:\s*[—–-]\s*\*(.+?)\*)?$/gm;
  let match;
  while ((match = regex.exec(raw)) !== null) {
    events.push({ date: match[1].trim(), event: match[2].trim(), impact: (match[3] || '').trim() });
  }
  return events;
}

function parseOtherProducts(raw) {
  if (!raw || raw === '暂缺') return [];
  try {
    return JSON.parse(raw);
  } catch {
    // 尝试解析人类可读格式
    const products = [];
    const regex = /-\s*\*\*(.+?)\*\*[：:]\s*(.+?)[（(](.+?)[）)]/g;
    let match;
    while ((match = regex.exec(raw)) !== null) {
      products.push({ name: match[1].trim(), def: match[2].trim(), highlight: match[3].trim() });
    }
    return products;
  }
}
