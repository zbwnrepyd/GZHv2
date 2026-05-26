const CARD_TITLES = {
  1: '首页',
  2: '公司介绍',
  3: '发展沿袭',
  4: '主产品',
  5: '其他产品',
  6: '商业模式',
  7: '总结',
};

const VERSION_LABELS = {
  standard: '标准版',
  business: '商业版',
  spread: '传播版',
};

const VERSIONS = ['standard', 'business', 'spread'];

const EditorApp = {
  companyName: '',
  currentCard: 1,
  currentMode: 'card',
  versionChoices: {},
  hookChoices: {},
  finalLinesByCard: {},
  dirtyCards: new Set(),
  previewTimer: null,

  async init() {
    this.companyName = new URLSearchParams(window.location.search).get('company') || '';
    this.bindEvents();
    if (!this.companyName) {
      this.setMeta('请从研究台选择公司进入定稿');
      this.setPreview('');
      return;
    }

    document.getElementById('editor-company-label').textContent = `定稿台 · ${this.companyName}`;
    document.getElementById('btn-go-canvas').href = `/canvas/?company=${encodeURIComponent(this.companyName)}`;
    await this.loadStatus();
    await this.loadHookChoices();
    await this.loadCard(1);
  },

  bindEvents() {
    document.querySelectorAll('.editor-card-btn').forEach((button) => {
      button.addEventListener('click', async () => {
        const card = button.dataset.card;
        if (card === 'hook') {
          await this.showHooks();
        } else {
          await this.loadCard(Number(card));
        }
      });
    });

    const grid = document.getElementById('line-choice-grid');
    grid.addEventListener('click', (event) => {
      const option = event.target.closest('.line-option');
      if (option) {
        this.applyLineChoice(Number(option.dataset.row), option.dataset.version);
      }
    });
    grid.addEventListener('input', (event) => {
      const input = event.target.closest('.final-line-input');
      if (!input) return;
      this.ensureFinalLines();
      this.finalLinesByCard[this.currentCard][Number(input.dataset.row)] = input.value;
      this.markDirty();
      this.schedulePreview();
      this.updateLineStates();
    });

    document.getElementById('btn-prev').addEventListener('click', () => {
      if (this.currentCard > 1) this.loadCard(this.currentCard - 1);
    });
    document.getElementById('btn-next').addEventListener('click', () => {
      if (this.currentCard < 7) this.loadCard(this.currentCard + 1);
    });
    document.getElementById('btn-confirm').addEventListener('click', () => this.confirmCurrentCard());
  },

  async loadStatus() {
    try {
      const status = await API.getFinalStatus(this.companyName);
      ConfirmManager.setConfirmed(status.confirmed || []);
      this.updateGoCanvas();
    } catch {
      ConfirmManager.setConfirmed([]);
    }
  },

  async loadCard(cardIndex) {
    if (!this.companyName) return;
    this.currentMode = 'card';
    this.currentCard = cardIndex;
    this.updateNav();
    this.showCardMode();
    await this.loadVersionChoices(cardIndex);
    this.ensureFinalLines();
    this.renderLineChoices();
    this.updateMeta();
    this.setPreview(this.getFinalMarkdown());
    this.updateButtons();
  },

  async showHooks() {
    if (!this.companyName) return;
    this.currentMode = 'hook';
    this.updateNav();
    this.showHookMode();
    await this.loadHookChoices();
    this.renderHookContent();
    this.updateButtons();
  },

  showCardMode() {
    document.getElementById('preview-toolbar-label').textContent = '实时预览';
    document.getElementById('preview-status').classList.remove('hidden');
    document.getElementById('btn-confirm').classList.remove('hidden');
    document.getElementById('version-compare').classList.remove('hidden');
    document.querySelector('.markdown-toolbar').classList.remove('hidden');
    document.querySelector('.markdown-footer').classList.remove('hidden');
    document.getElementById('preview-render').classList.remove('hidden');
    document.getElementById('hook-render').classList.add('hidden');
  },

  showHookMode() {
    document.getElementById('version-compare').classList.add('hidden');
    document.querySelector('.markdown-toolbar').classList.add('hidden');
    document.querySelector('.markdown-footer').classList.add('hidden');
    document.getElementById('preview-render').classList.add('hidden');
    document.getElementById('preview-status').classList.add('hidden');
    document.getElementById('btn-confirm').classList.add('hidden');
    document.getElementById('hook-render').classList.remove('hidden');
    document.getElementById('preview-toolbar-label').textContent = '传播钩子文案';
  },

  renderHookContent() {
    const container = document.getElementById('hook-render');
    const parts = ['<div class="hook-display">'];
    const hasHooks = VERSIONS.some((version) => this.getHookParagraphs(version).length);

    if (!hasHooks) {
      parts.push('<p class="hook-empty">暂无钩子文案</p>');
    } else {
      for (const version of VERSIONS) {
        const hooks = this.getHookParagraphs(version);
        parts.push(`<section class="hook-display-column"><h3>${VERSION_LABELS[version]}</h3>`);
        if (hooks.length) {
          hooks.forEach((text, index) => {
            parts.push(`<div class="hook-display-item"><strong>钩子${index + 1}</strong><p>${this.esc(text)}</p></div>`);
          });
        } else {
          parts.push('<p class="hook-empty">暂无</p>');
        }
        parts.push('</section>');
      }
    }
    parts.push('</div>');

    container.innerHTML = parts.join('');
    container.classList.remove('confirmed-preview');
  },

  async loadVersionChoices(cardIndex) {
    this.versionChoices[cardIndex] = this.versionChoices[cardIndex] || {};
    await Promise.all(VERSIONS.map(async (version) => {
      if (this.versionChoices[cardIndex][version] !== undefined) return;
      try {
        const result = await API.getResearchCard(this.companyName, cardIndex, version);
        this.versionChoices[cardIndex][version] = result.markdown || '';
      } catch {
        this.versionChoices[cardIndex][version] = `## 卡片${cardIndex}：${CARD_TITLES[cardIndex]}\n\n暂缺`;
      }
    }));
  },

  async loadHookChoices() {
    await Promise.all(VERSIONS.map(async (version) => {
      if (this.hookChoices[version] !== undefined) return;
      try {
        const result = await API.getResearch(this.companyName, version);
        this.hookChoices[version] = [
          result.hook_paragraph_1 || '',
          result.hook_paragraph_2 || '',
          result.hook_paragraph_3 || '',
        ];
      } catch {
        this.hookChoices[version] = [];
      }
    }));
  },

  renderLineChoices() {
    const grid = document.getElementById('line-choice-grid');
    const finalLines = this.ensureFinalLines();
    const parts = [];

    for (const row of this.getRenderableRows()) {
      parts.push(`<div class="line-choice-row" data-row="${row}">`);
      for (const version of VERSIONS) {
        const value = this.getVersionLine(version, row);
        parts.push(
          `<button class="line-option" data-row="${row}" data-version="${version}" title="采用${VERSION_LABELS[version]}这一行">${this.displayLine(value)}</button>`
        );
      }
      parts.push(
        `<textarea class="final-line-input" data-row="${row}" rows="1">${this.esc(finalLines[row] || '')}</textarea>`
      );
      parts.push('</div>');
    }

    grid.innerHTML = parts.join('');
    grid.querySelectorAll('.final-line-input').forEach((input) => {
      this.autoGrow(input);
      input.addEventListener('input', () => this.autoGrow(input));
    });
    this.updateLineStates();
  },

  getHookParagraphs(version) {
    return (this.hookChoices[version] || []).filter((text) => String(text || '').trim());
  },

  applyLineChoice(row, version) {
    this.ensureFinalLines();
    const value = this.getVersionLine(version, row);
    this.finalLinesByCard[this.currentCard][row] = value;
    const input = document.querySelector(`.final-line-input[data-row="${row}"]`);
    if (input) {
      input.value = value;
      this.autoGrow(input);
    }
    this.markDirty();
    this.setPreview(this.getFinalMarkdown());
    this.updateLineStates();
  },

  getFinalMarkdown() {
    const lines = this.ensureFinalLines();
    return this.getRenderableRows()
      .map((row) => lines[row] || '')
      .join('\n')
      .replace(/\s+$/g, '') + '\n';
  },

  ensureFinalLines() {
    if (!this.finalLinesByCard[this.currentCard]) {
      const standard = this.versionChoices[this.currentCard]?.standard || '';
      this.finalLinesByCard[this.currentCard] = this.splitMarkdownLines(standard);
      this.padFinalLines();
    }
    return this.finalLinesByCard[this.currentCard];
  },

  padFinalLines() {
    const lines = this.finalLinesByCard[this.currentCard];
    const rows = this.getRowCount();
    while (lines.length < rows) lines.push('');
  },

  getRowCount() {
    const choices = this.versionChoices[this.currentCard] || {};
    return Math.max(...VERSIONS.map((version) => this.splitMarkdownLines(choices[version] || '').length), 1);
  },

  getRenderableRows() {
    const finalLines = this.finalLinesByCard[this.currentCard] || [];
    const rows = [];
    for (let row = 0; row < this.getRowCount(); row++) {
      if (!this.isEmptyChoiceRow(row, finalLines)) {
        rows.push(row);
      }
    }
    return rows;
  },

  isEmptyChoiceRow(row, finalLines) {
    const allVersionsEmpty = VERSIONS.every((version) => !this.getVersionLine(version, row).trim());
    const finalEmpty = !String(finalLines[row] || '').trim();
    return allVersionsEmpty && finalEmpty;
  },

  getVersionLine(version, row) {
    return this.splitMarkdownLines(this.versionChoices[this.currentCard]?.[version] || '')[row] || '';
  },

  splitMarkdownLines(markdown) {
    return String(markdown || '').replace(/\r\n/g, '\n').split('\n');
  },

  markDirty() {
    this.dirtyCards.add(this.currentCard);
    this.updateMeta();
  },

  schedulePreview() {
    clearTimeout(this.previewTimer);
    this.previewTimer = setTimeout(() => this.setPreview(this.getFinalMarkdown()), 150);
  },

  async confirmCurrentCard() {
    if (!this.companyName) return;
    const markdown_content = this.getFinalMarkdown();
    await API.saveFinalMarkdown(this.companyName, this.currentCard, markdown_content);
    ConfirmManager.confirm(this.currentCard);
    this.dirtyCards.delete(this.currentCard);
    this.updateMeta();
    this.updateGoCanvas();

    if (!ConfirmManager.allConfirmed()) {
      const next = this.nextUnconfirmed();
      if (next) await this.loadCard(next);
    }
  },

  nextUnconfirmed() {
    for (let i = this.currentCard + 1; i <= 7; i++) {
      if (!ConfirmManager.isConfirmed(i)) return i;
    }
    for (let i = 1; i <= 7; i++) {
      if (!ConfirmManager.isConfirmed(i)) return i;
    }
    return null;
  },

  updateNav() {
    document.querySelectorAll('.editor-card-btn').forEach((button) => {
      const card = button.dataset.card;
      if (this.currentMode === 'hook') {
        button.classList.toggle('active', card === 'hook');
      } else {
        button.classList.toggle('active', Number(card) === this.currentCard);
      }
    });
  },

  updateButtons() {
    if (this.currentMode === 'hook') {
      document.getElementById('btn-prev').disabled = true;
      document.getElementById('btn-next').disabled = true;
      return;
    }
    document.getElementById('btn-prev').disabled = this.currentCard <= 1;
    document.getElementById('btn-next').disabled = this.currentCard >= 7;
  },

  updateGoCanvas() {
    document.getElementById('btn-go-canvas').classList.toggle('hidden', !ConfirmManager.allConfirmed());
  },

  updateLineStates() {
    const finalLines = this.ensureFinalLines();
    document.querySelectorAll('.line-option').forEach((option) => {
      const row = Number(option.dataset.row);
      const value = this.getVersionLine(option.dataset.version, row);
      option.classList.toggle('selected', finalLines[row] === value);
    });
  },

  updateMeta() {
    if (this.currentMode === 'hook') {
      this.setMeta('传播钩子文案 | 不生成卡片，只供正文开头使用');
      document.getElementById('dirty-indicator').classList.add('hidden');
      document.getElementById('preview-status').textContent = '';
      return;
    }
    const markdown = this.getFinalMarkdown();
    this.setMeta(`卡片${this.currentCard} · ${CARD_TITLES[this.currentCard]} | 四列逐行选择 | 字数：${markdown.length}`);
    document.getElementById('dirty-indicator').classList.toggle('hidden', !this.dirtyCards.has(this.currentCard));
    document.getElementById('preview-status').textContent = ConfirmManager.isConfirmed(this.currentCard) ? '已确认' : '未确认';
  },

  setMeta(text) {
    document.getElementById('markdown-meta').textContent = text;
  },

  setPreview(markdown) {
    const preview = document.getElementById('preview-render');
    preview.innerHTML = markdown ? marked.parse(markdown) : '<p>暂无内容</p>';
    preview.classList.toggle('confirmed-preview', ConfirmManager.isConfirmed(this.currentCard));
  },

  displayLine(value) {
    if (!value) return '<span class="empty-line">空行</span>';
    return this.esc(value);
  },

  autoGrow(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.max(36, textarea.scrollHeight)}px`;
  },

  esc(value) {
    return String(value || '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;',
    }[ch]));
  },
};

document.addEventListener('DOMContentLoaded', () => EditorApp.init());
