const CARD_TITLES = {
  1: '首页',
  2: '公司介绍',
  3: '发展沿袭',
  4: '主产品',
  5: '其他产品',
  6: '商业模式',
  7: '竞争格局',
  8: '总结',
};

const CARD_COUNT = 8;

const VERSION_LABELS = {
  standard: '标准版',
  business: '商业版',
  spread: '传播版',
};

const VERSIONS = ['standard', 'business', 'spread'];

const SLOT_LABELS = {
  logo: 'Logo',
  website_screenshot: '官网截图',
  office: '办公室或地图',
  product_main: '主产品截图',
  products_other: '其他产品截图',
  competitors: '竞品截图',
  competitors_logo_strip: '三个竞品 Logo 横排图',
  chart_competitive: 'AI 创业公司竞争格局图',
  chart_ecosystem: 'AI 产业链生态位图',
  flywheel: '飞轮图',
  timeline: '时间线图',
};

const SLOT_ORDER = ['logo', 'website_screenshot', 'office', 'product_main', 'products_other', 'competitors', 'competitors_logo_strip', 'chart_competitive', 'chart_ecosystem', 'flywheel', 'timeline'];

const EditorApp = {
  companyName: '',
  currentCard: null,
  currentSection: 'content',
  versionChoices: {},
  hookChoices: {},
  finalLinesByCard: {},
  dirtyCards: new Set(),
  previewTimer: null,
  _previewMode: 'preview',
  _imageIframeLoaded: false,
  _slots: null,
  _activeSlot: null,

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

    // 显示删除按钮
    const delBtn = document.getElementById('btn-delete-company');
    if (delBtn) {
      delBtn.classList.remove('hidden');
      delBtn.addEventListener('click', () => this.deleteCompany());
    }

    await this.loadStatus();
    await this.loadHookChoices();
    this.switchSection('content');
    await this.loadCard(1);
  },

  bindEvents() {
    document.querySelectorAll('.accordion-header').forEach(header => {
      header.addEventListener('click', () => {
        this.switchSection(header.dataset.section);
      });
    });

    document.getElementById('btn-recollect-editor')?.addEventListener('click', () => this.recollectAssets());

    document.querySelectorAll('.editor-card-btn').forEach((button) => {
      button.addEventListener('click', async () => {
        const card = button.dataset.card;
        if (card === 'hook') {
          this.switchSection('hook');
          await this.showHooks();
        } else if (card === 'image') {
          this.switchSection('image');
        } else if (card === 'dbfields') {
          this.switchSection('dbfields');
        } else {
          this.switchSection('content');
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
      if (this.currentCard < CARD_COUNT) this.loadCard(this.currentCard + 1);
    });
    document.getElementById('btn-confirm').addEventListener('click', () => this.confirmCurrentCard());

  },

  /* ── 手风琴切换 ── */

  switchSection(section) {
    this.currentSection = section;

    document.querySelectorAll('.accordion-header').forEach(h => {
      h.classList.toggle('open', h.dataset.section === section);
    });
    document.querySelectorAll('.accordion-body').forEach(b => {
      if (b.dataset.section === 'card-settings' || b.dataset.section === 'field-finalize') {
        b.classList.remove('open');
      } else {
        b.classList.toggle('open', b.dataset.section === section);
      }
    });

    document.querySelectorAll('#editor-card-nav .editor-card-btn').forEach(b => {
      b.classList.toggle('active', section === 'content' && Number(b.dataset.card) === this.currentCard);
    });
    const hookBtn = document.querySelector('#editor-hook-nav .editor-card-btn');
    if (hookBtn) hookBtn.classList.toggle('active', section === 'hook');

    const modeHandlers = {
      'image':          () => { this.showImageMode(); },
      'hook':           () => { this.showHookMode(); this.showHooks(); },
      'dbfields':       () => { this.showDbFields(); },
      'card-settings':  () => { this.showCardSettingsMode(); },
      'field-finalize': () => { this.showFieldFinalizeMode(); },
    };
    const handler = modeHandlers[section];
    if (handler) { handler(); } else { this.showContentMode(); }
  },

  /* ── 模式切换 ── */

  // Shared overlay IDs — single source of truth for all mode methods
  _OVERLAY_IDS: ['image-studio-frame', 'hook-mode', 'db-fields-mode', 'card-settings-mode', 'field-finalize-mode'],

  _closeAllOverlays() {
    this._OVERLAY_IDS.forEach(id => document.getElementById(id).classList.remove('open'));
  },

  _hidePanesShowOverlay(overlayId) {
    document.getElementById('editor-middle-pane').style.display = 'none';
    document.getElementById('editor-right-pane').style.display = 'none';
    this._closeAllOverlays();
    document.getElementById(overlayId).classList.add('open');
  },

  showContentMode() {
    document.getElementById('editor-middle-pane').style.display = '';
    document.getElementById('editor-right-pane').style.display = '';
    this._closeAllOverlays();
    document.getElementById('version-compare').classList.remove('hidden');
    document.querySelector('.markdown-toolbar').classList.remove('hidden');
    document.querySelector('.markdown-footer').classList.remove('hidden');
    document.getElementById('preview-render').classList.remove('hidden');
    document.getElementById('preview-status').classList.remove('hidden');
    document.getElementById('btn-confirm').classList.remove('hidden');
    document.getElementById('hook-content').classList.add('hidden');
    document.getElementById('hook-render').classList.add('hidden');
    this.updateButtons();
  },

  showHookMode() {
    this._hidePanesShowOverlay('hook-mode');
    this.updateButtons();
  },

  showImageMode() {
    this._hidePanesShowOverlay('image-studio-frame');
    this.updateButtons();

    if (!this._imageIframeLoaded && this.companyName) {
      const iframe = document.getElementById('image-studio-iframe');
      const slot = this._activeSlot || '';
      iframe.src = `/image-studio/?company=${encodeURIComponent(this.companyName)}&embed=1&slot=${encodeURIComponent(slot)}`;
      this._imageIframeLoaded = true;
    }

    this.loadImageSlots();
  },

  showCardSettingsMode() {
    this._hidePanesShowOverlay('card-settings-mode');
    this.updateMeta();
    this.updateButtons();
  },

  showFieldFinalizeMode() {
    this._hidePanesShowOverlay('field-finalize-mode');
    this.updateMeta();
    this.updateButtons();
  },

  /* ── 图片槽位列表 ── */

  async loadImageSlots() {
    if (this._slots) {
      this.renderImageSlots();
      return;
    }
    try {
      const resp = await fetch(`/api/image-studio/${encodeURIComponent(this.companyName)}`);
      if (resp.ok) {
        const data = await resp.json();
        this._slots = data.slots || [];
        this.renderImageSlots();
      }
    } catch {
      // 静默
    }
  },

  renderImageSlots() {
    const container = document.getElementById('image-slot-list');
    if (!container || !this._slots) return;

    container.innerHTML = this._slots.map(s => {
      const isSvgSlot = s.asset_key === 'flywheel' || s.asset_key === 'timeline';
      const thumbHtml = s.local_path
        ? `<img src="${this._esc(s.local_path)}" alt="">`
        : `<div class="slot-thumb-small">${isSvgSlot ? '&#9881;' : '&#128247;'}</div>`;

      let meta;
      if (isSvgSlot) {
        meta = s.status === 'ready' ? 'SVG信息图 · 已就绪' : 'SVG信息图 · 待生成';
      } else {
        meta = s.status === 'ready' ? '已就绪' : '待配图';
        if (s.variant_count > 0) meta += ` · ${s.variant_count}变体`;
      }

      const activeCls = this._activeSlot === s.asset_key ? ' active' : '';

      return `
        <div class="image-slot-item${activeCls}" data-slot="${s.asset_key}">
          <div class="slot-thumb-small">${thumbHtml}</div>
          <div class="slot-info-small">
            <span class="slot-label-small">${SLOT_LABELS[s.asset_key] || s.asset_key}</span>
            <span class="slot-meta-small">${meta}</span>
          </div>
          <span class="slot-dot ${s.status}"></span>
        </div>
      `;
    }).join('');

    container.querySelectorAll('.image-slot-item').forEach(item => {
      item.addEventListener('click', () => {
        const slot = item.dataset.slot;
        this._activeSlot = slot;
        this.renderImageSlots();
        // 通知 iframe 切换槽位
        const iframe = document.getElementById('image-studio-iframe');
        iframe.src = `/image-studio/?company=${encodeURIComponent(this.companyName)}&embed=1&slot=${encodeURIComponent(slot)}`;
      });
    });
  },

  async recollectAssets() {
    const btn = document.getElementById('btn-recollect-editor');
    if (btn) { btn.disabled = true; btn.textContent = '采集中...'; }
    try {
      const r = await fetch(`/api/assets/collect/${encodeURIComponent(this.companyName)}`, { method: 'POST' });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
      this._slots = null;
      await this.loadImageSlots();
      // 刷新 iframe 中的 image-studio
      const iframe = document.getElementById('image-studio-iframe');
      if (iframe) iframe.src = iframe.src;
    } catch (e) {
      alert('采集失败: ' + e.message);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '重新采集图片'; }
    }
  },

  /* ── 状态 ── */

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
    this.currentCard = cardIndex;
    this.updateNav();
    await this.loadVersionChoices(cardIndex);
    this.ensureFinalLines();
    await this.restoreFinalLines(cardIndex);
    this.renderLineChoices();
    this.updateMeta();
    this.setPreview(this.getFinalMarkdown());
    this.updateButtons();
  },

  async restoreFinalLines(cardIndex) {
    if (!ConfirmManager.isConfirmed(cardIndex)) return;
    try {
      const result = await API.getFinalCard(this.companyName, cardIndex);
      if (result.markdown_content) {
        const blocks = result.markdown_content.replace(/\n+$/, '').split('\n\n');
        const rows = this.getRenderableRows();
        const finalLines = this.finalLinesByCard[cardIndex];
        for (let i = 0; i < Math.min(blocks.length, rows.length); i++) {
          finalLines[rows[i]] = blocks[i];
        }
      }
    } catch {
      // 静默
    }
  },

  async showHooks() {
    if (!this.companyName) return;
    this.updateNav();
    await this.loadHookChoices();
    this.renderHookContent();
  },

  /* ── 钩子内容 ── */

  renderHookContent() {
    const container = document.getElementById('hook-mode-content');
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

  /* ── 版本选择 ── */

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

  /* ── 行选择 ── */

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
    const current = this.finalLinesByCard[this.currentCard][row];
    if (current === value) {
      this.finalLinesByCard[this.currentCard][row] = '';
      const input = document.querySelector(`.final-line-input[data-row="${row}"]`);
      if (input) {
        input.value = '';
        this.autoGrow(input);
      }
    } else {
      this.finalLinesByCard[this.currentCard][row] = value;
      const input = document.querySelector(`.final-line-input[data-row="${row}"]`);
      if (input) {
        input.value = value;
        this.autoGrow(input);
      }
    }
    this.markDirty();
    this.setPreview(this.getFinalMarkdown());
    this.updateLineStates();
  },

  getFinalMarkdown() {
    const lines = this.ensureFinalLines();
    return this.getRenderableRows()
      .map((row) => lines[row] || '')
      .filter((line) => line.trim())
      .join('\n\n')
      .replace(/\s+$/g, '') + '\n';
  },

  ensureFinalLines() {
    if (!this.finalLinesByCard[this.currentCard]) {
      this.finalLinesByCard[this.currentCard] = [];
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

  /* ── Dirty & Save ── */

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

    // 自动生成 SVG 信息图
    this._autoGenerateSvg(this.currentCard);

    if (!ConfirmManager.allConfirmed()) {
      const next = this.nextUnconfirmed();
      if (next) await this.loadCard(next);
    }
  },

  _autoGenerateSvg(cardIndex) {
    const svgConfig = { 3: 'timeline', 6: 'flywheel' };
    const assetKey = svgConfig[cardIndex];
    if (!assetKey) return;

    const defaultTemplates = {
      timeline: { template_id: 'timeline_horizontal', params: { node_w: 180, accent_color: '#29B8D4', title_size: 16 } },
      flywheel: { template_id: 'flywheel_circular', params: { radius: 200, accent_color: '#29B8D4', label_size: 16 } },
    };
    const cfg = defaultTemplates[assetKey];

    fetch(`/api/image-studio/${encodeURIComponent(this.companyName)}/${encodeURIComponent(assetKey)}/render-svg`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg),
    }).then(r => r.json()).then(data => {
      if (data.error) console.error('SVG 自动生成失败:', data.error);
    }).catch(e => {
      console.error('SVG 自动生成失败:', e);
    });
  },

  nextUnconfirmed() {
    for (let i = this.currentCard + 1; i <= CARD_COUNT; i++) {
      if (!ConfirmManager.isConfirmed(i)) return i;
    }
    for (let i = 1; i <= CARD_COUNT; i++) {
      if (!ConfirmManager.isConfirmed(i)) return i;
    }
    return null;
  },

  /* ── UI 更新 ── */

  updateNav() {
    document.querySelectorAll('.editor-card-btn').forEach((button) => {
      const card = button.dataset.card;
      if (this.currentSection === 'hook') {
        button.classList.toggle('active', card === 'hook');
      } else if (this.currentSection === 'image') {
        // 图片区不激活卡片按钮
      } else if (this.currentCard === null) {
        button.classList.remove('active');
      } else {
        button.classList.toggle('active', Number(card) === this.currentCard);
      }
    });
  },

  updateButtons() {
    if (this.currentSection === 'hook' || this.currentSection === 'image' || this.currentSection === 'card-settings' || this.currentSection === 'field-finalize' || this.currentCard === null) {
      document.getElementById('btn-prev').disabled = true;
      document.getElementById('btn-next').disabled = true;
      return;
    }
    document.getElementById('btn-prev').disabled = this.currentCard <= 1;
    document.getElementById('btn-next').disabled = this.currentCard >= CARD_COUNT;
  },

  async deleteCompany() {
    if (!this.companyName) return;
    const confirmed = confirm(
      `确定删除「${this.companyName}」的全部数据？\n\n` +
      `包括：研究记录、定稿内容、图片资产、图片变体\n` +
      `此操作不可恢复。`
    );
    if (!confirmed) return;

    const doubleConfirm = confirm('再次确认：输入"删除"或点确定继续，点取消放弃。');
    if (!doubleConfirm) return;

    try {
      const r = await fetch(`/api/research/${encodeURIComponent(this.companyName)}`, { method: 'DELETE' });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
      alert(`已删除「${this.companyName}」。\n\n` +
        `研究记录: ${data.deleted.research} 条\n` +
        `研究任务: ${data.deleted.research_jobs} 条\n` +
        `定稿内容: ${data.deleted.final_content} 条\n` +
        `图片变体: ${data.deleted.image_variants} 条\n` +
        `资产记录: ${data.deleted.company_assets} 条\n` +
        `图片目录: ${data.deleted.images_dir}`
      );
      window.location.href = '/';
    } catch (e) {
      alert('删除失败: ' + e.message);
    }
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
    const SECTION_META = {
      'hook':           '传播钩子文案 | 不生成卡片，只供正文开头使用',
      'image':          '图片定稿 | 为卡片搜索和定稿配图',
      'card-settings':  '卡片设置 | 管理卡片结构、字段分配与模板',
      'field-finalize': '字段定稿 | 逐字段确认三版本内容',
    };
    const meta = SECTION_META[this.currentSection];
    if (meta) {
      this.setMeta(meta);
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

  _esc(s) {
    return String(s || '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;',
    }[ch]));
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

  /* ── 数据库字段模式 ── */

  _allFieldsCache: null,
  _showSystemFields: false,

  showDbFields() {
    this._hidePanesShowOverlay('db-fields-mode');

    document.getElementById('db-fields-company').textContent = this.companyName;
    // 系统字段开关
    document.getElementById('db-show-system').checked = this._showSystemFields;
    document.getElementById('db-show-system').onchange = (e) => {
      this._showSystemFields = e.target.checked;
      this._renderDbFieldsTable();
    };
    if (!this._allFieldsCache) this._loadAllFieldsForDb().then(() => this._renderDbFieldsTable());
    else this._renderDbFieldsTable();

    this.updateButtons();
  },

  async _loadAllFieldsForDb() {
    this._allFieldsCache = {};
    await Promise.all(VERSIONS.map(async v => {
      try {
        const r = await API.getResearch(this.companyName, v);
        this._allFieldsCache[v] = r || {};
      } catch { this._allFieldsCache[v] = {}; }
    }));
  },

  _renderDbFieldsTable() {
    const tbody = document.getElementById('db-fields-tbody');
    if (!tbody || !this._allFieldsCache) return;

    const allKeys = new Set();
    VERSIONS.forEach(v => Object.keys(this._allFieldsCache[v] || {}).forEach(k => allKeys.add(k)));

    const SYSTEM_KEYS = new Set([
      'website_url','main_product_img_src','office_photo_hints',
      'ai_model_dependency','workflow_integration_level','data_flywheel',
      'proprietary_data_asset','incumbent_direct_competitor','customer_segment_type',
      'funding_stage','funding_stage_score','pricing_model','inference_cost_exposure',
      'stack_layer','score_defensibility','score_incumbent_attention','score_value_capture',
    ]);
    const HOOK_KEYS = new Set(['hook_paragraph_1','hook_paragraph_2','hook_paragraph_3']);

    const ordered = [...allKeys].sort();
    const rows = ordered.map(field => {
      if (SYSTEM_KEYS.has(field) && !this._showSystemFields) return '';
      const isSystem = SYSTEM_KEYS.has(field);
      const isHook = HOOK_KEYS.has(field);
      const cls = isSystem ? 'cell-system' : isHook ? 'cell-hook' : '';
      const dv = (v) => {
        const val = (this._allFieldsCache[v] || {})[field];
        if (!val || val === '暂缺') return '<span class="cell-empty">-</span>';
        if (typeof val === 'object') return `<span title="${this.esc(JSON.stringify(val))}">JSON</span>`;
        return this.esc(String(val).substring(0, 120));
      };
      return `<tr class="${cls}">
        <td title="${field}">${field}</td>
        <td>${dv('standard')}</td>
        <td>${dv('business')}</td>
        <td>${dv('spread')}</td>
      </tr>`;
    }).filter(Boolean);

    tbody.innerHTML = rows.join('');
  },
};

document.addEventListener('DOMContentLoaded', () => EditorApp.init());
