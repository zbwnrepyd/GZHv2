# GZHv2 Canvas 排版改造技术文档

> 目标：将 canvas 层的默认卡片样式改为参考图所示排版——顶部页签导航、大字标题居中、背景图水印、内容区字段列表，全部通过修改 `html-card-renderer.js` 和 `card.html` 实现，不动 Flask 后端和数据库。

---

## 一、排版解构

根据参考图，8 张卡片共享同一套视觉语言，差异仅在内容区。

### 1.1 通用结构（900 × 1200px）

```
┌─────────────────────────────────────┐  ← 卡片外框 900×1200
│  page N           [顶部页码]         │  ← 行1：左上角页码标签（浅灰色小字）
│  公司介绍 ｜ 产品线 ｜ 商业模式 ｜…  │  ← 行2：面包屑导航，当前项加粗
│                                     │
│         [内容区 - 每张不同]          │  ← 主体：居中或左对齐文字内容
│                                     │
│  [背景水印：公司名大字，极淡]        │  ← 绝对定位，底层，透明度约 5%
└─────────────────────────────────────┘
```

### 1.2 各页内容区字段映射

| 页 | 标题文字 | 内容字段（来自 final_db） |
|---|---|---|
| page1 | 公司名（大字加粗） | company_type；副标题"三分钟认识一家AI初创公司" |
| page2 | 公司介绍 | 在哪里、干什么；团队情况；投融资情况 |
| page3 | 发展沿袭 | timeline_events（时间线列表） |
| page4 | 产品1 | main_product_name；主要功能；竞争优势 |
| page5 | 产品2 | other_products 第一项；主要功能；竞争优势 |
| page6 | 商业模式 | 盈利方式；冷启动与增长策略；GTM；客户群体 |
| page7 | 竞争格局 | 总结；优势是什么；现在赛道大环境是什么样的 |
| page8 | 总结 | 这个栏目足干嘛的；关注我 |

### 1.3 视觉 Token

```css
/* 来自参考图观察 + 项目已有 token */
--accent:        #29B8D4;   /* 青色，项目已有 */
--navy:          #1B2A4A;   /* 深蓝，项目已有 */
--text-primary:  #111827;
--text-muted:    #8A94A6;
--bg-card:       #FFFFFF;
--bg-outer:      #F2F3F5;

/* 参考图尺寸观察 */
--page-label-size: 18px;    /* "page N" 左上角 */
--nav-size:        17px;    /* 面包屑导航 */
--card-padding-x:  72px;
--card-padding-y:  56px;
--title-size:      52px;    /* 内容标题 */
--body-size:       26px;
--watermark-opacity: 0.05;  /* 背景水印 */
```

---

## 二、改造文件清单

只需修改 3 个文件，新增 1 个文件：

```
canvas/
  card.html                   ← 修改：引入背景图支持、全局 CSS 变量
  js/
    html-card-renderer.js     ← 主要修改：重写所有 render 函数
    bg-loader.js              ← 新增：背景图注入工具
```

---

## 三、`bg-loader.js`（新增）

背景图存在本地，不上传服务器。通过 `localStorage` 记住路径，Puppeteer 导出时通过 `--bg-image` 参数注入。

```js
// canvas/js/bg-loader.js
// 背景图管理：支持三种来源
// 1. URL 参数 ?bg=<base64 data URL>（Puppeteer 注入）
// 2. localStorage 缓存的 base64
// 3. 用户在制作台手动上传

const BgLoader = (() => {
  const STORAGE_KEY = 'aistartups_bg_image';

  function applyBg(dataUrl) {
    // 写入所有 .knowledge-card 元素的伪元素背景
    let style = document.getElementById('__bg_style');
    if (!style) {
      style = document.createElement('style');
      style.id = '__bg_style';
      document.head.appendChild(style);
    }
    style.textContent = `
      .knowledge-card {
        position: relative;
      }
      .knowledge-card::before {
        content: '';
        position: absolute;
        inset: 0;
        background-image: url('${dataUrl}');
        background-size: cover;
        background-position: center;
        opacity: var(--watermark-opacity, 0.05);
        pointer-events: none;
        z-index: 0;
      }
      .knowledge-card > * {
        position: relative;
        z-index: 1;
      }
    `;
  }

  function init() {
    // 优先：URL 参数（Puppeteer 场景）
    const params = new URLSearchParams(window.location.search);
    const bgParam = params.get('bg');
    if (bgParam) {
      applyBg(decodeURIComponent(bgParam));
      localStorage.setItem(STORAGE_KEY, decodeURIComponent(bgParam));
      return;
    }
    // 其次：localStorage 缓存
    const cached = localStorage.getItem(STORAGE_KEY);
    if (cached) {
      applyBg(cached);
    }
  }

  // 供制作台"上传背景图"按钮调用
  function loadFromFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const dataUrl = e.target.result;
        localStorage.setItem(STORAGE_KEY, dataUrl);
        applyBg(dataUrl);
        resolve(dataUrl);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function clear() {
    localStorage.removeItem(STORAGE_KEY);
    const style = document.getElementById('__bg_style');
    if (style) style.textContent = '';
  }

  return { init, loadFromFile, clear };
})();
```

---

## 四、`html-card-renderer.js`（重写）

完整替换现有文件。核心变化：

- `navHTML()` 改为参考图的 `公司介绍 ｜ 产品线 ｜ 商业模式 ｜ 竞争优势` 格式，当前页加粗
- 每张卡片用独立的 `renderCard_N()` 函数，精确控制字段顺序
- 背景水印通过 `BgLoader` 注入，不硬编码图片路径
- `DEFAULT_CARD_CSS` 加入完整变量集

```js
// canvas/js/html-card-renderer.js  （完整替换）

// ─── 常量 ───────────────────────────────────────────────────────
const CARD_TITLES_HTML = {
  1: '首页', 2: '公司介绍', 3: '发展沿袭',
  4: '主产品', 5: '其他产品', 6: '商业模式',
  7: '竞争格局', 8: '总结',
};

// 参考图：导航项固定为这 4 个章节，page1 无导航
const NAV_SECTIONS = ['公司介绍', '产品线', '商业模式', '竞争优势'];

// 各卡片对应的"当前导航项"（加粗）
const CARD_NAV_ACTIVE = {
  1: null,          // page1 无导航
  2: '公司介绍',
  3: '公司介绍',
  4: '产品线',
  5: '产品线',
  6: '商业模式',
  7: '竞争优势',
  8: '竞争优势',
};

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

// ─── 工具函数 ────────────────────────────────────────────────────
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

// ─── 导航栏 ──────────────────────────────────────────────────────
// 参考图格式：公司介绍 ｜ 产品线 ｜ 商业模式 ｜ 竞争优势
// page1 没有导航；其余页当前章节加粗
function navHTML(cardIndex) {
  if (cardIndex === 1) return '';
  const active = CARD_NAV_ACTIVE[cardIndex];
  return NAV_SECTIONS.map((sec, i) => {
    const label = sec === active
      ? `<strong>${escapeHTML(sec)}</strong>`
      : `<span>${escapeHTML(sec)}</span>`;
    return i < NAV_SECTIONS.length - 1
      ? label + '<span class="nav-sep">｜</span>'
      : label;
  }).join('');
}

// ─── 各页卡片 HTML ───────────────────────────────────────────────

function renderPage1({ companyName, cardData }) {
  const name = companyName || val(cardData, '公司名');
  const type = val(cardData, 'company_type', '');
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

function renderPage2({ companyName, cardIndex, cardData }) {
  return `
<article class="knowledge-card card-index-2">
  <p class="page-label">page 2</p>
  <nav class="card-nav">${navHTML(2)}</nav>
  <div class="card-content">
    <div class="field-row">
      <span class="field-label">在哪里、干什么</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, 'location') + ' — ' + val(cardData, 'company_def'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">团队情况</span>
      <div class="field-value">${bodyMarkdownToHTML(
        `**${val(cardData, 'founder_name')}**（${val(cardData, 'founder_edu')}）\n` +
        `${val(cardData, 'founder_bg')}\n` +
        `团队规模：${val(cardData, 'team_size')} · ${val(cardData, 'team_highlight')}`
      )}</div>
    </div>
    <div class="field-row">
      <span class="field-label">投融资情况</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, 'funding_info'))}</div>
    </div>
  </div>
</article>`;
}

function renderPage3({ companyName, cardIndex, cardData }) {
  const timeline = cardData?.timeline_events || val(cardData, 'timeline_events', '');
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
    timelineHTML = `<li>${bodyMarkdownToHTML(String(timeline))}</li>`;
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

function renderPage4({ companyName, cardIndex, cardData }) {
  return `
<article class="knowledge-card card-index-4">
  <p class="page-label">page 4</p>
  <nav class="card-nav">${navHTML(4)}</nav>
  <div class="card-content">
    <h2 class="card-section-title">${escapeHTML(val(cardData, 'main_product_name', '产品1'))}</h2>
    <div class="field-row">
      <span class="field-label">主要功能</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, 'main_product_def') + '\n' + val(cardData, 'main_product_highlight'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">竞争优势</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, 'main_product_achievement'))}</div>
    </div>
  </div>
</article>`;
}

function renderPage5({ companyName, cardIndex, cardData }) {
  let products = [];
  try {
    const raw = cardData?.other_products;
    products = typeof raw === 'string' ? JSON.parse(raw) : (raw || []);
  } catch { products = []; }
  const first = products[0] || {};
  return `
<article class="knowledge-card card-index-5">
  <p class="page-label">page 5</p>
  <nav class="card-nav">${navHTML(5)}</nav>
  <div class="card-content">
    <h2 class="card-section-title">${escapeHTML(first.name || '产品2')}</h2>
    <div class="field-row">
      <span class="field-label">主要功能</span>
      <div class="field-value">${bodyMarkdownToHTML(first.def || '暂缺')}</div>
    </div>
    <div class="field-row">
      <span class="field-label">竞争优势</span>
      <div class="field-value">${bodyMarkdownToHTML(first.highlight || '暂缺')}</div>
    </div>
  </div>
</article>`;
}

function renderPage6({ companyName, cardIndex, cardData }) {
  return `
<article class="knowledge-card card-index-6">
  <p class="page-label">page 6</p>
  <nav class="card-nav">${navHTML(6)}</nav>
  <div class="card-content">
    <div class="field-row">
      <span class="field-label">盈利方式</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, 'revenue_model'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">冷启动与增长策略</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, 'cold_start') + '\n' + val(cardData, 'gtm_strategy'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">GTM</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, 'growth_flywheel'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">客户群体</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, 'customer_segment'))}</div>
    </div>
  </div>
</article>`;
}

function renderPage7({ companyName, cardIndex, cardData }) {
  let competitors = [];
  try {
    const raw = cardData?.competitors;
    competitors = typeof raw === 'string' ? JSON.parse(raw) : (raw || []);
  } catch { competitors = []; }
  const competitorHTML = competitors.map((c, i) =>
    `<li><strong>TOP${i + 1} ${escapeHTML(c.name || '')}：</strong>${inlineMarkdown(c.product || '')}（${escapeHTML(c.data || '')}）</li>`
  ).join('') || '<li>暂缺</li>';
  return `
<article class="knowledge-card card-index-7">
  <p class="page-label">page 7</p>
  <nav class="card-nav">${navHTML(7)}</nav>
  <div class="card-content">
    <div class="field-row">
      <span class="field-label">总结</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, 'moat'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">优势是什么</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, 'moat'))}</div>
    </div>
    <div class="field-row">
      <span class="field-label">现在赛道大环境是什么样的</span>
      <div class="field-value"><ul class="competitor-list">${competitorHTML}</ul></div>
    </div>
  </div>
</article>`;
}

function renderPage8({ companyName, cardIndex, cardData }) {
  return `
<article class="knowledge-card card-index-8">
  <p class="page-label">page 8</p>
  <nav class="card-nav">${navHTML(8)}</nav>
  <div class="card-content">
    <div class="field-row">
      <span class="field-label">这个栏目是干嘛的</span>
      <div class="field-value">${bodyMarkdownToHTML(val(cardData, 'market_opportunity'))}</div>
    </div>
    <div class="p8-follow">
      <p>最伟大的公司，阿巴阿巴爸爸吧</p>
      <p class="p8-cta">关注我</p>
    </div>
  </div>
</article>`;
}

// ─── 主路由函数（供外部调用）────────────────────────────────────
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
```

---

## 五、`card.html`（修改部分）

在 `<style>` 区段追加以下样式，替换原有 `.card-nav`、`.card-body` 等定义。

```html
<!-- card.html <style> 区段：替换旧样式，追加新样式 -->
<style>
/* ── 全局重置 ── */
*, *::before, *::after { box-sizing: border-box; }
html, body {
  margin: 0; width: 100%; height: 100%;
  background: #F2F3F5;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
}
body { display: grid; place-items: center; overflow: hidden; }

/* ── 卡片容器 ── */
#card-page {
  width: 900px; height: 1200px;
  transform-origin: center center;
}
.knowledge-card {
  width: 900px; height: 1200px;
  padding: 56px 72px;
  background: #FFFFFF;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 0;
  position: relative; /* 背景水印定位基准 */
}

/* ── 页码标签 ── */
.page-label {
  margin: 0 0 8px;
  font-size: 18px;
  color: #C0C8D4;
  font-weight: 400;
  letter-spacing: 0.02em;
}

/* ── 导航（面包屑）── */
.card-nav {
  display: flex;
  align-items: center;
  gap: 0;
  font-size: 17px;
  color: #9CA3AF;
  margin-bottom: 40px;
  flex-wrap: nowrap;
  white-space: nowrap;
}
.card-nav strong {
  color: #111827;
  font-weight: 700;
}
.nav-sep {
  margin: 0 6px;
  color: #D1D5DB;
}

/* ── 内容区 ── */
.card-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

/* ── 字段行 ── */
.field-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field-label {
  font-size: 18px;
  color: #9CA3AF;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.field-value {
  font-size: 26px;
  line-height: 1.5;
  color: #374151;
}
.field-value p { margin: 0; }
.field-value ul {
  margin: 0;
  padding-left: 1.2em;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.field-value strong { color: #111827; font-weight: 700; }

/* ── 章节标题（page 3/4/5）── */
.card-section-title {
  margin: 0 0 4px;
  font-size: 36px;
  font-weight: 800;
  color: #111827;
  line-height: 1.1;
}

/* ── 时间线（page 3）── */
.timeline-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.timeline-list li {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 24px;
  line-height: 1.4;
}
.tl-date {
  color: #29B8D4;
  font-weight: 700;
  white-space: nowrap;
}
.tl-event { color: #111827; font-weight: 600; }
.tl-impact { color: #6B7280; font-style: italic; }

/* ── 竞品列表（page 7）── */
.competitor-list {
  margin: 0; padding: 0; list-style: none;
  display: flex; flex-direction: column; gap: 14px;
}
.competitor-list li { font-size: 24px; line-height: 1.4; color: #374151; }

/* ── Page 1 专属 ── */
.p1-layout {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 20px;
}
.p1-tagline {
  margin: 0;
  font-size: 20px;
  color: #9CA3AF;
}
.p1-title {
  margin: 0;
  font-size: 80px;
  font-weight: 900;
  color: #111827;
  line-height: 1.05;
  letter-spacing: -0.02em;
}
.p1-logo-placeholder {
  width: 120px; height: 120px;
  border-radius: 24px;
  background: #F3F4F6;
  border: 1px solid #E5E7EB;
}
.p1-type {
  margin: 0;
  font-size: 22px;
  color: #6B7280;
}

/* ── Page 8 专属 ── */
.p8-follow {
  margin-top: auto;
  font-size: 24px;
  color: #9CA3AF;
  line-height: 1.6;
}
.p8-cta {
  margin: 8px 0 0;
  font-size: 28px;
  font-weight: 700;
  color: #29B8D4;
}

/* ── 空卡片 ── */
.empty-card {
  height: 100%;
  display: grid;
  place-items: center;
  color: #9CA3AF;
  font-size: 28px;
}
</style>
```

在 `</body>` 前，在现有 `<script>` 标签之前插入：

```html
<script src="/canvas/js/bg-loader.js"></script>
```

在 `DOMContentLoaded` 的最后调用：

```js
BgLoader.init();
```

---

## 六、制作台背景图上传控件

在 `canvas/card-renderer.html` 的底部提示栏区域，添加背景图上传入口：

```html
<!-- 在 prompt-bar 区域追加 -->
<div class="bg-upload-bar">
  <label class="bg-upload-label">
    背景图（水印）
    <input type="file" accept="image/*" id="bg-file-input" style="display:none">
    <button type="button" onclick="document.getElementById('bg-file-input').click()">
      选择本地图片
    </button>
  </label>
  <button type="button" onclick="BgLoader.clear(); location.reload()">清除背景</button>
</div>
<script>
document.getElementById('bg-file-input').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  await BgLoader.loadFromFile(file);
  // 重新渲染当前卡片
  if (window.reloadCurrentCard) window.reloadCurrentCard();
});
</script>
```

---

## 七、Puppeteer 导出时注入背景图

修改 `canvas/screenshot.js`，支持 `--bg-image` 参数：

```js
// 在 screenshot.js 的 argv 解析区域追加
const bgImagePath = args['--bg-image'] || args['-b'] || null;

// 在 page.goto() 之前，构造 URL 时附加 bg 参数
async function buildCardUrl(baseUrl, company, cardIndex) {
  let url = `${baseUrl}/canvas/card/${encodeURIComponent(company)}/${cardIndex}`;
  if (bgImagePath) {
    const fs = require('fs');
    const mime = bgImagePath.endsWith('.png') ? 'image/png' : 'image/jpeg';
    const b64 = fs.readFileSync(bgImagePath).toString('base64');
    const dataUrl = `data:${mime};base64,${b64}`;
    url += `?bg=${encodeURIComponent(dataUrl)}`;
  }
  return url;
}
```

用法：

```bash
node canvas/screenshot.js \
  --company Anthropic \
  --base-url http://127.0.0.1:5050 \
  --bg-image /Users/你/Desktop/watermark.png \
  --out output/cards/Anthropic
```

---

## 八、`markdown_builder.py` 字段对齐

参考图 page7 的字段标签（"总结"、"优势是什么"、"现在赛道大环境是什么样的"）与现有 `moat` / `competitors` / `market_opportunity` 字段的映射：

| 参考图标签 | final_db 字段 |
|---|---|
| 总结 | `moat`（壁垒总结） |
| 优势是什么 | `moat` |
| 现在赛道大环境是什么样的 | `competitors` + `market_opportunity` |

无需改 schema，仅 `html-card-renderer.js` 层做映射即可。

---

## 九、改动文件汇总

| 文件 | 改动类型 | 改动说明 |
|---|---|---|
| `canvas/js/html-card-renderer.js` | 重写 | 新增 8 个 `renderPage_N()` 函数，重写导航、CSS 变量 |
| `canvas/card.html` | 修改 | 替换 `<style>` 为新排版 CSS；引入 `bg-loader.js` |
| `canvas/js/bg-loader.js` | 新增 | 背景图 base64 注入工具 |
| `canvas/card-renderer.html` | 修改 | 追加背景图上传控件 |
| `canvas/screenshot.js` | 修改 | 追加 `--bg-image` 参数，URL 注入 base64 |

**不需要改动的文件：**

- `webapp/` 全部后端（Flask、pipeline、db）
- `db/` schema（字段不变）
- `prompts/` 全部 Prompt
- `webapp/markdown_builder.py`（字段映射在前端做）

---

## 十、验证步骤

```bash
# 1. 启动服务
cd webapp && python3 app.py

# 2. 浏览器打开制作台，确认 page1 显示大字标题
open "http://127.0.0.1:5050/canvas/?company=Anthropic"

# 3. 上传本地背景图，确认水印显示

# 4. 切换到 page2-8，确认导航栏、字段标签正确

# 5. 批量导出（带背景图）
node canvas/screenshot.js \
  --company Anthropic \
  --base-url http://127.0.0.1:5050 \
  --bg-image /path/to/watermark.png \
  --out output/Anthropic
```

---

## 附：背景图推荐规格

| 项目 | 建议值 |
|---|---|
| 尺寸 | 900 × 1200 px（与卡片同尺寸）或更大（会自动 cover） |
| 格式 | PNG（透明通道）或 JPEG |
| 内容 | 公司名/logo 大字，纯色或低对比度 |
| 不透明度 | 原图不透明；CSS `--watermark-opacity: 0.05` 控制叠加强度 |
| 文件大小 | < 500KB（base64 注入时 URL 较长，Puppeteer 可接受） |
