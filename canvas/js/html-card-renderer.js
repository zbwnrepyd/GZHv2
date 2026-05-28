// ─── 常量 ───────────────────────────────────────────────────
const CARD_TITLES_HTML = {
  1: '首页', 2: '公司介绍', 3: '发展沿袭',
  4: '主产品', 5: '其他产品', 6: '商业模式',
  7: '竞争格局', 8: '总结',
};

const NAV_SECTIONS = [
  { index: 1, title: '首页' },
  { index: 2, title: '公司介绍' },
  { index: 3, title: '发展沿袭' },
  { index: 4, title: '主产品' },
  { index: 5, title: '其他产品' },
  { index: 6, title: '商业模式' },
  { index: 7, title: '竞争格局' },
  { index: 8, title: '总结' },
];

const DEFAULT_CARD_CSS = `
:root {
  --card-width:        900px;
  --card-height:       1200px;
  --card-padding-x:    72px;
  --card-padding-y:    56px;
  --page-label-size:   18px;
  --nav-size:          17px;
  --nav-separator:     " ｜ ";
  --title-size:        52px;
  --title-line-height: 1.1;
  --body-size:         26px;
  --body-line-height:  1.5;
  --label-size:        18px;
  --text-primary:      #111827;
  --text-muted:        #9CA3AF;
  --text-body:         #374151;
  --accent:            #29B8D4;
  --navy:              #1B2A4A;
  --bg-card:           #FFFFFF;
  --watermark-opacity: 0.05;
}
`.trim();

// ─── 工具函数 ────────────────────────────────────────────────
function escapeHTML(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function inlineMarkdown(value) {
  return escapeHTML(value)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>');
}

function bodyMarkdownToHTML(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  const listItems = [];
  const blocks = [];
  for (const line of lines) {
    if (/^[-*]\s+/.test(line)) {
      listItems.push(`<li>${inlineMarkdown(line.replace(/^[-*]\s+/, ''))}</li>`);
    } else {
      if (listItems.length) blocks.push(`<ul>${listItems.splice(0).join('')}</ul>`);
      blocks.push(`<p>${inlineMarkdown(line)}</p>`);
    }
  }
  if (listItems.length) blocks.push(`<ul>${listItems.join('')}</ul>`);
  return blocks.join('');
}

// cardData 使用中文键名（来自 markdown-parser 和 FIELD_EN_TO_CN 映射）
function val(cardData, key, fallback = '暂缺') {
  const v = cardData?.[key];
  return (v && String(v).trim() && String(v).trim() !== '暂缺') ? String(v).trim() : fallback;
}

function firstVal(cardData, keys, fallback = '暂缺') {
  for (const key of keys) {
    const value = val(cardData, key, '');
    if (value) return value;
  }
  return fallback;
}

function bodyFallback(cardData, fallback = '暂缺') {
  return val(cardData, '_body', fallback);
}

function valueOrBody(cardData, keys, fallback = '暂缺') {
  const value = firstVal(cardData, Array.isArray(keys) ? keys : [keys], '');
  return value || bodyFallback(cardData, fallback);
}

// ─── 导航栏 ──────────────────────────────────────────────────
function navHTML(cardIndex) {
  return NAV_SECTIONS.map((section, i) => {
    const labelText = section.title;
    const label = section.index === cardIndex
      ? `<strong>${escapeHTML(labelText)}</strong>`
      : `<span>${escapeHTML(labelText)}</span>`;
    return i < NAV_SECTIONS.length - 1
      ? label + '<span class="nav-sep">｜</span>'
      : label;
  }).join('');
}

// ─── 各页卡片渲染 ────────────────────────────────────────────

function renderPage1({ companyName, cardData }) {
  const name = val(cardData, '公司名', '') || companyName || '暂缺';
  const type = val(cardData, '类型', '');
  return `
<article class="knowledge-card card-index-1">
  <p class="page-label">page 1</p>
  <div class="p1-layout">
    <p class="p1-tagline">三分钟认识一家AI初创公司</p>
    <h1 class="p1-title">${escapeHTML(name)}</h1>
    <div class="p1-logo-placeholder" aria-hidden="true"></div>
    ${type ? `<p class="p1-type">${escapeHTML(type)}</p>` : ''}
  </div>
</article>`;
}

function renderPage2({ cardData }) {
  const location = val(cardData, '地理位置');
  const companyDef = val(cardData, '公司定义');
  const whereWhat = [location, companyDef].filter(v => v !== '暂缺').join(' — ') || '暂缺';
  return `
<article class="knowledge-card card-index-2">
  <p class="page-label">page 2</p>
  <nav class="card-nav">${navHTML(2)}</nav>
  <div class="card-content">
    <div class="field-row">
      <span class="field-label">在哪里、干什么</span>
      <div class="field-value">${bodyMarkdownToHTML(whereWhat)}</div>
    </div>
    <div class="field-row">
      <span class="field-label">团队情况</span>
      <div class="field-value">${bodyMarkdownToHTML(
        '**' + val(cardData, '创始人') + '**（' + val(cardData, '学历背景') + '）\n' +
        val(cardData, '工作背景') + '\n' +
        '团队规模：' + val(cardData, '团队规模') + ' · ' + val(cardData, '团队亮点')
      )}</div>
    </div>
    <div class="field-row">
      <span class="field-label">投融资情况</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, '融资信息'))}</div>
    </div>
  </div>
</article>`;
}

function renderPage3({ cardData }) {
  const timeline = cardData?.['发展沿袭时间线'] || '';
  let timelineHTML = '';
  try {
    const events = typeof timeline === 'string' ? JSON.parse(timeline) : timeline;
    if (Array.isArray(events)) {
      timelineHTML = events.map(e =>
        `<li><span class="tl-date">${escapeHTML(e.date || '')}</span>
         <span class="tl-event">${inlineMarkdown(e.event || '')}</span>
         ${e.impact ? `<span class="tl-impact"> — ${inlineMarkdown(e.impact)}</span>` : ''}</li>`
      ).join('');
    }
  } catch {
    timelineHTML = bodyMarkdownToHTML(String(timeline)) || '<li>暂缺</li>';
  }
  return `
<article class="knowledge-card card-index-3">
  <p class="page-label">page 3</p>
  <nav class="card-nav">${navHTML(3)}</nav>
  <div class="card-content">
    <h2 class="card-section-title">发展沿袭</h2>
    <ul class="timeline-list">${timelineHTML || '<li>暂缺</li>'}</ul>
  </div>
</article>`;
}

function renderPage4({ cardData }) {
  return `
<article class="knowledge-card card-index-4">
  <p class="page-label">page 4</p>
  <nav class="card-nav">${navHTML(4)}</nav>
  <div class="card-content">
    <h2 class="card-section-title">${escapeHTML(val(cardData, '主产品名', '产品1'))}</h2>
    <div class="field-row">
      <span class="field-label">主要功能</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, '产品定义') + '\n' + val(cardData, '亮点功能'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">竞争优势</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, '产品成就'))}</div>
    </div>
  </div>
</article>`;
}

function renderPage5({ cardData }) {
  let products = [];
  let rawProducts = cardData?.['其他产品'] || '';
  try {
    products = typeof rawProducts === 'string' ? JSON.parse(rawProducts) : (rawProducts || []);
  } catch { products = []; }
  const first = products[0] || {};
  const productBody = first.def || rawProducts || bodyFallback(cardData);
  const productHighlight = first.highlight || '';
  return `
<article class="knowledge-card card-index-5">
  <p class="page-label">page 5</p>
  <nav class="card-nav">${navHTML(5)}</nav>
  <div class="card-content">
    <h2 class="card-section-title">${escapeHTML(first.name || val(cardData, '_title', '其他产品'))}</h2>
    <div class="field-row">
      <span class="field-label">主要功能</span>
      <div class="field-value">${bodyMarkdownToHTML(productBody)}</div>
    </div>
    ${productHighlight ? `<div class="field-row">
      <span class="field-label">竞争优势</span>
      <div class="field-value">${bodyMarkdownToHTML(productHighlight)}</div>
    </div>` : ''}
  </div>
</article>`;
}

function renderPage6({ cardData }) {
  return `
<article class="knowledge-card card-index-6">
  <p class="page-label">page 6</p>
  <nav class="card-nav">${navHTML(6)}</nav>
  <div class="card-content">
    <div class="field-row">
      <span class="field-label">盈利方式</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, '盈利方式'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">冷启动与增长策略</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, '冷启动策略') + '\n' + val(cardData, 'GTM与增长策略'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">增长飞轮</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, '增长飞轮'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">客户群体</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, '客户群体'))}</div>
    </div>
  </div>
</article>`;
}

function renderPage7({ cardData }) {
  let competitors = [];
  try {
    const raw = cardData?.['竞争格局'];
    competitors = typeof raw === 'string' ? JSON.parse(raw) : (raw || []);
  } catch { competitors = []; }
  const competitorHTML = competitors.length ? competitors.map((c, i) =>
    `<li><strong>TOP${i + 1} ${escapeHTML(c.name || '')}：</strong>${inlineMarkdown(c.product || c.description || '')}（${escapeHTML(c.data || c.metric || '暂缺')}）</li>`
  ).join('') : bodyMarkdownToHTML(val(cardData, '竞争格局', ''));
  return `
<article class="knowledge-card card-index-7">
  <p class="page-label">page 7</p>
  <nav class="card-nav">${navHTML(7)}</nav>
  <div class="card-content">
    <div class="field-row">
      <span class="field-label">竞争壁垒</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, '竞争壁垒'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">优势是什么</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, '竞争壁垒'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">现在赛道大环境是什么样的</span>
      <div class="field-value"><ul class="competitor-list">${competitorHTML || '<li>暂缺</li>'}</ul></div>
    </div>
  </div>
</article>`;
}

function renderPage8({ cardData }) {
  const opportunity = valueOrBody(cardData, '赛道契机');
  return `
<article class="knowledge-card card-index-8">
  <p class="page-label">page 8</p>
  <nav class="card-nav">${navHTML(8)}</nav>
  <div class="card-content">
    <div class="field-row">
      <span class="field-label">这个栏目是干嘛的</span>
      <div class="field-value">${bodyMarkdownToHTML(opportunity)}</div>
    </div>
    <div class="p8-follow">
      <p>最伟大的公司，往往诞生于最混沌的时代。</p>
      <p class="p8-cta">关注我</p>
    </div>
  </div>
</article>`;
}

// ─── 主路由 ──────────────────────────────────────────────────
const PAGE_RENDERERS = {
  1: renderPage1, 2: renderPage2, 3: renderPage3,
  4: renderPage4, 5: renderPage5, 6: renderPage6,
  7: renderPage7, 8: renderPage8,
};

function renderKnowledgeCard({ companyName, cardIndex, cardData }) {
  const renderer = PAGE_RENDERERS[cardIndex];
  if (!renderer) return `<article class="knowledge-card"><div class="empty-card">未知卡片 ${cardIndex}</div></article>`;
  return renderer({ companyName, cardIndex, cardData });
}

function renderCardSource({ companyName, cardIndex, cardData }) {
  return `<style>\n${DEFAULT_CARD_CSS}\n</style>\n${renderKnowledgeCard({ companyName, cardIndex, cardData }).trim()}\n`;
}

function renderEmptyCard(message) {
  return `<article class="knowledge-card"><div class="empty-card">${escapeHTML(message || '暂无数据')}</div></article>`;
}

function renderSourceIntoDocument(doc, source) {
  const targetDoc = doc || document;
  const root = targetDoc.getElementById('card-page');
  if (!root) return;
  root.innerHTML = source || renderEmptyCard('暂无卡片源码');
}

function injectCardCss(doc, styleState, cardIndex) {
  const targetDoc = doc || document;
  let style = targetDoc.getElementById('custom-card-css');
  if (!style) {
    style = targetDoc.createElement('style');
    style.id = 'custom-card-css';
    targetDoc.head.appendChild(style);
  }
  const globalCss = styleState?.globalCss || '';
  const perCardCss = styleState?.perCardCss?.[cardIndex] || '';
  style.textContent = `${globalCss}\n${perCardCss}`;
}
