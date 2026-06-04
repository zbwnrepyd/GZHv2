/* card-settings-panel.js — GZHv2 卡片设置面板
   功能：卡片列表增删改排序 + 字段/图片分配到卡片 */
const CardSettingsPanel = {
  _company: '',
  _cards: [],
  _availableFields: [],
  _availableMedia: [],

  async init(company) {
    if (this._loaded && this._company === company) return;
    this._company = company;
    await this._loadCards();
    await this._loadPools();
    this._render();
    this._loaded = true;
  },

  /* ── 数据加载 ── */
  async _loadCards() {
    try {
      const r = await fetch(`/api/card-config/${encodeURIComponent(this._company)}`);
      const d = await r.json();
      this._cards = d.cards || [];
    } catch { this._cards = []; }
  },

  async _loadPools() {
    try {
      const [fr, mr] = await Promise.all([
        fetch(`/api/fields/${encodeURIComponent(this._company)}`),
        fetch(`/api/media/${encodeURIComponent(this._company)}`),
      ]);
      const fd = await fr.json();
      const md = await mr.json();
      this._availableFields = [];
      (fd.groups || []).forEach(g => {
        (g.fields || []).forEach(f => {
          this._availableFields.push({ field_key: f.field_key, field_label: f.field_label, group_key: g.group_key });
        });
      });
      this._availableMedia = (md.media || md.slots || []).map(s => ({
        media_key: s.media_key || s.asset_key,
        label: s.media_label || s.label || s.media_key || s.asset_key,
      })).filter(m => m.media_key);
    } catch { this._availableFields = []; this._availableMedia = []; }
  },

  /* ── 渲染 ── */
  _render() {
    const root = document.getElementById('card-settings-mode-content');
    if (!root) return;

    root.innerHTML = `
      <div class="cs-toolbar">
        <button class="cs-btn-add" id="cs-btn-add-card">+ 新增卡片</button>
        <span class="cs-card-count">${this._cards.length} 张卡片</span>
      </div>
      <div class="cs-card-list" id="cs-card-list">
        ${this._cards.map((c, i) => this._cardRow(c, i)).join('')}
      </div>
      <div id="cs-card-editor" class="cs-card-editor hidden"></div>
    `;

    document.getElementById('cs-btn-add-card')?.addEventListener('click', () => this._showAddCard());
    document.querySelectorAll('.cs-card-row').forEach(row => {
      row.addEventListener('click', () => this._editCard(row.dataset.cardId));
    });
    document.querySelectorAll('.cs-card-delete').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this._deleteCard(btn.dataset.cardId);
      });
    });
  },

  _cardRow(card, index) {
    const items = card.items || [];
    const nf = items.filter(i => i.item_type === 'field').length;
    const nm = items.filter(i => i.item_type === 'media').length;
    const cls = card.enabled ? '' : 'disabled';
    return `
      <div class="cs-card-row ${cls}" data-card-id="${card.card_id}">
        <span class="cs-card-index">${card.card_index}</span>
        <span class="cs-card-title">${this._esc(card.card_title)}</span>
        <span class="cs-card-meta">${nf}字段 + ${nm}素材</span>
        <span class="cs-card-template">${this._esc(card.template_id || '无模板')}</span>
        <button class="cs-card-delete" data-card-id="${card.card_id}">×</button>
      </div>`;
  },

  /* ── 新增/编辑卡片 ── */
  _showAddCard() {
    const editor = document.getElementById('cs-card-editor');
    if (!editor) return;
    const maxIdx = this._cards.reduce((m, c) => Math.max(m, c.card_index || 0), 0);
    const cardId = `card_${String(maxIdx + 1).padStart(2, '0')}`;

    editor.classList.remove('hidden');
    editor.innerHTML = `
      <h4>新增卡片</h4>
      <div class="cs-form">
        <label>卡片ID <input id="cs-edit-id" value="${cardId}"></label>
        <label>卡片名称 <input id="cs-edit-title" placeholder="例如：团队介绍"></label>
        <label>排序 <input id="cs-edit-index" type="number" value="${maxIdx + 1}" min="1"></label>
        <label>模板 <input id="cs-edit-template" placeholder="留空使用默认"></label>
      </div>
      <div class="cs-pool-section">
        <h5>可选字段</h5>
        <div class="cs-pool-grid" id="cs-field-pool">
          ${this._availableFields.map(f => `<label class="cs-pool-item"><input type="checkbox" value="${f.field_key}"> ${this._esc(f.field_label)}</label>`).join('')}
        </div>
        <h5>可选图片</h5>
        <div class="cs-pool-grid" id="cs-media-pool">
          ${this._availableMedia.map(m => `<label class="cs-pool-item"><input type="checkbox" value="${m.media_key}"> ${this._esc(m.label || m.media_key)}</label>`).join('')}
        </div>
      </div>
      <div class="cs-form-actions">
        <button id="cs-btn-save">保存</button>
        <button id="cs-btn-cancel">取消</button>
      </div>
    `;

    document.getElementById('cs-btn-save')?.addEventListener('click', () => this._saveNewCard());
    document.getElementById('cs-btn-cancel')?.addEventListener('click', () => {
      editor.classList.add('hidden');
      editor.innerHTML = '';
    });
  },

  async _saveNewCard() {
    const cardId = document.getElementById('cs-edit-id')?.value || '';
    const title = document.getElementById('cs-edit-title')?.value || '';
    const index = parseInt(document.getElementById('cs-edit-index')?.value || '99');
    const template = document.getElementById('cs-edit-template')?.value || '';

    if (!cardId || !title) return alert('请填写卡片ID和名称');

    try {
      const r = await fetch(`/api/card-config/${encodeURIComponent(this._company)}/cards`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ card_id: cardId, card_title: title, card_index: index, template_id: template }),
      });
      if (!r.ok) throw new Error((await r.json()).error);

      // Add selected items
      const fields = [...document.querySelectorAll('#cs-field-pool input:checked')].map(el => el.value);
      const media = [...document.querySelectorAll('#cs-media-pool input:checked')].map(el => el.value);

      for (let i = 0; i < fields.length; i++) {
        await fetch(`/api/card-config/${encodeURIComponent(this._company)}/cards/${encodeURIComponent(cardId)}/items`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ item_type: 'field', item_key: fields[i], sort_order: i }),
        });
      }
      for (let i = 0; i < media.length; i++) {
        await fetch(`/api/card-config/${encodeURIComponent(this._company)}/cards/${encodeURIComponent(cardId)}/items`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ item_type: 'media', item_key: media[i], sort_order: i + 100, display_role: 'hero_image' }),
        });
      }

      document.getElementById('cs-card-editor')?.classList.add('hidden');
      await this._loadCards();
      this._render();
    } catch (e) { alert('保存失败: ' + e.message); }
  },

  _editCard(cardId) {
    const card = this._cards.find(c => c.card_id === cardId);
    if (!card) return;
    const editor = document.getElementById('cs-card-editor');
    if (!editor) return;
    editor._editingCardId = cardId;

    const items = card.items || [];
    const fieldItems = items.filter(i => i.item_type === 'field');
    const mediaItems = items.filter(i => i.item_type === 'media');

    editor.classList.remove('hidden');
    editor.innerHTML = `
      <h4>编辑卡片：${this._esc(card.card_title)}</h4>
      <div class="cs-form">
        <label>卡片ID <input id="cs-edit-id" value="${cardId}" disabled style="opacity:.6"></label>
        <label>卡片名称 <input id="cs-edit-title" value="${this._esc(card.card_title)}"></label>
        <label>排序 <input id="cs-edit-index" type="number" value="${card.card_index || 0}" min="1"></label>
        <label>模板 <input id="cs-edit-template" value="${this._esc(card.template_id || '')}" placeholder="留空使用默认"></label>
        <label class="cs-check-label"><input type="checkbox" id="cs-edit-enabled" ${card.enabled !== false ? 'checked' : ''}> 启用</label>
      </div>
      <div class="cs-pool-section">
        <h5>字段 <span style="font-weight:400;font-size:11px;color:var(--text-muted)">（勾选即添加，取消勾选即移除）</span></h5>
        <div class="cs-pool-grid" id="cs-field-pool">
          ${this._availableFields.map(f => {
            const existing = fieldItems.find(i => i.item_key === f.field_key);
            return `<label class="cs-pool-item"><input type="checkbox" value="${f.field_key}" ${existing ? 'checked' : ''}> ${this._esc(f.field_label)}</label>`;
          }).join('')}
        </div>
        <h5>图片 <span style="font-weight:400;font-size:11px;color:var(--text-muted)">（勾选即添加，取消勾选即移除）</span></h5>
        <div class="cs-pool-grid" id="cs-media-pool">
          ${this._availableMedia.map(m => {
            const existing = mediaItems.find(i => i.item_key === m.media_key);
            return `<label class="cs-pool-item"><input type="checkbox" value="${m.media_key}" ${existing ? 'checked' : ''}> ${this._esc(m.label || m.media_key)}</label>`;
          }).join('')}
        </div>
      </div>
      <div class="cs-form-actions">
        <button id="cs-btn-save">保存修改</button>
        <button id="cs-btn-cancel">取消</button>
      </div>
    `;

    document.getElementById('cs-btn-save')?.addEventListener('click', () => this._saveEditCard());
    document.getElementById('cs-btn-cancel')?.addEventListener('click', () => {
      editor.classList.add('hidden');
      editor.innerHTML = '';
      delete editor._editingCardId;
    });
    editor.scrollIntoView({ behavior: 'smooth' });
  },

  async _saveEditCard() {
    const editor = document.getElementById('cs-card-editor');
    const cardId = editor._editingCardId;
    if (!cardId) return;

    const title = document.getElementById('cs-edit-title')?.value || '';
    const index = parseInt(document.getElementById('cs-edit-index')?.value || '99');
    const template = document.getElementById('cs-edit-template')?.value || '';
    const enabled = document.getElementById('cs-edit-enabled')?.checked;

    try {
      // Update card metadata
      const r = await fetch(`/api/card-config/${encodeURIComponent(this._company)}/cards/${encodeURIComponent(cardId)}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ card_title: title, card_index: index, template_id: template, enabled }),
      });
      if (!r.ok) throw new Error((await r.json()).error);

      // Sync items: batch replace
      const fieldKeys = [...document.querySelectorAll('#cs-field-pool input:checked')].map(el => el.value);
      const mediaKeys = [...document.querySelectorAll('#cs-media-pool input:checked')].map(el => el.value);

      const items = [];
      fieldKeys.forEach((key, i) => {
        items.push({ item_type: 'field', item_key: key, sort_order: i, display_role: 'body' });
      });
      mediaKeys.forEach((key, i) => {
        items.push({ item_type: 'media', item_key: key, sort_order: i + 100, display_role: 'hero_image' });
      });

      await fetch(`/api/card-config/${encodeURIComponent(this._company)}/cards/${encodeURIComponent(cardId)}/items/batch`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items }),
      });

      editor.classList.add('hidden');
      editor.innerHTML = '';
      delete editor._editingCardId;
      await this._loadCards();
      this._render();
    } catch (e) { alert('保存失败: ' + e.message); }
  },

  async _deleteCard(cardId) {
    if (!confirm(`确定删除卡片 ${cardId}？`)) return;
    try {
      await fetch(`/api/card-config/${encodeURIComponent(this._company)}/cards/${encodeURIComponent(cardId)}`, { method: 'DELETE' });
      await this._loadCards();
      this._render();
    } catch (e) { alert('删除失败: ' + e.message); }
  },

  _esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); },
};
