// 主编排逻辑

const App = {
  currentCompany: null,
  currentVersion: 'standard',
  currentCard: 1,
  allVersions: {},        // { standard: {...}, business: {...}, spread: {...} }
  editedFields: {},       // 当前卡片字段，由各版本选中的字段拼合
  fieldPicks: {},         // { fieldKey: 'standard'|'business'|'spread' } — 每个字段选哪个版本
  localImages: {},        // { fieldKey: localPath } — AI 生成的图片本地路径
  isPreviewEditMode: false,
  researchPollTimer: null,

  // ── 初始化 ────────────────────────────────────
  async init() {
    this._bindEvents();
    await this._loadCompanies();
  },

  _bindEvents() {
    document.getElementById('company-select').addEventListener('change', e => {
      this.selectCompany(e.target.value);
    });

    document.querySelectorAll('.v-tab').forEach(btn => {
      btn.addEventListener('click', () => this.switchVersion(btn.dataset.version));
    });

    document.querySelectorAll('.card-tab').forEach(tab => {
      tab.addEventListener('click', () => this.switchCard(parseInt(tab.dataset.card)));
    });

    // 比较 header 点击切换版本
    document.querySelectorAll('.compare-hdr').forEach(hdr => {
      hdr.addEventListener('click', () => {
        const version = hdr.dataset.version;
        if (version) this.switchVersion(version);
      });
    });

    document.getElementById('btn-prev').addEventListener('click', () => {
      if (this.currentCard > 1) this.switchCard(this.currentCard - 1);
    });
    document.getElementById('btn-next').addEventListener('click', () => {
      if (this.currentCard < 7) this.switchCard(this.currentCard + 1);
    });
    document.getElementById('btn-confirm').addEventListener('click', () => this.confirmCard());

    document.getElementById('btn-start-research').addEventListener('click', () => this.startResearchJob());
    document.getElementById('btn-split').addEventListener('click', () => this.splitText());
    document.getElementById('btn-export').addEventListener('click', () => this.exportMarkdown());
    document.getElementById('btn-edit-toggle').addEventListener('click', () => this._togglePreviewEdit());
    document.getElementById('btn-hook-close').addEventListener('click', () => {
      document.getElementById('hook-modal').classList.add('hidden');
    });
  },

  // ── 公司选择 ──────────────────────────────────
  async _loadCompanies(preferredCompany = null) {
    const sel = document.getElementById('company-select');
    try {
      sel.innerHTML = '<option value="">-- 选择公司 --</option>';
      const companies = await API.getCompanies();
      if (companies.length === 0) {
        sel.innerHTML = '<option value="">-- 暂无数据 --</option>';
        return;
      }
      companies.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.company_name;
        opt.textContent = c.company_name;
        sel.appendChild(opt);
      });
      const target = preferredCompany && companies.some(c => c.company_name === preferredCompany)
        ? preferredCompany
        : companies[0].company_name;
      if (target) {
        this.selectCompany(target);
      }
    } catch (e) {
      console.error('加载公司列表失败:', e);
      this._toast('加载公司列表失败，请检查数据库', 'error');
    }
  },

  async selectCompany(name) {
    if (!name) return;
    this.currentCompany = name;
    document.getElementById('company-select').value = name;
    document.getElementById('global-status').textContent = '加载中...';

    try {
      this.allVersions = await API.getAllVersions(name);
      this.localImages = {};
      this.switchVersion(this.currentVersion);
      ConfirmManager.init(name);
      document.getElementById('global-status').textContent =
        `已加载：${name}（${Object.keys(this.allVersions).length}版本）`;
    } catch (e) {
      console.error('加载研究数据失败:', e);
      this._toast('加载数据失败: ' + e.message, 'error');
      document.getElementById('global-status').textContent = '加载失败';
    }
  },

  // ── 研究任务 ──────────────────────────────────
  async startResearchJob() {
    const nameInput = document.getElementById('research-company-name');
    const urlInput = document.getElementById('research-company-url');
    const btn = document.getElementById('btn-start-research');
    const companyName = nameInput.value.trim();
    const companyUrl = urlInput.value.trim();

    if (!companyName || !companyUrl) {
      this._setResearchStatus('请填写公司名和官网', 'error');
      return;
    }

    clearInterval(this.researchPollTimer);
    btn.disabled = true;
    this._setResearchStatus('正在提交研究任务...', 'info');

    try {
      const job = await API.startResearch(companyName, companyUrl);
      this._setResearchStatus(`任务已启动：${job.job_id}`, 'info');
      this._pollResearchJob(job.job_id, companyName, btn);
    } catch (e) {
      btn.disabled = false;
      this._setResearchStatus('启动失败', 'error');
      this._toast('启动失败: ' + e.message, 'error');
    }
  },

  _pollResearchJob(jobId, companyName, btn) {
    const poll = async () => {
      try {
        const job = await API.getResearchStatus(jobId);
        this._setResearchStatus(`${job.status} · ${job.stage || '处理中'} · ${job.detail || ''}`, job.status === 'failed' ? 'error' : 'info');

        if (job.status === 'done') {
          clearInterval(this.researchPollTimer);
          btn.disabled = false;
          this._setResearchStatus('研究完成，已刷新公司列表', 'success');
          await this._loadCompanies(companyName);
          this._toast('研究完成', 'success');
        } else if (job.status === 'failed') {
          clearInterval(this.researchPollTimer);
          btn.disabled = false;
          this._toast('研究失败: ' + (job.error || '未知错误'), 'error');
        }
      } catch (e) {
        clearInterval(this.researchPollTimer);
        btn.disabled = false;
        this._setResearchStatus('进度查询失败', 'error');
        this._toast('进度查询失败: ' + e.message, 'error');
      }
    };

    poll();
    this.researchPollTimer = setInterval(poll, 3000);
  },

  _setResearchStatus(message, type) {
    const el = document.getElementById('research-job-status');
    el.textContent = message;
    el.className = type || '';
  },

  // ── 版本切换 ──────────────────────────────────
  switchVersion(version) {
    this.currentVersion = version;
    document.querySelectorAll('.v-tab').forEach(t => {
      t.classList.toggle('active', t.dataset.version === version);
    });
    // 高亮对应版本 header
    document.querySelectorAll('.compare-hdr').forEach(hdr => {
      hdr.classList.toggle('active-hdr', hdr.dataset.version === version);
    });

    // 将所有字段选为该版本
    const data = this.allVersions[version];
    if (data) {
      this.fieldPicks = {};
      for (const key of Object.keys(data)) {
        if (key.startsWith('_')) continue;
        this.fieldPicks[key] = version;
        this.editedFields[key] = data[key];
      }
      this.editedFields._hooks = {
        hook_paragraph_1: data.hook_paragraph_1 || '',
        hook_paragraph_2: data.hook_paragraph_2 || '',
        hook_paragraph_3: data.hook_paragraph_3 || '',
      };
    } else {
      this.editedFields = { _hooks: {} };
      this.fieldPicks = {};
    }

    this._renderComparison(this.currentCard);
    this._renderMiniFields(this.currentCard);
    this._updatePreview();
    document.getElementById('mini-version-label').textContent =
      { standard: '标准版', business: '商业版', spread: '传播版' }[version] || version;
  },

  // ── 卡片切换 ──────────────────────────────────
  switchCard(cardIndex) {
    this.currentCard = cardIndex;
    document.querySelectorAll('.card-tab').forEach(t => {
      t.classList.toggle('active', parseInt(t.dataset.card) === cardIndex);
    });

    document.getElementById('btn-prev').disabled = cardIndex <= 1;
    document.getElementById('btn-next').disabled = cardIndex >= 7;

    this._renderComparison(cardIndex);
    this._renderMiniFields(cardIndex);
    this._updatePreview();

    const splitRow = document.getElementById('split-row');
    splitRow.style.display = (cardIndex >= 4) ? 'flex' : 'none';
  },

  // ── 三列对比渲染（每条可选） ──────────────────
  _renderComparison(cardIndex) {
    if (!this.currentCompany) return;

    const container = document.getElementById('compare-rows');
    const defs = CARD_FIELD_MAP[cardIndex] || [];
    const versions = ['standard', 'business', 'spread'];

    let rowsHtml = '';
    for (const def of defs) {
      const key = def.key;
      const pickedVer = this.fieldPicks[key] || '';
      let hasValue = false;
      for (const ver of versions) {
        const v = this.allVersions[ver] && this.allVersions[ver][key];
        if (v && v !== '暂缺') { hasValue = true; break; }
      }

      rowsHtml += `<div class="compare-row${hasValue ? '' : ' field-row-empty'}" data-field="${key}">`;
      rowsHtml += `<div class="compare-row-label">${def.label}</div>`;
      rowsHtml += `<div class="compare-row-cols">`;

      for (const ver of versions) {
        const verData = this.allVersions[ver];
        let val = verData ? verData[key] : '';
        const picked = this.fieldPicks[key] === ver;
        const pickedClass = picked ? ' field-picked' : '';

        if (val && typeof val === 'object') {
          val = JSON.stringify(val, null, 2);
        }
        const escaped = this._esc(String(val || ''));
        const display = (val && val !== '暂缺') ? escaped : '<span class="field-missing">暂缺</span>';

        rowsHtml += `<div class="compare-cell${pickedClass}" data-version="${ver}" data-field="${key}" title="点击选取此版本">`;
        rowsHtml += `<div class="cell-content">${display}</div>`;
        rowsHtml += `</div>`;
      }

      rowsHtml += `</div></div>`;
    }

    container.innerHTML = rowsHtml || '<div class="fields-empty">请选择公司，加载数据</div>';

    // 事件委托（只绑一次）
    if (!container._boundPick) {
      container.addEventListener('click', (e) => {
        const cell = e.target.closest('.compare-cell');
        if (!cell) return;
        this._pickField(cell.dataset.field, cell.dataset.version);
      });
      container._boundPick = true;
    }
  },

  _pickField(fieldKey, version) {
    const verData = this.allVersions[version];
    if (!verData) return;
    let val = verData[fieldKey];
    if (val === undefined || val === null || val === '') val = '暂缺';

    this.fieldPicks[fieldKey] = version;
    this.editedFields[fieldKey] = val;

    // 更新视觉
    document.querySelectorAll(`.compare-cell[data-field="${fieldKey}"]`).forEach(cell => {
      cell.classList.toggle('field-picked', cell.dataset.version === version);
    });
    const row = document.querySelector(`.compare-row[data-field="${fieldKey}"]`);
    if (row) {
      const isEmpty = !val || val === '暂缺' || (typeof val === 'string' && val.trim() === '暂缺');
      row.classList.toggle('field-row-empty', isEmpty);
    }

    this._renderMiniFields(this.currentCard);
    this._updatePreview();
  },

  // ── 右侧 mini 字段编辑 ─────────────────────────
  _renderMiniFields(cardIndex) {
    const container = document.getElementById('mini-fields');
    const defs = CARD_FIELD_MAP[cardIndex] || [];

    if (!this.currentCompany) {
      container.innerHTML = '<div class="fields-empty">请选择公司</div>';
      return;
    }

    let html = '';
    for (const def of defs) {
      const key = def.key;
      const val = this.editedFields[key] || '';
      const isJson = typeof val === 'object';

      html += `<div class="field-group">`;
      html += `<div class="field-label"><span>${def.label}</span></div>`;

      if (key === 'main_product_img_src' || key === 'website_url') {
        const imgPath = this.localImages[key] || '';
        html += `<div class="field-img-row">
          <textarea class="field-input" data-field="${key}" rows="1">${this._esc(isJson ? JSON.stringify(val) : String(val))}</textarea>
          <button class="btn-img-gen" data-field="${key}">生成</button>
        </div>`;
        if (imgPath) {
          html += `<div style="font-size:10px;color:var(--green);margin-top:1px">已生成：${imgPath}</div>`;
        }
      } else if (isJson) {
        html += `<textarea class="field-input" data-field="${key}" rows="3">${this._esc(JSON.stringify(val, null, 2))}</textarea>`;
      } else {
        const rows = val.length > 200 ? 4 : (val.length > 100 ? 2 : 1);
        html += `<textarea class="field-input" data-field="${key}" rows="${rows}">${this._esc(String(val))}</textarea>`;
      }

      html += `</div>`;
    }

    container.innerHTML = html;

    // 绑定编辑事件
    container.querySelectorAll('.field-input').forEach(input => {
      input.addEventListener('input', () => {
        const key = input.dataset.field;
        const raw = input.value;
        if ((key === 'timeline_events' || key === 'other_products' || key === 'competitors') && raw.trim()) {
          try { this.editedFields[key] = JSON.parse(raw); } catch { this.editedFields[key] = raw; }
        } else {
          this.editedFields[key] = raw;
        }
        this._schedulePreviewUpdate();
      });
    });

    // 绑定图片生成按钮
    container.querySelectorAll('.btn-img-gen').forEach(btn => {
      btn.addEventListener('click', async () => {
        const key = btn.dataset.field;
        await this._generateImage(key);
      });
    });
  },

  _esc(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },

  // ── 实时预览 ──────────────────────────────────
  _previewTimer: null,
  _schedulePreviewUpdate() {
    clearTimeout(this._previewTimer);
    this._previewTimer = setTimeout(() => this._updatePreview(), 300);
  },

  _updatePreview() {
    if (this.isPreviewEditMode) return;
    const markdown = buildCardMarkdown(this.currentCard, this.editedFields, this.localImages);
    const renderEl = document.getElementById('preview-render');
    renderEl.innerHTML = marked.parse(markdown);
    if (ConfirmManager.isConfirmed(this.currentCard)) {
      const badge = document.createElement('span');
      badge.style.cssText = 'display:inline-block;background:#E8F5E9;color:#2E7D32;padding:2px 8px;border-radius:10px;font-size:12px;margin-left:8px';
      badge.textContent = '已确认';
      const h2 = renderEl.querySelector('h2');
      if (h2) h2.appendChild(badge);
    }
  },

  // ── AI 图片生成 ───────────────────────────────
  async _generateImage(fieldKey) {
    const btn = document.querySelector(`.btn-img-gen[data-field="${fieldKey}"]`);
    if (btn) { btn.disabled = true; btn.textContent = '生成中...'; }

    try {
      const promptParts = [];
      if (this.editedFields.main_product_name) promptParts.push(this.editedFields.main_product_name);
      if (this.editedFields.main_product_def) promptParts.push(this.editedFields.main_product_def);
      if (this.editedFields.company_def) promptParts.push(this.editedFields.company_def);

      const prompt = promptParts.join('. ') || (this.editedFields[fieldKey] || 'AI startup product screenshot');
      const result = await API.generateImage(this.currentCompany, fieldKey, prompt);
      this.localImages[fieldKey] = result.img_path;
      this._toast('图片生成成功', 'success');
      this._renderMiniFields(this.currentCard);
      this._updatePreview();
    } catch (e) {
      this._toast('图片生成失败: ' + e.message, 'error');
    }
    if (btn) { btn.disabled = false; btn.textContent = '生成'; }
  },

  // ── 卡片确认 ──────────────────────────────────
  async confirmCard() {
    if (!this.currentCompany) return;

    const cardIndex = this.currentCard;
    const fields = ConfirmManager.getCardFields(cardIndex, this.editedFields);
    const imgPaths = {};
    for (const key of Object.keys(this.localImages)) {
      if (fields.hasOwnProperty(key)) {
        imgPaths[key] = this.localImages[key];
      }
    }

    try {
      await API.saveFinal(this.currentCompany, cardIndex, fields, imgPaths);
      ConfirmManager.confirm(cardIndex);
      this._toast(`卡片${cardIndex} 已确认`, 'success');
      this._updatePreview();
      this._renderComparison(this.currentCard);

      const next = ConfirmManager.getNextUnconfirmed(cardIndex);
      if (next) {
        this.switchCard(next);
      } else if (ConfirmManager.allConfirmed()) {
        this._toast('全部7张卡片已确认！可导出 Markdown', 'success');
        this._showHooks();
      }
    } catch (e) {
      this._toast('保存失败: ' + e.message, 'error');
    }
  },

  _showHooks() {
    const hooks = this.editedFields._hooks || {};
    const container = document.getElementById('hook-paragraphs');
    let html = '';
    if (hooks.hook_paragraph_1) html += `<div class="hook-p"><strong>段落1</strong><br>${hooks.hook_paragraph_1}</div>`;
    if (hooks.hook_paragraph_2) html += `<div class="hook-p"><strong>段落2</strong><br>${hooks.hook_paragraph_2}</div>`;
    if (hooks.hook_paragraph_3) html += `<div class="hook-p"><strong>段落3</strong><br>${hooks.hook_paragraph_3}</div>`;
    if (!html) html = '<p>暂无钩子段落</p>';
    container.innerHTML = html;
    document.getElementById('hook-modal').classList.remove('hidden');
  },

  // ── 文本分段 ──────────────────────────────────
  async splitText() {
    const cardIndex = this.currentCard;
    const defs = CARD_FIELD_MAP[cardIndex] || [];
    const count = parseInt(document.getElementById('segment-count').value) || 2;

    for (const def of defs) {
      const val = this.editedFields[def.key];
      if (!val || val === '暂缺' || typeof val !== 'string' || val.length < 100) continue;
      try {
        const result = await API.splitText(val, count);
        if (result.segments && result.segments.length > 0) {
          this.editedFields[def.key] = result.segments.join('\n\n');
        }
      } catch (e) {
        // 分段失败静默跳过
      }
    }
    this._renderMiniFields(cardIndex);
    this._updatePreview();
    this._toast('文本分段完成', 'success');
  },

  // ── 预览模式切换 ──────────────────────────────
  _togglePreviewEdit() {
    this.isPreviewEditMode = !this.isPreviewEditMode;
    const renderEl = document.getElementById('preview-render');
    const editorEl = document.getElementById('preview-editor');
    const btn = document.getElementById('btn-edit-toggle');

    if (this.isPreviewEditMode) {
      const markdown = buildCardMarkdown(this.currentCard, this.editedFields, this.localImages);
      editorEl.value = markdown;
      renderEl.classList.add('hidden');
      editorEl.classList.remove('hidden');
      btn.textContent = '预览模式';
      editorEl.addEventListener('input', () => {
        renderEl.innerHTML = marked.parse(editorEl.value);
      });
    } else {
      editorEl.classList.add('hidden');
      renderEl.classList.remove('hidden');
      btn.textContent = '编辑模式';
      this._updatePreview();
    }
  },

  // ── 导出 ──────────────────────────────────────
  async exportMarkdown() {
    if (!this.currentCompany) return;
    try {
      const result = await API.exportCompany(this.currentCompany);
      if (result.markdown) {
        const blob = new Blob([result.markdown], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.currentCompany}_knowledge_card.md`;
        a.click();
        URL.revokeObjectURL(url);
        this._toast('Markdown 导出成功', 'success');
      }
    } catch (e) {
      this._toast('导出失败: ' + e.message, 'error');
    }
  },

  // ── 工具方法 ──────────────────────────────────
  _toast(msg, type) {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2500);
  },
};

// 启动
document.addEventListener('DOMContentLoaded', () => App.init());
