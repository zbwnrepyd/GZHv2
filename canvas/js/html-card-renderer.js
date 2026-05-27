const CARD_TITLES_HTML = {
  1: '首页',
  2: '公司介绍',
  3: '发展沿袭',
  4: '主产品',
  5: '其他产品',
  6: '商业模式',
  7: '竞争格局',
  8: '总结',
};

const CARD_NAV_BY_INDEX = {
  1: ['首页', '公司介绍', '总结'],
  2: ['首页', '公司介绍', '产品策略', '总结'],
  3: ['首页', '发展沿袭', '产品策略', '总结'],
  4: ['首页', '产品策略', '主产品', '总结'],
  5: ['首页', '产品策略', '产品线', '总结'],
  6: ['首页', '产品策略', '商业模式', '总结'],
  7: ['首页', '产品策略', '竞争格局', '总结'],
  8: ['首页', '产品策略', '竞争格局', '总结'],
};

const DEFAULT_CARD_CSS = `:root {
  --card-padding-x: 72px;
  --card-padding-y: 64px;
  --title-size: 54px;
  --title-top: 64px;
  --body-size: 28px;
  --body-line-height: 1.45;
  --image-height: 260px;
  --image-radius: 32px;
  --nav-size: 20px;
  --text-primary: #111827;
  --text-muted: #8A94A6;
  --accent: #29B8D4;
}`;

function escapeHTML(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function inlineMarkdown(value) {
  return escapeHTML(value)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>');
}

function bodyMarkdownToHTML(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  const lines = text.split('\n').map((line) => line.trim()).filter(Boolean);
  const listItems = [];
  const blocks = [];

  for (const line of lines) {
    if (/^[-*]\s+/.test(line)) {
      listItems.push(`<li>${inlineMarkdown(line.replace(/^[-*]\s+/, ''))}</li>`);
    } else {
      if (listItems.length) {
        blocks.push(`<ul>${listItems.splice(0).join('')}</ul>`);
      }
      blocks.push(`<p>${inlineMarkdown(line)}</p>`);
    }
  }
  if (listItems.length) {
    blocks.push(`<ul>${listItems.join('')}</ul>`);
  }
  return blocks.join('');
}

function cardTitle(cardIndex, cardData, companyName) {
  if (cardIndex === 1) {
    return cardData['公司名'] || companyName || cardData._title || CARD_TITLES_HTML[cardIndex];
  }
  return cardData._title || CARD_TITLES_HTML[cardIndex] || `卡片${cardIndex}`;
}

function navHTML(cardIndex) {
  const labels = CARD_NAV_BY_INDEX[cardIndex] || ['首页', CARD_TITLES_HTML[cardIndex] || `卡片${cardIndex}`, '总结'];
  const current = CARD_TITLES_HTML[cardIndex] || labels[1];
  return labels.map((label) => {
    if (label === current || (cardIndex === 4 && label === '主产品') || (cardIndex === 5 && label === '产品线')) {
      return `<strong>${escapeHTML(label)}</strong>`;
    }
    return `<span>${escapeHTML(label)}</span>`;
  }).join('');
}

function imageHTML(cardData) {
  if (cardData && cardData._image) {
    return `<img class="card-image" src="${escapeHTML(cardData._image)}" alt="">`;
  }
  return '<div class="card-image placeholder" aria-hidden="true"></div>';
}

function fieldBlocks(cardData) {
  const blocks = [];
  for (const [key, value] of Object.entries(cardData || {})) {
    if (key.startsWith('_') || !value) continue;
    if (key === '公司名') continue;
    blocks.push(`
      <div class="field-block">
        <div class="field-label">${escapeHTML(key)}</div>
        <div class="field-value">${bodyMarkdownToHTML(value)}</div>
      </div>
    `);
  }
  if (blocks.length) return blocks.join('');
  return bodyMarkdownToHTML(cardData?._body || '内容待补充。');
}

function renderKnowledgeCard({ companyName, cardIndex, cardData }) {
  const data = cardData || {};
  const title = cardTitle(cardIndex, data, companyName);
  return `
    <article class="knowledge-card card-index-${cardIndex}">
      <header class="card-nav">${navHTML(cardIndex)}</header>
      <section class="card-image-frame">${imageHTML(data)}</section>
      <h1 class="card-title">${escapeHTML(title)}</h1>
      <section class="card-body">${fieldBlocks(data)}</section>
    </article>
  `;
}

function renderCardSource({ companyName, cardIndex, cardData }) {
  return `<style>
${DEFAULT_CARD_CSS}
</style>
${renderKnowledgeCard({ companyName, cardIndex, cardData }).trim()}
`;
}

function renderEmptyCard(message) {
  return `
    <article class="knowledge-card">
      <div class="empty-card">${escapeHTML(message || '暂无卡片数据')}</div>
    </article>
  `;
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

function renderSourceIntoDocument(doc, source) {
  const targetDoc = doc || document;
  const root = targetDoc.getElementById('card-page');
  if (!root) return;
  root.innerHTML = source || renderEmptyCard('暂无卡片源码');
}
