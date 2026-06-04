/* layout-app.js — GZHv2 排版界面控制器
   加载 render-data → 选择卡片 → 选模板 → iframe 预览 → 区域调参 → 保存 layout */
const LayoutApp = {
  _company: '',
  _data: null,
  _cards: [],
  _activeCardId: null,
  _activeCard: null,
  _templates: [],
  _activeRegionId: null,
  _layoutOverrides: {},
  _scale: 1.0,

  async init() {
    const p = new URLSearchParams(window.location.search);
    this._company = p.get('company') || '';
    if (!this._company) {
      document.getElementById('canvas-area').innerHTML = '<div class="empty-state">缺少 ?company= 参数</div>';
      return;
    }

    document.getElementById('company-label').textContent = `排版 · ${this._company}`;
    this._setStatus('加载中');
    document.getElementById('btn-back-editor').href = `/editor?company=${encodeURIComponent(this._company)}`;
    document.getElementById('btn-template-maker').addEventListener('click', () => {
      window.open('/template-maker', '_blank');
    });
    document.getElementById('btn-export').addEventListener('click', () => this._exportPNG());
    document.getElementById('btn-apply-template').addEventListener('click', () => this._applyTemplate());
    document.getElementById('btn-save-layout').addEventListener('click', () => this._saveLayout());
    document.getElementById('btn-reset-layout').addEventListener('click', () => this._resetLayout());

    await this._loadData();
    await this._loadTemplates();
    this._renderCardList();
    this._renderTemplateSelect();
    // 自动选第一张卡片
    if (this._cards.length) this._selectCard(this._cards[0].card_id);
  },

  /* ── 数据加载 ── */
  async _loadData() {
    try {
      const r = await fetch(`/api/render-data/${encodeURIComponent(this._company)}`);
      if (!r.ok) throw new Error(`render-data ${r.status}`);
      this._data = await r.json();
      this._cards = this._data.cards || [];
      this._setStatus(`已加载 ${this._cards.length} 张卡`);
    } catch (e) {
      console.error('加载 render-data 失败:', e);
      this._cards = [];
      this._setStatus('加载失败');
    }
  },

  async _loadTemplates() {
    try {
      const r = await fetch('/api/svg-templates');
      const d = await r.json();
      this._templates = d.templates || [];
      // Fallback: also load from template repo
    } catch { this._templates = []; }
    try {
      const r2 = await fetch('/api/templates');
      if (r2.ok) {
        const d2 = await r2.json();
        this._templates = [...this._templates, ...(d2.templates || [])];
      }
    } catch { /* no /api/templates yet */ }
  },

  /* ── 左侧卡片列表 ── */
  _renderCardList() {
    const el = document.getElementById('card-list');
    el.innerHTML = this._cards.map(c => `
      <div class="layout-card-item" data-card-id="${c.card_id}" id="card-item-${c.card_id}">
        <span class="layout-card-idx">${c.card_index}</span>
        <span class="layout-card-title">${this._esc(c.card_title)}</span>
        <span class="layout-card-badge">${(c.items || []).length}项</span>
      </div>
    `).join('');

    el.querySelectorAll('.layout-card-item').forEach(item => {
      item.addEventListener('click', () => this._selectCard(item.dataset.cardId));
    });
  },

  _renderTemplateSelect() {
    const sel = document.getElementById('template-select');
    sel.innerHTML = '<option value="">-- 选择模板 --</option>' +
      this._templates.map(t => `<option value="${t.id || t.template_id}">${this._esc(t.name || t.template_name)}</option>`).join('');
  },

  /* ── 选择卡片 → 渲染预览 ── */
  _selectCard(cardId) {
    this._activeCardId = cardId;
    this._activeCard = this._cards.find(c => c.card_id === cardId);
    this._layoutOverrides = JSON.parse(JSON.stringify(this._activeCard?.layout?.overrides || {}));
    document.querySelectorAll('.layout-card-item').forEach(el =>
      el.classList.toggle('active', el.dataset.cardId === cardId));

    // 同步模板 select
    if (this._activeCard?.template_id) {
      document.getElementById('template-select').value = this._activeCard.template_id;
    }

    this._renderPreview();
    this._renderLayerList();
  },

  /* ── iframe 预览 ── */
  _renderPreview() {
    const area = document.getElementById('canvas-area');
    const card = this._activeCard;
    if (!card) {
      area.innerHTML = '<div class="empty-state">未选择卡片</div>';
      return;
    }

    const template = this._effectiveTemplate() || TemplateRenderer?.DEFAULT_TEMPLATE || {};
    const canvas = template.canvas || { width: 900, height: 1200 };
    const regions = template.regions || [];
    const overrides = this._layoutOverrides || {};

    // Apply overrides + cached text edits to regions for rendering
    const mergedRegions = regions.map(r => {
      const ov = overrides[r.id] || {};
      const merged = this._deepMerge({ ...r }, ov);
      // Preserve edited text content across iframe rebuilds
      if (this._regionTextCache?.[r.id]) {
        merged.value = this._regionTextCache[r.id];
      }
      return merged;
    });

    const renderCard = {
      ...card,
      template: { ...template, regions: mergedRegions },
      layout: { overrides: {} },
    };

    let html;
    if (typeof TemplateRenderer !== 'undefined') {
      html = TemplateRenderer.render(renderCard);
    } else {
      html = this._fallbackRender(renderCard);
    }

    // Inject editable text + region highlight support
    html = html.replace('</style>', `
      [data-od-id] { transition: box-shadow .15s; }
      [data-od-id].region-selected {
        box-shadow: inset 0 0 0 2px #29B8D4 !important;
        outline: 2px solid #29B8D4 !important; outline-offset: -1px;
      }
      [data-od-id][contenteditable]:focus {
        box-shadow: inset 0 0 0 2px #29B8D4 !important; outline: none;
      }
    </style>`);

    this._scale = Math.min(
      (area.clientWidth - 40) / canvas.width,
      (area.clientHeight - 40) / canvas.height,
      1.0
    );

    area.innerHTML = `<div class="canvas-stage" id="canvas-stage" style="width:${canvas.width * this._scale}px;height:${canvas.height * this._scale}px;position:relative">
      <iframe id="preview-iframe" srcdoc="${this._escAttr(html)}" style="width:${canvas.width}px;height:${canvas.height}px;transform:scale(${this._scale});transform-origin:top left;border:none"></iframe>
    </div>`;

    // After iframe loads, make text regions editable + bind region clicks
    const iframe = document.getElementById('preview-iframe');
    iframe.addEventListener('load', () => {
      this._setupIframeRegions(iframe, template);
    });
  },

  _setupIframeRegions(iframe, template) {
    try {
      const doc = iframe.contentDocument || iframe.contentWindow?.document;
      if (!doc) return;

      const regions = template.regions || [];
      const textRegions = regions.filter(r => r.type === 'text');

      // Make text regions contenteditable
      textRegions.forEach(r => {
        const el = doc.querySelector(`[data-od-id="${r.id}"]`);
        if (el && el.tagName !== 'IMG') {
          el.contentEditable = true;
          // Apply cached text content across iframe rebuilds
          if (this._regionTextCache?.[r.id]) {
            el.innerHTML = this._regionTextCache[r.id];
          }
          el.addEventListener('input', () => {
            if (!this._regionTextCache) this._regionTextCache = {};
            this._regionTextCache[r.id] = el.innerHTML;
          });
          el.addEventListener('blur', () => {
            const html = this._regionTextCache?.[r.id];
            if (html && this._activeCard) {
              this._layoutOverrides[r.id] = this._deepMerge(
                this._layoutOverrides[r.id] || {},
                { value: html }
              );
              this._activeCard.layout = {
                ...(this._activeCard.layout || {}),
                overrides: this._layoutOverrides,
              };
            }
          });
        }
      });

      this._refreshRegionHighlight(doc);
    } catch (e) { /* cross-origin iframe access */ }
  },

  _refreshRegionHighlight(doc) {
    if (!doc) return;
    doc.querySelectorAll('.region-selected').forEach(el => el.classList.remove('region-selected'));
    if (this._activeRegionId) {
      const el = doc.querySelector(`[data-od-id="${this._activeRegionId}"]`);
      if (el) el.classList.add('region-selected');
    }
  },

  _bindRegionClicks() {
    // Now handled by _setupIframeRegions
  },

  _fallbackRender(card) {
    const items = card.items || [];
    const fields = items.filter(i => i.item_type === 'field').map(i => `<p>${this._esc(i.value || '')}</p>`).join('');
    return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{width:900px;height:1200px;background:#fff;font-family:sans-serif;padding:68px}</style></head><body><h1>${this._esc(card.card_title)}</h1>${fields}</body></html>`;
  },

  _effectiveTemplate() {
    const base = this._activeCard?.template || TemplateRenderer?.DEFAULT_TEMPLATE || {};
    const regions = (base.regions || []).map(region => {
      const override = this._layoutOverrides[region.id];
      return override ? this._deepMerge(region, override) : region;
    });
    return { ...base, regions };
  },

  _deepMerge(base, override) {
    const result = { ...(base || {}) };
    Object.entries(override || {}).forEach(([key, value]) => {
      if (value && typeof value === 'object' && !Array.isArray(value) && result[key] && typeof result[key] === 'object') {
        result[key] = this._deepMerge(result[key], value);
      } else {
        result[key] = value;
      }
    });
    return result;
  },

  /* ── 区域点击 → 属性面板 ── */
  _bindRegionClicks() {
    // 绑定 iframe 内区域点击（如果有的话）；不做任何会清除选中状态的事
  },

  /* ── 图层列表 ── */
  _renderLayerList() {
    const el = document.getElementById('layer-list');
    const template = this._effectiveTemplate();
    const regions = template.regions || [];
    el.innerHTML = regions.map((r, i) => `
      <div class="layer-item${r.id === this._activeRegionId ? ' active' : ''}" data-region-id="${r.id}">
        <span class="layer-dot" style="background:${r.type==='text'?'#29B8D4':r.type==='image'?'#81C784':'#C4B5FD'}"></span>
        <span class="layer-name">${this._esc(r.id)}</span>
        <span class="layer-role">${r.role || r.type || ''}</span>
      </div>
    `).join('');

    el.querySelectorAll('.layer-item').forEach(item => {
      item.addEventListener('click', () => {
        this._selectRegion(item.dataset.regionId);
      });
    });
  },

  _selectRegion(regionId) {
    this._activeRegionId = regionId;
    // 更新图层列表 active 状态
    document.querySelectorAll('.layer-item').forEach(li =>
      li.classList.toggle('active', li.dataset.regionId === regionId));
    const template = this._effectiveTemplate();
    const region = (template.regions || []).find(r => r.id === regionId);
    this._renderPropertyPanel(region);
    // 高亮 iframe 中的区域
    const iframe = document.getElementById('preview-iframe');
    if (iframe) {
      try {
        const doc = iframe.contentDocument || iframe.contentWindow?.document;
        this._refreshRegionHighlight(doc);
      } catch (e) { /* cross-origin */ }
    }
  },

  /* ── 属性面板 ── */
  _renderPropertyPanel(region) {
    const el = document.getElementById('property-panel');
    if (!region) {
      el.innerHTML = '<div class="empty-state">选择图层查看属性</div>';
      return;
    }

    const s = region.style || {};
    const fontFamilies = ['Noto Sans SC', 'Instrument Sans', 'Bebas Neue', 'IBM Plex Mono', 'DM Serif Display'];

    el.innerHTML = `
      <label>ID: <strong>${this._esc(region.id)}</strong> (${region.type} / ${region.role || '-'})</label>
      <div class="prop-row">
        <label>X <input type="number" value="${region.x}" data-key="x" data-rid="${region.id}" onchange="LayoutApp._onPropChange(this)"></label>
        <label>Y <input type="number" value="${region.y}" data-key="y" data-rid="${region.id}" onchange="LayoutApp._onPropChange(this)"></label>
      </div>
      <div class="prop-row">
        <label>W <input type="number" value="${region.w}" data-key="w" data-rid="${region.id}" onchange="LayoutApp._onPropChange(this)"></label>
        <label>H <input type="number" value="${region.h}" data-key="h" data-rid="${region.id}" onchange="LayoutApp._onPropChange(this)"></label>
      </div>
      ${region.type === 'text' ? `
        <label>字体 <select data-key="fontFamily" data-rid="${region.id}" onchange="LayoutApp._onPropChange(this)" style="width:100%">
          ${fontFamilies.map(f => `<option ${s.fontFamily===f?'selected':''}>${f}</option>`).join('')}
        </select></label>
        <div class="prop-row">
          <label>字号 <input type="range" min="10" max="96" value="${s.fontSize||24}" data-key="fontSize" data-rid="${region.id}" oninput="LayoutApp._onPropChange(this)"><span style="font-size:10px">${s.fontSize||24}</span></label>
        </div>
        <div class="prop-row">
          <label>字重 <input type="range" min="100" max="900" step="100" value="${s.fontWeight||400}" data-key="fontWeight" data-rid="${region.id}" oninput="LayoutApp._onPropChange(this)"><span style="font-size:10px">${s.fontWeight||400}</span></label>
        </div>
        <label>颜色 <input type="color" value="${s.color||'#111111'}" data-key="color" data-rid="${region.id}" onchange="LayoutApp._onPropChange(this)"></label>
        <label>行高 <input type="number" step="0.1" min="1" max="3" value="${s.lineHeight||1.5}" data-key="lineHeight" data-rid="${region.id}" onchange="LayoutApp._onPropChange(this)"></label>
      ` : ''}
      ${region.type === 'image' || region.type === 'chart' ? `
        <label>圆角 <input type="range" min="0" max="40" value="${s.borderRadius||0}" data-key="borderRadius" data-rid="${region.id}" oninput="LayoutApp._onPropChange(this)"><span style="font-size:10px">${s.borderRadius||0}</span></label>
        <label>适应方式 <select data-key="objectFit" data-rid="${region.id}" onchange="LayoutApp._onPropChange(this)">
          <option ${s.objectFit==='contain'?'selected':''}>contain</option>
          <option ${s.objectFit==='cover'?'selected':''}>cover</option>
        </select></label>
      ` : ''}
      <label>透明度 <input type="range" min="0" max="1" step="0.05" value="${s.opacity||1}" data-key="opacity" data-rid="${region.id}" oninput="LayoutApp._onPropChange(this)"><span style="font-size:10px">${s.opacity||1}</span></label>
    `;
  },

  _onPropChange(el) {
    const rid = el.dataset.rid;
    const key = el.dataset.key;
    let val = el.value;
    if (el.type === 'range' || el.type === 'number') val = parseFloat(val);

    const region = (this._effectiveTemplate().regions || []).find(r => r.id === rid);
    if (!region) return;

    const geometryKeys = new Set(['x', 'y', 'w', 'h']);
    const patch = geometryKeys.has(key)
      ? { [key]: val }
      : { style: { [key]: val } };
    this._layoutOverrides[rid] = this._deepMerge(this._layoutOverrides[rid] || {}, patch);
    this._activeCard.layout = {
      ...(this._activeCard.layout || {}),
      overrides: this._layoutOverrides,
    };

    // Range sliders: debounce preview. Number/color: immediate.
    if (el.type === 'range') {
      clearTimeout(this._previewDebounce);
      this._previewDebounce = setTimeout(() => this._renderPreview(), 60);
    } else {
      this._renderPreview();
    }
    // Keep active region visible in layer list without rebuilding property panel
    document.querySelectorAll('.layer-item').forEach(li =>
      li.classList.toggle('active', li.dataset.regionId === this._activeRegionId));
    // Update the displayed value text next to range sliders
    const valSpan = el.nextElementSibling;
    if (valSpan && el.type === 'range') valSpan.textContent = el.value;
  },

  /* ── 应用模板 ── */
  async _applyTemplate() {
    const tid = document.getElementById('template-select').value;
    if (!tid || !this._activeCardId) return;

    // 更新 card_compositions 的 template_id
    try {
      await fetch(`/api/card-config/${encodeURIComponent(this._company)}/cards/${encodeURIComponent(this._activeCardId)}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: tid }),
      });
      await this._loadData();
      this._selectCard(this._activeCardId);
    } catch (e) { alert('应用失败: ' + e.message); }
  },

  /* ── 保存排版 ── */
  async _saveLayout() {
    if (!this._activeCardId) return;
    try {
      const r = await fetch(`/api/layout/${encodeURIComponent(this._company)}/${encodeURIComponent(this._activeCardId)}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ overrides: this._layoutOverrides }),
      });
      if (r.ok) {
        alert('排版已保存');
      }
    } catch (e) { alert('保存失败: ' + e.message); }
  },

  async _resetLayout() {
    if (!this._activeCardId) return;
    if (!confirm('重置当前卡片排版到模板默认值？')) return;
    try {
      await fetch(`/api/layout/${encodeURIComponent(this._company)}/${encodeURIComponent(this._activeCardId)}/reset`, { method: 'POST' });
      await this._loadData();
      this._selectCard(this._activeCardId);
    } catch (e) { alert('重置失败: ' + e.message); }
  },

  _exportPNG() {
    this._showExportDialog();
  },

  _showExportDialog() {
    if (document.getElementById('export-dialog-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'export-dialog-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;display:flex;align-items:center;justify-content:center';
    overlay.innerHTML = `
      <div style="background:var(--surface-1, #fff);border-radius:12px;padding:24px;min-width:360px;max-width:420px;box-shadow:0 8px 40px rgba(0,0,0,.2)">
        <h3 style="margin:0 0 16px;font-size:16px;color:var(--text, #1B2A4A)">导出卡片</h3>
        <div style="display:flex;flex-direction:column;gap:14px">
          <label style="font-size:13px;color:var(--text-muted, #556B82)">
            导出范围
            <select id="export-range" style="width:100%;margin-top:4px;padding:6px 8px;border:1px solid var(--border, #E2E4E9);border-radius:6px;font-size:13px">
              <option value="current">当前卡片</option>
              <option value="all">全部启用卡片</option>
            </select>
          </label>
          <label style="font-size:13px;color:var(--text-muted, #556B82)">
            格式
            <select id="export-format" style="width:100%;margin-top:4px;padding:6px 8px;border:1px solid var(--border, #E2E4E9);border-radius:6px;font-size:13px">
              <option value="png">PNG（单个文件）</option>
              <option value="zip">ZIP（打包下载）</option>
            </select>
          </label>
          <label style="font-size:13px;color:var(--text-muted, #556B82)">
            倍率
            <select id="export-scale" style="width:100%;margin-top:4px;padding:6px 8px;border:1px solid var(--border, #E2E4E9);border-radius:6px;font-size:13px">
              <option value="1">1x</option>
              <option value="2" selected>2x</option>
              <option value="3">3x</option>
            </select>
          </label>
        </div>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:20px">
          <button id="export-dialog-cancel" style="padding:7px 16px;border:1px solid var(--border, #E2E4E9);border-radius:6px;background:var(--surface-1, #fff);font-size:13px;cursor:pointer">取消</button>
          <button id="export-dialog-confirm" style="padding:7px 20px;border:none;border-radius:6px;background:var(--cyan, #29B8D4);color:#fff;font-size:13px;font-weight:600;cursor:pointer">开始导出</button>
        </div>
      </div>`;

    document.body.appendChild(overlay);

    overlay.querySelector('#export-dialog-cancel').onclick = () => overlay.remove();
    overlay.querySelector('#export-dialog-confirm').onclick = () => {
      const range = document.getElementById('export-range').value;
      const format = document.getElementById('export-format').value;
      const scale = parseInt(document.getElementById('export-scale').value);
      overlay.remove();
      this._startExport({ range, format, scale });
    };
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
  },

  async _startExport(opts = {}) {
    try {
      this._setStatus('导出中');
      const payload = {
        card_ids: opts.range === 'current' && this._activeCardId ? [this._activeCardId] : undefined,
        format: opts.format || 'png',
        scale: opts.scale || 2,
      };
      const r = await fetch(`/api/export/${encodeURIComponent(this._company)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const job = await r.json();
      if (!r.ok) throw new Error(job.error || `export ${r.status}`);
      await this._pollExport(job.job_id);
    } catch (e) {
      this._setStatus('导出失败');
      alert('导出失败: ' + e.message);
    }
  },

  async _pollExport(jobId) {
    for (let i = 0; i < 80; i += 1) {
      await new Promise(resolve => setTimeout(resolve, 800));
      const r = await fetch(`/api/export/${encodeURIComponent(this._company)}/jobs/${encodeURIComponent(jobId)}`);
      const job = await r.json();
      if (!r.ok) throw new Error(job.error || `job ${r.status}`);
      if (job.status === 'done') {
        this._setStatus('导出完成');
        window.open(job.download_url, '_blank');
        return;
      }
      if (job.status === 'failed') throw new Error(job.error || '导出任务失败');
      this._setStatus(`导出中 ${i + 1}`);
    }
    throw new Error('导出超时');
  },

  _setStatus(text) {
    const el = document.getElementById('layout-status');
    if (el) el.textContent = text;
  },

  _esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); },
  _escAttr(s) { return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;'); },
};

document.addEventListener('DOMContentLoaded', () => LayoutApp.init());
