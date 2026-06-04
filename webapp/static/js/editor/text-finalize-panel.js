/* text-finalize-panel.js — GZHv2 字段定稿面板
   功能：按字段分组展示三版本内容，支持编辑定稿 */
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

    root.innerHTML = `
      <div class="ff-actions">
        <button class="ff-btn-confirm-all" id="ff-btn-confirm-all">全部定稿</button>
      </div>
      <div class="ff-groups" id="ff-groups">
        ${this._groups.map(g => this._groupSection(g)).join('')}
      </div>
    `;

    document.getElementById('ff-btn-confirm-all')?.addEventListener('click', () => this._confirmAll());
    document.querySelectorAll('.ff-use-version-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const fieldKey = btn.dataset.field;
        const value = btn.dataset.value || '';
        const textarea = document.querySelector(`.ff-final-input[data-field="${fieldKey}"]`);
        if (textarea) { textarea.value = value; textarea.classList.add('dirty'); }
      });
    });
    document.querySelectorAll('.ff-save-btn').forEach(btn => {
      btn.addEventListener('click', () => this._saveField(btn.dataset.fieldKey));
    });
  },

  _groupSection(group) {
    return `
      <div class="ff-group">
        <h4 class="ff-group-title">${this._esc(group.group_label)}</h4>
        ${group.fields.map(f => this._fieldRow(f)).join('')}
      </div>`;
  },

  _fieldRow(field) {
    const versions = field.versions || {};
    const finalVal = field.final_value || '';
    const statusCls = field.status === 'confirmed' ? 'confirmed' : 'draft';
    const hasVersions = Object.keys(versions).length > 0;

    return `
      <div class="ff-field-row ${statusCls}" data-field="${field.field_key}">
        <div class="ff-field-header">
          <span class="ff-field-label">${this._esc(field.field_label)}</span>
          <span class="ff-field-key">${field.field_key}</span>
          <span class="ff-field-type">${field.type}</span>
          <span class="ff-status-dot ${statusCls}"></span>
        </div>
        ${hasVersions ? `
        <div class="ff-versions">
          ${Object.entries(versions).map(([ver, val]) => `
            <div class="ff-version-row" data-ver="${ver}">
              <span class="ff-ver-label">${ver}</span>
              <span class="ff-ver-value" title="${this._esc(val)}">${this._esc(val).substring(0, 120)}</span>
              <button class="ff-use-version-btn" data-field="${field.field_key}" data-value="${this._escAttr(val)}">采用</button>
            </div>
          `).join('')}
        </div>` : ''}
        <div class="ff-final-row">
          <textarea class="ff-final-input" data-field="${field.field_key}" rows="3" placeholder="定稿内容...">${this._esc(finalVal)}</textarea>
          <button class="ff-save-btn" data-field-key="${field.field_key}">保存</button>
        </div>
      </div>`;
  },

  async _saveField(fieldKey) {
    const textarea = document.querySelector(`.ff-final-input[data-field="${fieldKey}"]`);
    if (!textarea) return;
    const value = textarea.value.trim();

    try {
      const r = await fetch(`/api/fields/${encodeURIComponent(this._company)}/${encodeURIComponent(fieldKey)}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ final_value: value, status: 'confirmed' }),
      });
      if (r.ok) {
        const dot = document.querySelector(`.ff-field-row[data-field="${fieldKey}"] .ff-status-dot`);
        if (dot) { dot.classList.remove('draft'); dot.classList.add('confirmed'); }
      }
    } catch (e) { /* non-blocking */ }
  },

  async _confirmAll() {
    if (!confirm('确定将所有字段标记为已定稿？')) return;
    try {
      const fieldValues = {};
      document.querySelectorAll('.ff-final-input').forEach(ta => {
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
