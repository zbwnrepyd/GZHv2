const SourceEditor = {
  getCompanyName: () => '',
  getCurrentCard: () => 1,
  getCurrentSource: () => '',
  refreshPreview: () => {},
  setStatus: () => {},
  previewTimer: null,

  init({ getCompanyName, getCurrentCard, getCurrentSource, refreshPreview, setStatus }) {
    this.getCompanyName = getCompanyName;
    this.getCurrentCard = getCurrentCard;
    this.getCurrentSource = getCurrentSource;
    this.refreshPreview = refreshPreview;
    this.setStatus = setStatus;

    const editor = document.getElementById('source-editor');
    editor?.addEventListener('input', () => {
      this.updateHighlight();
      clearTimeout(this.previewTimer);
      this.previewTimer = setTimeout(() => this.previewEditorSource(), 160);
    });
    editor?.addEventListener('scroll', () => this.syncHighlightScroll());
    document.getElementById('btn-save-source')?.addEventListener('click', () => this.saveCurrent());
    document.getElementById('btn-reset-source')?.addEventListener('click', () => this.resetCurrent());
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

  loadCurrentSource(defaultSource) {
    const map = this.loadMap();
    return map[this.getCurrentCard()] || defaultSource || '';
  },

  setEditorValue(source) {
    const editor = document.getElementById('source-editor');
    if (editor) editor.value = source || '';
    this.updateHighlight();
  },

  saveCurrent() {
    const editor = document.getElementById('source-editor');
    const map = this.loadMap();
    map[this.getCurrentCard()] = editor?.value || '';
    this.saveMap(map);
    this.setStatus(`卡片 ${this.getCurrentCard()} 源码已保存到本机浏览器。`, 'success');
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
  },

  previewEditorSource() {
    const frame = document.getElementById('card-frame');
    const editor = document.getElementById('source-editor');
    if (!frame || !editor) return;
    this.applyToFrame(frame, editor.value);
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
