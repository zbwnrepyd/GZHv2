// ─── 深海控制台卡片渲染器 ─────────────────────────────────

const DEFAULT_CARD_CSS = `
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Serif+Display:ital@0;1&family=IBM+Plex+Mono:wght@500;700&family=Instrument+Sans:wght@400;600&family=Noto+Sans+SC:wght@400;700;900&display=swap');

:root {
  --card-width:        900px;
  --card-height:       1200px;
  --card-pad:          68px;

  --font-display:      "Bebas Neue", "Source Han Sans CN", "Noto Sans SC", sans-serif;
  --font-serif:        "DM Serif Display", "Noto Serif SC", "Songti SC", serif;
  --font-mono:         "IBM Plex Mono", "SF Mono", Menlo, Consolas, monospace;
  --font-body:         "Instrument Sans", "Noto Sans SC", "PingFang SC", sans-serif;

  --fs-hero:           96px;
  --fs-s1:             40px;
  --fs-s2:             30px;
  --fs-body:           22px;
  --fs-body-sm:        17px;
  --fs-label:          11px;
  --fs-caption:        10px;
  --fs-data:           26px;
  --fs-timeline:       20px;

  --lh-body:           1.52;
  --lh-tight:          1.08;

  --field-gap:         22px;
  --field-inner-gap:   8px;
  --field-pad-y:       12px;
  --section-gap:       26px;

  --navy-deep:         #0B1629;
  --navy-mid:          #162440;
  --ink-primary:       #0D0D0D;
  --ink-secondary:     rgba(0,0,0,0.74);
  --ink-muted:         rgba(0,0,0,0.50);
  --ink-dim:           rgba(0,0,0,0.28);

  --accent:            #29B8D4;
  --accent-glow:       rgba(41,184,212,0.08);
}

/* ── 卡片基底 — 深海渐变 → 白底 ── */
.knowledge-card {
  width: var(--card-width);
  height: var(--card-height);
  padding: var(--card-pad);
  background: linear-gradient(180deg,
    #0B1629 0%, #1A2C4A 3%, #3A5070 6%, #7080A0 9%,
    #A8B4C4 14%, #D0D4DC 20%, #ECECF0 28%, #F8F8F8 38%,
    #FFFFFF 50%, #FFFFFF 100%
  );
  color: var(--ink-primary);
  overflow: hidden;
  position: relative;
  isolation: isolate;
  font-family: var(--font-body);
  font-size: var(--fs-body);
  line-height: var(--lh-body);
  display: flex;
  flex-direction: column;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

/* ── 电影噪点 ── */
.card-grain {
  position: absolute; inset: 0;
  opacity: 0.055;
  filter: url(#card-grain-filter);
  mix-blend-mode: multiply;
  pointer-events: none;
  z-index: 1;
}

/* ── 边缘晕影 ── */
.knowledge-card::after {
  content: "";
  position: absolute; inset: 0;
  background: radial-gradient(ellipse 70% 65% at 50% 50%, transparent 48%, rgba(0,0,0,0.04) 78%, rgba(0,0,0,0.10) 100%);
  pointer-events: none;
  z-index: 2;
}

/* ── 变质黑线 ── */
.card-decay {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  pointer-events: none;
  z-index: 0;
}

/* ── 内容层叠序 ── */
.knowledge-card > * { position: relative; z-index: 3; }
.knowledge-card > .card-grain,
.knowledge-card > .card-decay,
.knowledge-card > .card-filter-svg { z-index: 0; }
.knowledge-card > .card-grain { z-index: 1; }

/* ── 内容区 ── */
.card-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 0;
}

/* ── Markdown 渲染正文区 ── */
.card-body {
  flex: 1;
  min-height: 0;
}

/* ── Markdown 一级标题（卡片1公司名专用）── */
.md-h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--fs-hero);
  font-weight: 400;
  line-height: 0.94;
  letter-spacing: -0.015em;
  color: #FFFFFF;
  word-break: break-word;
}

/* ── Markdown 二级标题（章节主标题）── */
.md-h2 {
  margin: 0 0 20px;
  font-family: var(--font-serif);
  font-size: var(--fs-s1);
  font-weight: 400;
  line-height: var(--lh-tight);
  color: var(--ink-primary);
  letter-spacing: -0.01em;
}

/* ── Markdown 三级标题（子章节）── */
.md-h3 {
  margin: 0 0 14px;
  font-family: var(--font-body);
  font-size: var(--fs-s2);
  font-weight: 600;
  line-height: 1.25;
  color: var(--ink-primary);
}

/* ── Markdown 键值对字段 ── */
.md-field {
  display: flex;
  flex-direction: column;
  gap: var(--field-inner-gap);
  padding: var(--field-pad-y) 0;
}

.md-label {
  display: block;
  font: 500 var(--fs-label)/1.2 var(--font-mono);
  letter-spacing: 0.12em;
  color: var(--accent);
}

.md-value {
  font: 400 var(--fs-body)/var(--lh-body) var(--font-body);
  color: var(--ink-secondary);
}
.md-value p { margin: 0; }
.md-value p + p { margin-top: 12px; }
.md-value ul {
  margin: 0; padding-left: 0;
  display: flex; flex-direction: column; gap: 8px;
  list-style: none;
}
.md-value li {
  position: relative;
  padding-left: 18px;
}
.md-value li::before {
  content: "";
  position: absolute; left: 0; top: 0.62em;
  width: 5px; height: 1px;
  background: var(--accent);
}
.md-value strong { color: var(--ink-primary); font-weight: 600; }

/* ── Markdown 无序列表 ── */
.md-list {
  margin: 0; padding-left: 0;
  display: flex; flex-direction: column; gap: 10px;
  list-style: none;
}
.md-list li {
  position: relative;
  padding-left: 18px;
  font-size: var(--fs-body);
  line-height: var(--lh-body);
  color: var(--ink-secondary);
}
.md-list li::before {
  content: "";
  position: absolute; left: 0; top: 0.62em;
  width: 5px; height: 1px;
  background: var(--accent);
}
.md-list li strong { color: var(--ink-primary); font-weight: 600; }

/* ── Markdown 段落 ── */
.md-p {
  margin: 0 0 12px;
  font-size: var(--fs-body);
  line-height: var(--lh-body);
  color: var(--ink-secondary);
}
.md-p strong { color: var(--ink-primary); font-weight: 600; }

/* ── 空内容 ── */
.md-empty {
  color: var(--ink-muted);
  font-size: var(--fs-body);
}

/* ── 图片框（卡片2-8底部，2:1，5%侧边距，微圆角微阴影）── */
.img-box {
  margin-top: 10%;
  margin-left: 5%;
  width: 90%;
  aspect-ratio: 2 / 1;
  border-radius: 6px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.10);
  overflow: hidden;
  background: var(--navy-deep);
  flex-shrink: 0;
}
.img-box img {
  width: 100%; height: 100%;
  object-fit: cover;
  display: block;
}

/* ── 卡片1 — Magazine Poster 封面 ── */
.p1-hero {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding-bottom: 60px;
}
.p1-tagline {
  margin: 0 0 20px;
  color: rgba(255,255,255,0.55);
  font: 500 var(--fs-label)/1.2 var(--font-mono);
  letter-spacing: 0.14em;
}
.p1-title {
  margin: 0;
  max-width: 700px;
  font-family: var(--font-serif);
  font-size: var(--fs-hero);
  font-weight: 400;
  line-height: 0.94;
  letter-spacing: -0.015em;
  color: #FFFFFF;
  word-break: break-word;
}
.p1-type {
  display: inline-block;
  margin-top: 24px;
  padding: 5px 14px;
  border: 1px solid rgba(255,255,255,0.18);
  color: var(--accent);
  font: 500 var(--fs-label)/1.2 var(--font-mono);
  letter-spacing: 0.10em;
}
.p1-rule {
  margin-top: 32px;
  width: 100px;
  height: 1px;
  background: var(--accent);
}

/* ── 空卡片 ── */
.empty-card {
  height: 100%;
  display: grid;
  place-items: center;
  color: var(--ink-muted);
  font-size: 28px;
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

// ─── 图片框 ──────────────────────────────────────────────────
function imageBox(imageUrl) {
  const imgTag = imageUrl ? `<img src="${escapeHTML(imageUrl)}" alt="">` : '';
  return `<div class="img-box">${imgTag}</div>`;
}

// ─── Markdown → HTML（保留原始层级，不添加人为标签）─────────
function fullMarkdownToHTML(markdown) {
  if (!markdown || !String(markdown).trim()) return { html: '', image: '' };

  const lines = String(markdown).split('\n');
  let image = '';
  const blocks = [];
  let currentItems = [];
  let currentType = null;

  function flush() {
    if (currentType === 'list' && currentItems.length) {
      blocks.push({ type: 'list', items: [...currentItems] });
    } else if (currentType === 'para' && currentItems.length) {
      blocks.push({ type: 'para', text: currentItems.join('\n') });
    }
    currentItems = [];
    currentType = null;
  }

  let startIdx = 0;
  for (let i = 0; i < lines.length; i++) {
    if (/^##\s*卡片\d+/.test(lines[i].trim())) { startIdx = i + 1; break; }
  }

  for (let i = startIdx; i < lines.length; i++) {
    const t = lines[i].trim();
    if (!t) { flush(); continue; }

    const imgM = t.match(/^!\[.*?\]\((.+?)\)$/);
    if (imgM) { flush(); image = imgM[1].trim(); continue; }

    if (/^#{1,3}\s+/.test(t)) {
      flush();
      const hm = t.match(/^(#{1,3})\s+(.+)/);
      blocks.push({ type: 'h', level: hm[1].length, text: hm[2].trim() });
      continue;
    }

    const kvm = t.match(/^\*\*(.+?)\*\*[：:]\s*(.*)/);
    if (kvm) {
      flush();
      blocks.push({ type: 'kv', label: kvm[1].trim(), value: kvm[2].trim() });
      continue;
    }

    if (/^[-*]\s+/.test(t)) {
      if (currentType !== 'list') { flush(); currentType = 'list'; }
      currentItems.push(t.replace(/^[-*]\s+/, ''));
      continue;
    }

    if (currentType !== 'para') { flush(); currentType = 'para'; }
    currentItems.push(t);
  }
  flush();

  const parts = [];
  for (const b of blocks) {
    switch (b.type) {
      case 'h':
        if (b.level === 1) parts.push(`<h1 class="md-h1">${inlineMarkdown(b.text)}</h1>`);
        else if (b.level === 2) parts.push(`<h2 class="md-h2">${inlineMarkdown(b.text)}</h2>`);
        else parts.push(`<h3 class="md-h3">${inlineMarkdown(b.text)}</h3>`);
        break;
      case 'kv':
        parts.push(`<div class="md-field"><span class="md-label">${escapeHTML(b.label)}</span><div class="md-value">${bodyMarkdownToHTML(b.value)}</div></div>`);
        break;
      case 'list':
        parts.push(`<ul class="md-list">${b.items.map(item => `<li>${inlineMarkdown(item)}</li>`).join('')}</ul>`);
        break;
      case 'para':
        parts.push(`<p class="md-p">${inlineMarkdown(b.text)}</p>`);
        break;
    }
  }

  return { html: parts.join(''), image };
}

// ─── 卡片 Chrome（噪点 + 变质线 + SVG 滤镜）─────────────────
function cardChrome() {
  return `
    <svg aria-hidden="true" style="position:absolute;width:0;height:0">
      <filter id="card-grain-filter">
        <feTurbulence type="fractalNoise" baseFrequency="0.70" numOctaves="3" stitchTiles="stitch"/>
        <feColorMatrix type="saturate" values="0"/>
      </filter>
    </svg>
    <div class="card-grain" aria-hidden="true" style="position:absolute;inset:0;opacity:0.055;mix-blend-mode:multiply;filter:url(#card-grain-filter);pointer-events:none;z-index:1"></div>
    <svg class="card-decay" viewBox="0 0 900 1200" preserveAspectRatio="none" aria-hidden="true" style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:0">
      <path d="M180 580 Q310 568 420 595 T640 578" stroke="rgba(0,0,0,0.07)" stroke-width="0.5" fill="none"/>
      <path d="M320 560 Q440 545 510 568 T730 550" stroke="rgba(0,0,0,0.05)" stroke-width="0.7" fill="none"/>
      <path d="M140 598 Q290 588 410 605 T600 592" stroke="rgba(0,0,0,0.06)" stroke-width="0.3" fill="none"/>
      <path d="M420 572 Q500 558 570 578 T710 565" stroke="rgba(0,0,0,0.04)" stroke-width="0.6" fill="none"/>
      <path d="M250 610 Q370 600 460 612 T550 605" stroke="rgba(0,0,0,0.05)" stroke-width="0.4" fill="none"/>
    </svg>`;
}

// ─── 内容量 → 连续缩放 ─────────────────────────────────────
function textMetricsValue(value) {
  return typeof value === 'string' ? value : JSON.stringify(value || '');
}

function cardContentMetrics(cardData) {
  const entries = Object.entries(cardData || {}).filter(([key, value]) => {
    if (key === '_image' || key === '_markdown' || key === '_title') return false;
    const text = textMetricsValue(value).trim();
    return text && text !== '暂缺';
  });
  const text = entries.map(([, value]) => textMetricsValue(value)).join('\n');
  return {
    fieldCount: entries.length,
    charCount: Array.from(text).length,
    lineCount: text.split(/\n+/).filter(Boolean).length,
  };
}

function fitVarsForCard(cardIndex, cardData) {
  const metrics = cardContentMetrics(cardData);
  const totalChars = metrics.charCount;
  const totalFields = metrics.fieldCount;

  const contentW = 764;
  const contentH = 990;

  const refBody = 22;
  const refLineH = refBody * 1.52;
  const avgCharW = 12;
  const charsPerLine = Math.floor(contentW / avgCharW);
  const bodyLines = Math.ceil(totalChars / Math.max(1, charsPerLine));
  const bodyPx = bodyLines * refLineH;
  const fieldPx = totalFields * (11 + 12 * 2 + 8);
  const estimatedPx = bodyPx + fieldPx;

  let scale;
  if (cardIndex === 1) {
    scale = totalChars <= 14 ? 1.08 : totalChars <= 32 ? 0.90 : 0.74;
  } else {
    scale = contentH / Math.max(estimatedPx, contentH * 0.45);
    scale = Math.max(0.68, Math.min(1.10, scale));
  }

  const S = scale;
  const vars = {
    '--fs-hero':       Math.round(108 * S),
    '--fs-s1':         Math.round(46 * S),
    '--fs-s2':         Math.round(32 * S),
    '--fs-body':       Math.round(22 * S),
    '--fs-body-sm':    Math.round(17 * S),
    '--fs-label':      Math.round(11 * S),
    '--fs-caption':    Math.round(10 * S),
    '--fs-data':       Math.round(26 * S),
    '--fs-timeline':   Math.round(20 * S),
    '--lh-body':       S > 0.90 ? 1.56 : S > 0.78 ? 1.52 : 1.42,
    '--field-gap':     Math.round(24 * S),
    '--field-inner-gap': Math.round(8 * S),
    '--field-pad-y':   Math.round(14 * S),
    '--section-gap':   Math.round(28 * S),
  };

  const pxVars = {};
  for (const [k, v] of Object.entries(vars)) {
    pxVars[k] = k === '--lh-body' ? String(v) : v + 'px';
  }
  return pxVars;
}

function articleOpen(cardIndex, cardData) {
  const vars = fitVarsForCard(cardIndex, cardData);
  const style = Object.entries(vars).map(([k, v]) => `${k}: ${v}`).join('; ');
  return `<article class="knowledge-card" style="${style}">`;
}

// ─── 卡片2-8 通用渲染（Markdown 驱动 + 底部图框）───────────
function renderPageGeneric(cardIndex, cardData) {
  const md = cardData?._markdown || '';
  const { html, image } = fullMarkdownToHTML(md);

  // 优先级：_selectedImage（图片夹选中） > 资产图片 > markdown 图片
  let displayImage = cardData?._selectedImage || '';
  if (!displayImage) {
    const assets = cardData?._assets || {};
    const assetKey = CARD_ASSET_MAP[cardIndex];
    const asset = assetKey ? assets[assetKey] : null;
    if (asset && asset.local_path && asset.status === 'ready') {
      displayImage = asset.local_path;
    }
  }
  if (!displayImage) displayImage = image;

  return `
${articleOpen(cardIndex, cardData)}
  ${cardChrome()}
  <div class="card-content">
    <div class="card-body">${html || '<p class="md-empty">暂无内容</p>'}</div>
    ${imageBox(displayImage)}
  </div>
</article>`;
}

// ─── 卡片1 — 封面 Hero ──────────────────────────────────────
function renderPage1({ companyName, cardData }) {
  const name = val(cardData, '公司名', '') || companyName || '暂缺';
  const type = val(cardData, '类型', '');
  return `
${articleOpen(1, cardData)}
  ${cardChrome()}
  <div class="p1-hero">
    <p class="p1-tagline">三分钟认识一家AI初创公司</p>
    <h1 class="p1-title">${escapeHTML(name)}</h1>
    ${type ? `<span class="p1-type">${escapeHTML(type)}</span>` : ''}
    <div class="p1-rule"></div>
  </div>
</article>`;
}

function renderPage2({ cardData }) { return renderPageGeneric(2, cardData); }
function renderPage3({ cardData }) { return renderPageGeneric(3, cardData); }
function renderPage4({ cardData }) { return renderPageGeneric(4, cardData); }
function renderPage5({ cardData }) { return renderPageGeneric(5, cardData); }
function renderPage6({ cardData }) { return renderPageGeneric(6, cardData); }
function renderPage7({ cardData }) { return renderPageGeneric(7, cardData); }
function renderPage8({ cardData }) { return renderPageGeneric(8, cardData); }

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
  return `<article class="knowledge-card"><div class="empty-card">${escapeHTML(message || '加载失败')}</div></article>`;
}

function renderSourceIntoDocument(doc, source) {
  // 移除旧动态样式和旧卡片
  doc.querySelectorAll('style.card-dynamic').forEach(el => el.remove());
  const oldCards = doc.querySelectorAll('.knowledge-card');
  oldCards.forEach(el => el.remove());

  // 注入新样式
  const styleMatch = source.match(/<style>([\s\S]*?)<\/style>/);
  if (styleMatch) {
    const styleEl = doc.createElement('style');
    styleEl.className = 'card-dynamic';
    styleEl.textContent = styleMatch[1];
    doc.head.appendChild(styleEl);
  }

  // 注入新卡片
  const container = doc.getElementById('card-page');
  if (container) {
    container.innerHTML = source.replace(/<style>[\s\S]*?<\/style>\n?/, '');
  }
}
