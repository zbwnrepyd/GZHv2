const SourceEditor = {
  getCompanyName: () => '',
  getCurrentCard: () => 1,
  getCurrentSource: () => '',
  getDefaultSource: () => '',
  refreshPreview: () => {},
  setStatus: () => {},
  onTemplateSaved: null,
  previewTimer: null,
  fullSource: '',
  viewMode: 'all',
  inspectMode: false,

  init({ getCompanyName, getCurrentCard, getCurrentSource, getDefaultSource, refreshPreview, setStatus, onTemplateSaved }) {
    this.getCompanyName = getCompanyName;
    this.getCurrentCard = getCurrentCard;
    this.getCurrentSource = getCurrentSource;
    this.getDefaultSource = getDefaultSource || (() => '');
    this.refreshPreview = refreshPreview;
    this.setStatus = setStatus;
    this.onTemplateSaved = onTemplateSaved || null;

    const editor = document.getElementById('source-editor');
    editor?.addEventListener('input', () => {
      this.updateFullSourceFromEditor();
      this.updateHighlight();
      clearTimeout(this.previewTimer);
      this.previewTimer = setTimeout(() => this.previewEditorSource(), 160);
    });
    editor?.addEventListener('scroll', () => this.syncHighlightScroll());
    document.getElementById('btn-save-template')?.addEventListener('click', () => this.saveCurrent());
    document.getElementById('btn-reset-source')?.addEventListener('click', () => this.resetCurrent());
    document.getElementById('btn-source-all')?.addEventListener('click', () => this.showSection('all'));
    document.getElementById('btn-source-css')?.addEventListener('click', () => this.showSection('css'));
    document.getElementById('btn-source-html')?.addEventListener('click', () => this.showSection('html'));
    document.getElementById('btn-inspect-source')?.addEventListener('click', () => this.toggleInspect());
    this.updateViewButtons();
  },

  key(companyName) {
    return `aistartups.cardSource.${companyName || this.getCompanyName() || 'default'}`;
  },

  loadMap(companyName) {
    try {
      return JSON.parse(localStorage.getItem(this.key(companyName)) || '{}');
    } catch {
      return {};
    }
  },

  saveMap(map) {
    localStorage.setItem(this.key(), JSON.stringify(map));
  },

  signature(source) {
    const text = String(source || '');
    let hash = 0;
    for (let i = 0; i < text.length; i += 1) {
      hash = ((hash << 5) - hash + text.charCodeAt(i)) | 0;
    }
    return String(hash);
  },

  loadCurrentSource(defaultSource) {
    const map = this.loadMap();
    const saved = map[this.getCurrentCard()];
    const signature = this.signature(defaultSource);
    if (saved && typeof saved === 'object' && saved.signature === signature) {
      return saved.source || defaultSource || '';
    }
    return defaultSource || '';
  },

  /* 自动保存当前卡片源码（静默，不弹窗） */
  autoSaveCurrentCard(cardIndex) {
    const map = this.loadMap();
    const idx = cardIndex != null ? cardIndex : this.getCurrentCard();
    const source = this.getFullSource();
    if (!source) return;
    const defaultSource = this.getDefaultSource();
    map[idx] = {
      source,
      signature: this.signature(defaultSource),
    };
    this.saveMap(map);
  },

  /* 外部保存指定卡片的 source（如 inline 编辑后） */
  saveCurrentCard(cardIndex, source) {
    if (!source) return;
    const map = this.loadMap();
    const defaultSource = (typeof this.getDefaultSource === 'function') ? this.getDefaultSource() : '';
    map[cardIndex] = {
      source,
      signature: this.signature(defaultSource),
    };
    this.saveMap(map);
  },

  getFullSource() {
    this.updateFullSourceFromEditor();
    return this.fullSource || '';
  },

  setEditorValue(source) {
    this.fullSource = source || '';
    this.renderEditorView();
  },

  splitSource(source) {
    const text = String(source || '');
    const styleStart = text.indexOf('<style>');
    const styleEnd = text.indexOf('</style>');
    if (styleStart === -1 || styleEnd === -1 || styleEnd < styleStart) {
      return { prefix: '', css: '', html: text };
    }
    return {
      prefix: text.slice(0, styleStart),
      css: text.slice(styleStart + '<style>'.length, styleEnd).replace(/^\n/, '').replace(/\n$/, ''),
      html: text.slice(styleEnd + '</style>'.length).replace(/^\n/, ''),
    };
  },

  composeSource(parts) {
    if (!parts.css) return parts.html || '';
    const css = String(parts.css || '').replace(/\s+$/, '');
    const html = String(parts.html || '').replace(/^\n+/, '');
    return `${parts.prefix || ''}<style>\n${css}\n</style>\n${html}`;
  },

  updateFullSourceFromEditor() {
    const editor = document.getElementById('source-editor');
    if (!editor) return;
    if (this.viewMode === 'css') {
      const parts = this.splitSource(this.fullSource);
      parts.css = editor.value;
      this.fullSource = this.composeSource(parts);
    } else if (this.viewMode === 'html') {
      const parts = this.splitSource(this.fullSource);
      parts.html = editor.value;
      this.fullSource = this.composeSource(parts);
    } else {
      this.fullSource = editor.value || '';
    }
  },

  renderEditorView() {
    const editor = document.getElementById('source-editor');
    if (!editor) return;
    const parts = this.splitSource(this.fullSource);
    if (this.viewMode === 'css') {
      editor.value = parts.css;
    } else if (this.viewMode === 'html') {
      editor.value = parts.html;
    } else {
      editor.value = this.fullSource || '';
    }
    document.querySelector('.source-code-wrap')?.setAttribute('data-source-view', this.viewMode);
    this.updateViewButtons();
    this.updateHighlight();
  },

  showSection(mode) {
    if (!['all', 'css', 'html'].includes(mode)) return;
    this.updateFullSourceFromEditor();
    this.viewMode = mode;
    this.renderEditorView();
    const label = mode === 'css' ? 'CSS' : mode === 'html' ? 'HTML' : '全部源码';
    this.setStatus(`源码栏已切换到 ${label}。`, 'info');
  },

  updateViewButtons() {
    const map = {
      all: 'btn-source-all',
      css: 'btn-source-css',
      html: 'btn-source-html',
    };
    Object.entries(map).forEach(([mode, id]) => {
      document.getElementById(id)?.classList.toggle('active', this.viewMode === mode);
    });
    document.getElementById('btn-inspect-source')?.classList.toggle('active', this.inspectMode);
    document.querySelector('.source-code-wrap')?.classList.toggle('is-inspecting', this.inspectMode);
  },

  saveCurrent() {
    // 委托给外部 saveAllCards 处理
    if (this._saveAllCardsCallback) {
      this._saveAllCardsCallback();
    } else {
      // 兜底：只保存当前卡片
      this._saveSingleCard();
    }
  },

  _saveSingleCard() {
    const cardIndex = this.getCurrentCard();
    const templateKey = 'aistartups.templates';
    const source = this.getFullSource();
    let map;
    try { map = JSON.parse(localStorage.getItem(templateKey) || '{}'); } catch { map = {}; }
    const cardKey = String(cardIndex);
    if (!map[cardKey]) map[cardKey] = [];

    const name = prompt('模板名称：', `卡片${cardIndex}-模板${map[cardKey].length + 1}`);
    if (!name) return;

    const now = new Date();
    const createdAt = `${now.getMonth()+1}/${now.getDate()} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
    map[cardKey].push({ name: name.trim(), source, createdAt, cardIndex });

    localStorage.setItem(templateKey, JSON.stringify(map));
    this.setStatus(`模板"${name.trim()}"已保存。`, 'success');
    if (this.onTemplateSaved) this.onTemplateSaved();
  },

  setSaveAllCardsCallback(cb) {
    this._saveAllCardsCallback = cb;
  },

  resetCurrent() {
    const map = this.loadMap();
    delete map[this.getCurrentCard()];
    this.saveMap(map);
    this.setStatus(`卡片 ${this.getCurrentCard()} 源码已恢复默认。`, 'success');
    this.refreshPreview();
  },

  applyToFrame(frame, source) {
    if (!frame?.contentWindow?.document) return;
    frame.contentWindow.renderSourcePreview(source);
    this.installInspectHooks(frame);
  },

  previewEditorSource() {
    const frame = document.getElementById('card-frame');
    if (!frame) return;
    this.applyToFrame(frame, this.getFullSource());
  },

  toggleInspect() {
    this.inspectMode = !this.inspectMode;
    this.updateViewButtons();
    this.syncInspectFrame(document.getElementById('card-frame'));
    this.setStatus(this.inspectMode ? '检查模式已开启：点击画布元素跳转到源码。' : '检查模式已关闭。', 'info');
  },

  syncInspectFrame(frame) {
    const doc = frame?.contentWindow?.document;
    if (!doc?.documentElement) return;
    doc.documentElement.dataset.sourceInspecting = this.inspectMode ? 'true' : 'false';
    let style = doc.getElementById('source-inspect-style');
    if (!style) {
      style = doc.createElement('style');
      style.id = 'source-inspect-style';
      doc.head.appendChild(style);
    }
    style.textContent = `
      [data-source-inspecting="true"] .knowledge-card * { cursor: crosshair !important; }
      [data-source-inspecting="true"] .source-inspect-hover {
        outline: 2px solid #29B8D4 !important;
        outline-offset: 3px !important;
      }
    `;
  },

  installInspectHooks(frame) {
    const doc = frame?.contentWindow?.document;
    if (!doc || doc.__sourceInspectInstalled) {
      this.syncInspectFrame(frame);
      return;
    }
    doc.__sourceInspectInstalled = true;
    doc.addEventListener('mouseover', (event) => {
      if (!this.inspectMode) return;
      const target = this.pickInspectableElement(event.target);
      target?.classList?.add('source-inspect-hover');
    }, true);
    doc.addEventListener('mouseout', (event) => {
      event.target?.classList?.remove('source-inspect-hover');
    }, true);
    doc.addEventListener('click', (event) => {
      if (!this.inspectMode) return;
      event.preventDefault();
      event.stopPropagation();
      const target = this.pickInspectableElement(event.target);
      this.locateSourceForElement(target);
    }, true);
    this.syncInspectFrame(frame);
  },

  pickInspectableElement(target) {
    if (!target?.closest) return target;
    return target.closest([
      '.md-field',
      '.md-label',
      '.md-value',
      '.md-h1',
      '.md-h2',
      '.md-h3',
      '.md-list',
      '.md-p',
      '.img-box',
      '.card-body',
      '.p1-hero',
      '.p1-title',
      '.p1-type',
      '.p1-rule',
      '.p1-tagline',
      'article',
    ].join(',')) || target;
  },

  escapeRegExp(value) {
    return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  },

  classNeedles(element) {
    return Array.from(element?.classList || [])
      .filter((className) => className !== 'source-inspect-hover')
      .map((className) => ({
        className,
        pattern: new RegExp(`class="[^"]*\\b${this.escapeRegExp(className)}\\b[^"]*"`),
      }));
  },

  locateSourceForElement(element) {
    if (!element) return false;
    this.updateFullSourceFromEditor();
    const source = this.fullSource || '';
    const parts = this.splitSource(source);
    const htmlStart = source.length - parts.html.length;
    const html = parts.html;

    if (element.id) {
      const idNeedle = `id="${element.id}"`;
      const idIndex = html.indexOf(idNeedle);
      if (idIndex >= 0) return this.jumpToSource(htmlStart + idIndex, idNeedle.length);
    }

    const text = String(element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 32);
    if (text) {
      const textIndex = html.indexOf(text);
      if (textIndex >= 0) return this.jumpToSource(htmlStart + textIndex, text.length);
    }

    for (const { pattern } of this.classNeedles(element)) {
      const match = pattern.exec(html);
      if (match) return this.jumpToSource(htmlStart + match.index, match[0].length);
    }

    const tagNeedle = `<${String(element.tagName || '').toLowerCase()}`;
    const tagIndex = html.indexOf(tagNeedle);
    if (tagIndex >= 0) return this.jumpToSource(htmlStart + tagIndex, tagNeedle.length);

    this.setStatus('没有在源码中定位到这个元素。', 'error');
    return false;
  },

  jumpToSource(start, length = 1) {
    this.viewMode = 'all';
    this.renderEditorView();
    const editor = document.getElementById('source-editor');
    if (!editor) return false;
    const safeStart = Math.max(0, Math.min(start, editor.value.length));
    const safeEnd = Math.max(safeStart, Math.min(safeStart + length, editor.value.length));
    editor.focus();
    editor.setSelectionRange(safeStart, safeEnd);
    const line = editor.value.slice(0, safeStart).split('\n').length;
    const lineHeight = parseFloat(getComputedStyle(editor).lineHeight) || 18;
    editor.scrollTop = Math.max(0, (line - 8) * lineHeight);
    editor.scrollLeft = 0;
    this.syncHighlightScroll();
    this.setStatus('已跳转到对应源码。', 'success');
    return true;
  },

  escapeSource(source) {
    return String(source || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  },

  stash(html, pattern, render) {
    const tokens = [];
    const output = html.replace(pattern, (...args) => {
      const token = `@@SOURCE_TOKEN_${tokens.length}@@`;
      tokens.push(render(...args));
      return token;
    });
    return { output, tokens };
  },

  restore(html, tokens) {
    return tokens.reduce((result, value, index) => {
      return result.replace(`@@SOURCE_TOKEN_${index}@@`, value);
    }, html);
  },

  highlightTag(tagText) {
    return tagText.replace(/^(&lt;\/?)([a-zA-Z][\w:-]*)([\s\S]*?)(&gt;)$/, (_, open, tagName, attrs, close) => {
      const highlightedAttrs = attrs.replace(/([\w:-]+)(=)(&quot;.*?&quot;|&#039;.*?&#039;|[^\s]+)/g, (_attr, name, eq, value) => {
        return `<span class="tok-attr">${name}</span><span class="tok-punct">${eq}</span><span class="tok-string">${value}</span>`;
      });
      return `<span class="tok-punct">${open}</span><span class="tok-tag">${tagName}</span>${highlightedAttrs}<span class="tok-punct">${close}</span>`;
    });
  },

  highlightCSS(html) {
    return html
      .replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="tok-comment">$1</span>')
      .replace(/(\.[a-zA-Z_-][\w-]*|#[a-zA-Z_-][\w-]*)/g, '<span class="tok-selector">$1</span>')
      .replace(/(--[\w-]+)/g, '<span class="tok-var">$1</span>')
      .replace(/\b([a-zA-Z-]+)(\s*:)/g, '<span class="tok-prop">$1</span>$2')
      .replace(/(#[0-9a-fA-F]{3,8})\b/g, '<span class="tok-number">$1</span>')
      .replace(/\b(\d+(?:\.\d+)?(?:px|rem|em|%|vh|vw)?)\b/g, '<span class="tok-number">$1</span>');
  },

  highlightSource(source) {
    let html = this.escapeSource(source);
    const comments = this.stash(html, /(&lt;!--[\s\S]*?--&gt;)/g, (match) => `<span class="tok-comment">${match}</span>`);
    html = comments.output;
    const tags = this.stash(html, /(&lt;\/?[a-zA-Z][\w:-]*(?:\s+[\s\S]*?)?&gt;)/g, (match) => this.highlightTag(match));
    html = this.highlightCSS(tags.output);
    html = this.restore(html, tags.tokens);
    html = this.restore(html, comments.tokens);
    return html;
  },

  updateHighlight() {
    const editor = document.getElementById('source-editor');
    const highlight = document.getElementById('source-highlight');
    if (!editor || !highlight) return;
    highlight.innerHTML = this.highlightSource(editor.value) + '\n';
    this.syncHighlightScroll();
  },

  syncHighlightScroll() {
    const editor = document.getElementById('source-editor');
    const highlight = document.getElementById('source-highlight');
    if (!editor || !highlight) return;
    highlight.scrollTop = editor.scrollTop;
    highlight.scrollLeft = editor.scrollLeft;
  },
};
