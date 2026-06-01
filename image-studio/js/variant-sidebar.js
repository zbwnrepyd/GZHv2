/* variant-sidebar.js — 变体库 + 定稿预览 + 导入区 + AI 生图面板 */
const VariantSidebar = {
  _company: '',
  _assetKey: '',
  _variants: [],
  _onSelect: null,
  _rendered: false,

  init(container, { onSelect }) {
    this._container = container;
    this._onSelect = onSelect;
  },

  _ensureRendered() {
    if (!this._container || this._rendered) return;
    this._container.innerHTML = `
      <h3>操作</h3>
      <div class="sidebar-actions" id="sidebar-actions"></div>
      <div class="svg-render-row hidden" id="svg-render-row">
        <button class="svg-render-btn-sidebar">生成当前参数 SVG</button>
      </div>
      <div class="selected-preview">
        <h4>当前选定</h4>
        <img src="" alt="" style="display:none">
        <div class="empty-preview" style="font-size:12px;color:var(--ink-muted)">未选择</div>
      </div>
      <div class="import-section">
        <div class="import-row">
          <input class="import-url-input" type="text" placeholder="粘贴图片 URL...">
          <button class="import-btn url-btn">下载</button>
        </div>
        <div class="import-row">
          <input type="file" accept="image/*" style="display:none" class="file-input">
          <button class="import-btn upload-btn">上传本地图片</button>
        </div>
      </div>
    `;

    // SVG 按钮
    this._container.querySelector('.svg-render-btn-sidebar')?.addEventListener('click', () => {
      if (window.StudioApp) StudioApp._renderSvg();
    });

    // 导入事件
    this._container.querySelector('.url-btn').addEventListener('click', () => this._importUrl());
    this._container.querySelector('.import-url-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this._importUrl();
    });
    this._container.querySelector('.upload-btn').addEventListener('click', () => {
      this._container.querySelector('.file-input').click();
    });
    this._container.querySelector('.file-input').addEventListener('change', (e) => {
      if (e.target.files[0]) this._importFile(e.target.files[0]);
    });

    this._rendered = true;
  },

  _renderActions() {
    const el = this._container?.querySelector('#sidebar-actions');
    if (!el) return;

    const isOffice = this._assetKey === 'office';

    el.innerHTML = `
      <div class="ai-gen-row">
        <input class="ai-prompt-input" type="text" placeholder="AI 生图 prompt...">
        <button class="ai-gen-btn">生成</button>
      </div>
      ${isOffice ? '<button class="btn-generate-map" id="btn-generate-map">生成地图</button>' : ''}
    `;

    el.querySelector('.ai-gen-btn')?.addEventListener('click', () => {
      const prompt = el.querySelector('.ai-prompt-input').value.trim();
      if (prompt) this._onAiGenerate(prompt);
    });
    el.querySelector('.ai-prompt-input')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const prompt = e.target.value.trim();
        if (prompt) this._onAiGenerate(prompt);
      }
    });
    const mapBtn = el.querySelector('#btn-generate-map');
    if (mapBtn) {
      mapBtn.addEventListener('click', () => this._onGenerateMap());
    }
  },

  async _onAiGenerate(prompt) {
    const el = this._container?.querySelector('#sidebar-actions');
    const btn = el?.querySelector('.ai-gen-btn');
    if (btn) { btn.disabled = true; btn.textContent = '生成中...'; }
    try {
      const result = await fetch('/api/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt, company_name: this._company,
          field_name: this._assetKey, asset_key: this._assetKey,
        }),
      }).then(r => r.json());
      if (result.error) throw new Error(result.error);
      await StudioAPI.fetch(this._company, this._assetKey, {
        full_url: result.img_path, id: `ai_${Date.now()}`,
        source: 'api_generate', source_page: '',
        author: 'AI Generated', license: 'AI',
      });
    } catch (e) {
      alert('AI 生成失败: ' + e.message);
    }
    if (btn) { btn.disabled = false; btn.textContent = '生成'; }
    await this._loadVariants();
  },

  async _onGenerateMap() {
    const el = this._container?.querySelector('#sidebar-actions');
    const btn = el?.querySelector('#btn-generate-map');
    if (btn) { btn.disabled = true; btn.textContent = '生成中...'; }
    try {
      const r = await fetch(
        `/api/image-studio/${encodeURIComponent(this._company)}/${encodeURIComponent(this._assetKey)}/generate-map`,
        { method: 'POST' }
      );
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    } catch (e) {
      alert('地图生成失败: ' + e.message);
    }
    if (btn) { btn.disabled = false; btn.textContent = '生成地图'; }
    await this._loadVariants();
  },

  setContext(company, assetKey) {
    this._company = company;
    this._assetKey = assetKey;
    this._ensureRendered();
    this._renderActions();
    this._loadVariants();
  },

  async _loadVariants() {
    try {
      const data = await StudioAPI.variants(this._company, this._assetKey);
      this._variants = data.variants || [];
      this._renderVariantList();
    } catch {
      this._variants = [];
      this._renderVariantList();
    }
  },

  async _onFetchImage(imageData) {
    try {
      const result = await StudioAPI.fetch(this._company, this._assetKey, imageData);
      // 检查版权披露
      if (imageData.source !== 'tavily' && !sessionStorage.getItem('copyright_shown')) {
        this._showCopyrightModal(imageData);
      }
      await this._loadVariants();
      // 选中刚加入的
      if (this._onSelect && result.id) {
        const v = this._variants.find(v => v.id === result.id);
        if (v) this._onSelect(v);
      }
    } catch (err) {
      this._toast(err.message, 'error');
    }
  },

  async _selectVariant(variant) {
    try {
      await StudioAPI.selectVariant(this._company, this._assetKey, variant.id);
      await this._loadVariants();
      if (this._onSelect) this._onSelect(variant);
      this._toast('已定稿');
    } catch (err) {
      this._toast(err.message, 'error');
    }
  },

  async _deleteVariant(variant) {
    if (!confirm('删除此变体？')) return;
    try {
      await StudioAPI.deleteVariant(this._company, this._assetKey, variant.id);
      await this._loadVariants();
    } catch (err) {
      this._toast(err.message, 'error');
    }
  },

  async _importUrl() {
    if (!this._container) return;
    const input = this._container.querySelector('.import-url-input');
    const url = input.value.trim();
    if (!url) return;
    try {
      await StudioAPI.importUrl(this._company, this._assetKey, url);
      input.value = '';
      await this._loadVariants();
      this._toast('导入成功，已设为选定');
    } catch (err) {
      this._toast(err.message, 'error');
    }
  },

  async _importFile(file) {
    try {
      await StudioAPI.importFile(this._company, this._assetKey, file);
      await this._loadVariants();
      this._toast('上传成功，已设为选定');
    } catch (err) {
      this._toast(err.message, 'error');
    }
  },

  /* ── SVG 渲染按钮显隐 ── */

  showSvgRender(show) {
    if (!this._container) return;
    const row = this._container.querySelector('#svg-render-row');
    if (row) row.classList.toggle('hidden', !show);
  },

  _renderVariantList() {
    const list = document.getElementById('variant-list-main');
    const countLabel = document.getElementById('variant-count-label');
    if (countLabel) countLabel.textContent = `${this._variants.length} 张`;
    if (!list) return;
    if (!this._variants.length) {
      list.innerHTML = `<div style="padding:16px;text-align:center;font-size:12px;color:var(--ink-muted)">暂无候选<br>搜索下载图片或导入</div>`;
    } else {
      list.innerHTML = this._variants.map(v => {
      const cls = v.is_selected ? 'variant-item selected' : 'variant-item';
      const srcLabel = { web_pexels: 'Pexels', web_unsplash: 'Unsplash', web_tavily: 'Tavily',
                         import_upload: '上传', import_url: 'URL', api_generate: 'AI', osm_map: '地图' }[v.source_type] || v.source_type;
      return `
        <div class="${cls}" data-id="${v.id}">
          <img src="${this._escape(v.local_path)}" alt="" onerror="this.style.opacity='0.3'">
          <div class="variant-meta">
            <span class="variant-source">${srcLabel}${v.author ? ' · ' + v.author : ''}</span>
            <span class="variant-delete" data-id="${v.id}">&times;</span>
          </div>
        </div>
      `;
      }).join('');
    }

    // Events
    list.querySelectorAll('.variant-item').forEach(item => {
      item.addEventListener('click', (e) => {
        if (e.target.classList.contains('variant-delete')) return;
        const id = parseInt(item.dataset.id);
        const v = this._variants.find(v => v.id === id);
        if (v) this._selectVariant(v);
      });
    });
    list.querySelectorAll('.variant-delete').forEach(del => {
      del.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = parseInt(del.dataset.id);
        const v = this._variants.find(v => v.id === id);
        if (v) this._deleteVariant(v);
      });
    });

    // 更新选定预览
    const selected = this._variants.find(v => v.is_selected);
    if (!this._container) return;
    const previewImg = this._container.querySelector('.selected-preview img');
    const previewEmpty = this._container.querySelector('.empty-preview');
    if (selected && previewImg) {
      previewImg.src = selected.local_path;
      previewImg.style.display = 'block';
      if (previewEmpty) previewEmpty.style.display = 'none';
    } else if (previewImg && previewEmpty) {
      previewImg.style.display = 'none';
      previewEmpty.style.display = 'block';
    }
  },

  /* ── Copyright Modal ── */

  _showCopyrightModal(imageData) {
    sessionStorage.setItem('copyright_shown', '1');
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal-box">
        <h3>&#9888; 版权提示</h3>
        <div class="modal-body">
          已从 ${imageData.source} 取图：<br>
          <strong>${this._escape(imageData.author || '未知作者')}</strong><br>
          ${this._escape(imageData.source_page || imageData.full_url || '')}
        </div>
        <p style="font-size:12px;color:var(--ink-muted);margin:8px 0">
          请自行判断版权是否适用于你的发布场景。
        </p>
        <div class="modal-actions">
          <button class="modal-btn-secondary skip-btn">不标注，仅本地记录</button>
          <button class="modal-btn-primary attr-btn">标注来源：Photo · ${imageData.source} · ${this._escape(imageData.author || '')}</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    overlay.querySelector('.attr-btn').addEventListener('click', () => {
      // 更新最近导入的变体 attribution_req
      overlay.remove();
    });
    overlay.querySelector('.skip-btn').addEventListener('click', () => {
      overlay.remove();
    });
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });
  },

  /* ── Toast ── */

  _toast(msg, type) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const el = document.createElement('div');
    el.className = 'toast' + (type === 'error' ? ' error' : '');
    el.textContent = msg;
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 200);
    }, 2500);
  },

  _escape(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },
};
