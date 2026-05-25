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

    // 比较 header 点击切换版本（快速填充）
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
    document.getElementById('btn-export-draft').addEventListener('click', () => this.exportDraftMarkdown());
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
      this.fieldPicks = {};
      this.editedFields = { _hooks: {} };
      // 取第一个可用版本的数据作为初始值
      const firstVer = this.allVersions.standard || this.allVersions.business || this.allVersions.spread;
      if (firstVer) {
        for (const key of Object.keys(firstVer)) {
          if (!key.startsWith('_')) {
            this.editedFields[key] = firstVer[key];
          }
        }
      }
      this._renderAllAccordions();
      ConfirmManager.init(name);
      // 展开卡片1
      this.switchCard(1);
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

        if (job.status === 'done') {
          this._setResearchStatus(`${job.status} · ${job.stage || '完成'} · ${job.detail || ''}`, 'success');
          clearInterval(this.researchPollTimer);
          btn.disabled = false;
          this._setResearchStatus('研究完成，已刷新公司列表', 'success');
          await this._loadCompanies(companyName);
          this._toast('研究完成', 'success');
        } else if (job.status === 'failed') {
          this._setResearchStatus(`研究失败 · ${job.error || job.detail || '未知错误'}`, 'error');
          clearInterval(this.researchPollTimer);
          btn.disabled = false;
          this._toast('研究失败: ' + (job.error || '未知错误'), 'error');
        } else {
          this._setResearchStatus(`${job.status} · ${job.stage || '处理中'} · ${job.detail || ''}`, 'info');
        }
      } catch (e) {
        clearInterval(this.researchPollTimer);
        btn.disabled = false;
        this._setResearchStatus('进度查询失败', 'error');
        this._toast('进度查询失败: ' + e.message, 'error');
      }
    };

    poll();
    this.researchPollTimer = setInterval(poll, 2000);
  },

  _setResearchStatus(message, type) {
    const el = document.getElementById('research-job-status');
    el.textContent = message;
    el.className = type || '';

    const details = document.getElementById('research-section');
    const summaryStatus = document.getElementById('research-summary-status');
    if (type === 'info') {
      details.open = true;
      summaryStatus.textContent = '（研究中...）';
      summaryStatus.style.color = 'var(--cyan)';
    } else if (type === 'success') {
      setTimeout(() => { details.open = false; }, 3000);
      summaryStatus.textContent = '（上次完成）';
      summaryStatus.style.color = 'var(--green)';
    } else if (type === 'error') {
      summaryStatus.textContent = '（失败）';
      summaryStatus.style.color = 'var(--red)';
    }
  },

  // ── 版本切换（快速填充） ──────────────────────
  switchVersion(version) {
    const labels = { standard: '标准版', business: '商业版', spread: '传播版' };
    if (!confirm(`将所有字段设为「${labels[version]}」？`)) return;

    const data = this.allVersions[version];
    if (!data) return;
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

    this._renderComparisonRows(this.currentCard);
    this._renderMiniFields(this.currentCard);
    this._updatePreview();
  },

  // ── 卡片切换 ──────────────────────────────────
  switchCard(cardIndex) {
    this.currentCard = cardIndex;
    const details = document.querySelector(`.accordion-card[data-card="${cardIndex}"]`);
    if (details) {
      details.open = true;
      details.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  },

  // ── 手风琴结构 ──────────────────────────────
  _renderAllAccordions() {
    if (!this.currentCompany) return;
    const list = document.getElementById('accordion-list');
    let html = '';
    for (let i = 1; i <= 7; i++) {
      const title = CARD_TITLES[i] || `卡片${i}`;
      const confirmed = ConfirmManager.isConfirmed(i);
      html += `<details class="accordion-card" data-card="${i}">`;
      html += `<summary>卡片${i}：${title}${confirmed ? ' <span class="accordion-confirmed">已确认</span>' : ''}</summary>`;
      html += `<div class="compare-rows" id="compare-rows-${i}"></div>`;
      html += `</details>`;
    }
    list.innerHTML = html;

    // 事件：展开时渲染字段
    list.querySelectorAll('.accordion-card').forEach(details => {
      details.addEventListener('toggle', () => {
        if (details.open) {
          const cardIndex = parseInt(details.dataset.card);
          this.currentCard = cardIndex;
          this._renderComparisonRows(cardIndex);
          this._renderMiniFields(cardIndex);
          this._updatePreview();
          this._updateNavButtons();
          // 手风琴模式：关闭其他
          list.querySelectorAll('.accordion-card').forEach(d => {
            if (d !== details) d.open = false;
          });
        }
      });
    });

    // 事件委托：字段选取
    if (!list._boundPick) {
      list.addEventListener('click', (e) => {
        const cell = e.target.closest('.compare-cell');
        if (!cell) return;
        this._pickField(cell.dataset.field, cell.dataset.version);
      });
      list._boundPick = true;
    }
  },

  _renderComparisonRows(cardIndex) {
    const container = document.getElementById(`compare-rows-${cardIndex}`);
    if (!container) return;

    const defs = CARD_FIELD_MAP[cardIndex] || [];
    const versions = ['standard', 'business', 'spread'];

    let rowsHtml = '';
    for (const def of defs) {
      const key = def.key;
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

    container.innerHTML = rowsHtml || '<div class="fields-empty">暂无字段数据</div>';
  },

  _renderComparison(cardIndex) {
    // 兼容旧调用：展开对应手风琴
    const details = document.querySelector(`.accordion-card[data-card="${cardIndex}"]`);
    if (details && !details.open) {
      details.open = true;
      // toggle 事件会自动调用 _renderComparisonRows
    } else if (details && details.open) {
      this._renderComparisonRows(cardIndex);
    }
  },

  _updateNavButtons() {
    document.getElementById('btn-prev').disabled = this.currentCard <= 1;
    document.getElementById('btn-next').disabled = this.currentCard >= 7;
    const splitRow = document.getElementById('split-row');
    splitRow.style.display = (this.currentCard >= 4) ? 'flex' : 'none';
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

      const pickedVer = this.fieldPicks[key] || '';
      const verBadge = pickedVer
        ? `<span class="ver-badge ver-${pickedVer}">${pickedVer === 'standard' ? 'S' : pickedVer === 'business' ? 'B' : 'P'}</span>`
        : '';

      html += `<div class="field-group">`;
      html += `<div class="field-label"><span>${def.label}</span>${verBadge}</div>`;

      if (key === 'main_product_img_src') {
        const imgPath = this.localImages[key] || '';
        html += `<div class="field-img-row">
          <input class="field-input field-input-text" data-field="${key}" value="${this._esc(String(val))}">
          <button class="btn-img-gen" data-field="${key}">生成</button>
        </div>`;
        if (imgPath) {
          html += `<div style="font-size:10px;color:var(--green);margin-top:1px">已生成：${imgPath}</div>`;
        }
      } else if (isJson) {
        html += `<textarea class="field-input field-input-area" data-field="${key}" rows="3">${this._esc(JSON.stringify(val, null, 2))}</textarea>`;
      } else if (def.inputType === 'text') {
        html += `<input class="field-input field-input-text" data-field="${key}" value="${this._esc(String(val))}">`;
      } else {
        html += `<textarea class="field-input field-input-area" data-field="${key}" rows="3">${this._esc(String(val))}</textarea>`;
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
    this._previewTimer = setTimeout(() => this._updatePreview(), 150);
  },

  _updatePreview() {
    if (this.isPreviewEditMode) return;
    const confirmed = ConfirmManager.isConfirmed(this.currentCard);
    const renderEl = document.getElementById('preview-render');

    const markdown = buildCardMarkdown(this.currentCard, this.editedFields, this.localImages);
    renderEl.innerHTML = marked.parse(markdown);
    renderEl.style.borderLeft = confirmed ? '3px solid var(--green)' : '3px solid transparent';
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
      this._renderComparisonRows(this.currentCard);

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
    html += `<div style="margin-top:16px;text-align:center">
      <a href="/canvas/?company=${encodeURIComponent(this.currentCompany)}" class="btn btn-cyan" style="display:inline-block;text-decoration:none;padding:10px 24px;background:var(--cyan);color:white;border-radius:6px;font-size:14px">去制作卡片</a>
    </div>`;
    container.innerHTML = html;
    document.getElementById('hook-modal').classList.remove('hidden');
  },

  // ── 文本分段 ──────────────────────────────────
  async splitText() {
    const cardIndex = this.currentCard;
    const defs = CARD_FIELD_MAP[cardIndex] || [];
    const count = parseInt(document.getElementById('segment-count').value) || 2;
    let splitCount = 0;
    let skippedCount = 0;
    const splitErrors = [];

    for (const def of defs) {
      const val = this.editedFields[def.key];
      if (!val || val === '暂缺' || typeof val !== 'string') {
        skippedCount++;
        continue;
      }
      try {
        const result = await API.splitText(val, count);
        if (result.segments && result.segments.length > 0) {
          this.editedFields[def.key] = result.segments.join('\n\n');
          splitCount++;
        } else {
          skippedCount++;
        }
      } catch (e) {
        splitErrors.push(`${def.label}: ${e.message}`);
      }
    }
    this._renderMiniFields(cardIndex);
    this._updatePreview();
    if (splitErrors.length > 0) {
      this._toast(`分段失败 ${splitErrors.length} 项，请检查 API Key 或网络`, 'error');
    } else if (splitCount > 0) {
      this._toast(`文本分段完成：${splitCount} 项`, 'success');
    } else {
      this._toast(`没有可分段字段（跳过 ${skippedCount} 项）`, 'error');
    }
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
        this._downloadMarkdown(result.markdown, `${this.currentCompany}_confirmed.md`);
        this._toast('已确认 Markdown 导出成功', 'success');
      }
    } catch (e) {
      this._toast('导出失败：请先确认至少一张卡片', 'error');
    }
  },

  exportDraftMarkdown() {
    if (!this.currentCompany) return;
    const parts = [];
    for (let i = 1; i <= 7; i++) {
      parts.push(buildCardMarkdown(i, this.editedFields, this.localImages));
    }
    const hooks = this.editedFields._hooks || {};
    if (hooks.hook_paragraph_1 || hooks.hook_paragraph_2 || hooks.hook_paragraph_3) {
      parts.push('---');
      parts.push('');
      parts.push('## 传播钩子段落');
      parts.push('');
      if (hooks.hook_paragraph_1) parts.push(hooks.hook_paragraph_1);
      if (hooks.hook_paragraph_2) parts.push(hooks.hook_paragraph_2);
      if (hooks.hook_paragraph_3) parts.push(hooks.hook_paragraph_3);
      parts.push('');
    }
    this._downloadMarkdown(parts.join('\n'), `${this.currentCompany}_draft.md`);
    this._toast('草稿 Markdown 导出成功', 'success');
  },

  _downloadMarkdown(markdown, filename) {
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
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
