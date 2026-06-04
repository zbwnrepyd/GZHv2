/* text-finalize-panel.js — 文字定稿面板
   功能：按字段分组，三版本对比，点击采用，编辑定稿 */

const VERSION_LABELS_TF = { standard: '标准版', business: '商业版', spread: '传播版' };

const TextFinalizePanel = {
  _company: '',
  _groups: [],

  async init(company) {
    if (this._loaded && this._company === company) return;
    this._company = company;
    await this._loadFields();
    this._render();
    this._loaded = true;
  },

  async _loadFields() {
    try {
      const r = await fetch(`/api/fields/${encodeURIComponent(this._company)}`);
      const d = await r.json();
      this._groups = d.groups || [];
    } catch { this._groups = []; }
  },

  _render() {
    const root = document.getElementById('text-finalize-mode-content');
    if (!root) return;

    const confirmedCount = this._groups.reduce((sum, g) =>
      sum + (g.fields || []).filter(f => f.status === 'confirmed').length, 0);
    const totalCount = this._groups.reduce((sum, g) => sum + (g.fields || []).length, 0);

    root.innerHTML = `
      <div class="tf-top-bar">
        <span class="tf-progress">${confirmedCount}/${totalCount} 已定稿</span>
        <button class="tf-btn-confirm-all" id="tf-btn-confirm-all">全部定稿</button>
      </div>
      <div class="tf-groups">
        ${this._groups.map(g => this._groupSection(g)).join('')}
      </div>
    `;

    document.getElementById('tf-btn-confirm-all')?.addEventListener('click', () => this._confirmAll());
    this._bindRowEvents();
  },

  _groupSection(group) {
    const fields = group.fields || [];
    return `
      <div class="tf-group">
        <h3 class="tf-group-title">${this._esc(group.group_label)}</h3>
        <div class="tf-fields">
          ${fields.map(f => this._fieldCard(f)).join('')}
        </div>
      </div>`;
  },

  _fieldCard(field) {
    const versions = field.versions || {};
    const finalVal = field.final_value || '';
    const confirmed = field.status === 'confirmed';
    const hasVersions = Object.keys(versions).length > 0;

    return `
      <div class="tf-field-card ${confirmed ? 'confirmed' : ''}" data-field="${field.field_key}">
        <div class="tf-field-head">
          <span class="tf-field-label">${this._esc(field.field_label)}</span>
          <span class="tf-field-dot ${confirmed ? 'confirmed' : 'draft'}" title="${confirmed ? '已定稿' : '未定稿'}"></span>
        </div>

        ${hasVersions ? `
        <div class="tf-versions">
          ${Object.entries(versions).map(([ver, val]) => `
            <div class="tf-version-card" data-field="${field.field_key}" data-value="${this._escAttr(val)}"
                 title="点击采用${VERSION_LABELS_TF[ver] || ver}版本">
              <span class="tf-ver-tag">${VERSION_LABELS_TF[ver] || ver}</span>
              <p class="tf-ver-text">${this._esc(val)}</p>
            </div>
          `).join('')}
        </div>` : '<p class="tf-empty-hint">暂无研究数据</p>'}

        <div class="tf-final-area">
          <textarea class="tf-final-input" data-field="${field.field_key}" rows="2"
            placeholder="输入定稿内容...">${this._esc(finalVal)}</textarea>
          <button class="tf-save-btn" data-field-key="${field.field_key}">保存</button>
        </div>
      </div>`;
  },

  _bindRowEvents() {
    // 采用：点击版本卡片
    document.querySelectorAll('.tf-version-card').forEach(card => {
      card.addEventListener('click', () => {
        const fieldKey = card.dataset.field;
        const value = card.dataset.value || '';
        const textarea = document.querySelector(`.tf-final-input[data-field="${fieldKey}"]`);
        if (textarea) {
          textarea.value = value;
          textarea.classList.add('dirty');
          textarea.focus();
        }
      });
    });

    // 保存
    document.querySelectorAll('.tf-save-btn').forEach(btn => {
      btn.addEventListener('click', () => this._saveField(btn.dataset.fieldKey));
    });
  },

  async _saveField(fieldKey) {
    const textarea = document.querySelector(`.tf-final-input[data-field="${fieldKey}"]`);
    if (!textarea) return;
    const value = textarea.value.trim();

    try {
      const r = await fetch(`/api/fields/${encodeURIComponent(this._company)}/${encodeURIComponent(fieldKey)}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ final_value: value, status: 'confirmed' }),
      });
      if (r.ok) {
        const card = document.querySelector(`.tf-field-card[data-field="${fieldKey}"]`);
        if (card) { card.classList.add('confirmed'); card.classList.remove('draft'); }
        const dot = card?.querySelector('.tf-field-dot');
        if (dot) { dot.classList.add('confirmed'); dot.classList.remove('draft'); }
        textarea.classList.remove('dirty');
        // Update progress
        const confirmedCount = document.querySelectorAll('.tf-field-card.confirmed').length;
        const totalCount = document.querySelectorAll('.tf-field-card').length;
        const progress = document.querySelector('.tf-progress');
        if (progress) progress.textContent = `${confirmedCount}/${totalCount} 已定稿`;
      }
    } catch (e) { /* non-blocking */ }
  },

  async _confirmAll() {
    if (!confirm('确定将所有已填写的字段标记为已定稿？')) return;
    try {
      const fieldValues = {};
      document.querySelectorAll('.tf-final-input').forEach(ta => {
        const key = ta.dataset.field;
        if (key && ta.value.trim()) fieldValues[key] = ta.value.trim();
      });
      await fetch(`/api/fields/${encodeURIComponent(this._company)}/confirm`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ field_values: fieldValues }),
      });
      await this._loadFields();
      this._render();
    } catch (e) { alert('保存失败: ' + e.message); }
  },

  _esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); },
  _escAttr(s) { return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); },
};
