/* variant-sidebar.js — 右栏：候选缩略图 + 确定图片 */
const VariantSidebar = {
  _company: '',
  _assetKey: '',
  _variants: [],
  _sortMode: 'score',
  _previewedId: null,   // 当前预览中的变体 ID（未确认）
  _selectedId: null,    // 已确认选中的变体 ID
  _container: null,
  _onSelect: null,      // callback(variant) — 选中后刷新槽位
  _onPreview: null,     // callback(imageSrc) — 在中间栏预览
  _rendered: false,

  init(container, { onSelect, onPreview }) {
    this._container = container;
    this._onSelect = onSelect;
    this._onPreview = onPreview;
    this._render();
  },

  setContext(company, assetKey) {
    this._company = company;
    this._assetKey = assetKey;
    this._previewedId = null;
    this._selectedId = null;
    this._loadVariants();
  },

  /* 外部调用：刷新变体列表 */
  async refresh() {
    await this._loadVariants();
  },

  _render() {
    if (!this._container || this._rendered) return;
    this._container.innerHTML = `
      <div class="candidate-panel-header">
        <h3>候选图片</h3>
        <select class="candidate-sort-select" id="candidate-sort-select">
          <option value="score">按分数</option>
          <option value="source">按来源</option>
          <option value="size">按尺寸</option>
          <option value="selected">按选中</option>
          <option value="time">按时间</option>
        </select>
        <span class="candidate-count" id="candidate-count">0 张</span>
      </div>
      <div class="candidate-grid-scroll" id="candidate-grid-scroll">
        <div class="candidate-grid-2col" id="candidate-grid-2col"></div>
      </div>
      <div class="candidate-confirm-bar">
        <button class="btn-confirm" id="btn-confirm-image" disabled>确定图片</button>
      </div>
    `;

    this._container.querySelector('#candidate-sort-select').addEventListener('change', (e) => {
      this._sortMode = e.target.value || 'score';
      this._renderVariantList();
    });

    this._container.querySelector('#btn-confirm-image').addEventListener('click', () => {
      if (this._previewedId != null) this._confirmSelection();
    });

    this._rendered = true;
  },

  /* ── 加载变体 ── */

  async _loadVariants() {
    try {
      const data = await StudioAPI.variants(this._company, this._assetKey);
      this._variants = data.variants || [];
      // 找到已选中的变体
      const selected = this._variants.find(v => v.is_selected);
      this._selectedId = selected ? selected.id : null;
      // 首次加载时，如果有已选中变体，自动预览
      if (selected && this._previewedId == null) {
        this._previewedId = selected.id;
        if (this._onPreview) this._onPreview(selected.local_path);
      }
      this._renderVariantList();
    } catch {
      this._variants = [];
      this._renderVariantList();
    }
  },

  /* ── 渲染缩略图 ── */

  _renderVariantList() {
    const grid = document.getElementById('candidate-grid-2col');
    const countLabel = document.getElementById('candidate-count');
    if (countLabel) countLabel.textContent = `${this._variants.length} 张`;
    if (!grid) return;

    const variants = this._sortVariants(this._variants);

    if (!variants.length) {
      grid.innerHTML = `<div style="grid-column:1/-1;padding:24px;text-align:center;font-size:12px;color:var(--ink-muted)">暂无候选<br>搜索下载图片后出现在这里</div>`;
    } else {
      grid.innerHTML = variants.map(v => {
        const cls = this._thumbClass(v);
        const srcLabel = { web_pexels: 'Pexels', web_unsplash: 'Unsplash', web_tavily: 'Tavily',
                           import_upload: '上传', import_url: 'URL', api_generate: 'AI', osm_map: '地图',
                           official_og_image: 'OG', product_hunt: 'PH', playwright: '截图',
                           street_view: 'Street View', clearbit: 'Clearbit',
                           logo_strip: 'Logo拼图' }[v.source_type] || v.source_type;
        const dimensions = v.width && v.height ? `${v.width}×${v.height}` : '';
        const score = Number(v.final_score || 0).toFixed(1);
        const rejectReason = v.reject_reason ? `<div class="thumb-reject" title="${this._escape(v.reject_reason)}">${this._escape(v.reject_reason)}</div>` : '';

        return `
          <div class="${cls}" data-id="${v.id}">
            ${v.is_selected ? '<span class="thumb-selected-badge">已选</span>' : ''}
            <span class="thumb-delete" data-id="${v.id}">&times;</span>
            <img src="${this._escape(v.local_path)}" alt="" loading="lazy"
                 onerror="this.style.opacity='0.3'">
            <div class="thumb-info">
              <span class="thumb-source">${srcLabel}${v.author ? ' · ' + this._escape(v.author) : ''}</span>
              <span class="thumb-score">${score}</span>
            </div>
            ${dimensions ? `<div class="thumb-dimensions">${dimensions}</div>` : ''}
            ${rejectReason}
          </div>
        `;
      }).join('');
    }

    // 更新确定按钮状态
    this._updateConfirmButton();

    // 事件绑定
    grid.querySelectorAll('.candidate-thumb').forEach(thumb => {
      thumb.addEventListener('click', (e) => {
        if (e.target.classList.contains('thumb-delete')) return;
        const id = parseInt(thumb.dataset.id);
        this._previewVariant(id);
      });
    });
    grid.querySelectorAll('.thumb-delete').forEach(del => {
      del.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = parseInt(del.dataset.id);
        this._deleteVariant(id);
      });
    });
  },

  _thumbClass(v) {
    const parts = ['candidate-thumb'];
    if (v.id === this._previewedId) parts.push('previewed');
    if (v.is_selected) parts.push('selected');
    return parts.join(' ');
  },

  /* ── 预览 ── */

  _previewVariant(id) {
    this._previewedId = id;
    const v = this._variants.find(v => v.id === id);
    if (v && this._onPreview) {
      this._onPreview(v.local_path);
    }
    this._renderVariantList();
  },

  _updateConfirmButton() {
    const btn = document.getElementById('btn-confirm-image');
    if (!btn) return;
    if (this._previewedId == null) {
      btn.disabled = true;
      btn.textContent = '确定图片';
    } else if (this._previewedId === this._selectedId) {
      btn.disabled = true;
      btn.textContent = '已确定';
      btn.classList.add('secondary');
    } else {
      btn.disabled = false;
      btn.textContent = '确定图片';
      btn.classList.remove('secondary');
    }
  },

  /* ── 确认选中 ── */

  async _confirmSelection() {
    if (this._previewedId == null) return;
    try {
      await StudioAPI.selectVariant(this._company, this._assetKey, this._previewedId);
      this._selectedId = this._previewedId;
      // 更新变体列表中的 is_selected 状态
      this._variants.forEach(v => {
        v.is_selected = (v.id === this._selectedId);
      });
      this._renderVariantList();
      if (this._onSelect) this._onSelect(this._variants.find(v => v.id === this._selectedId));
      this._toast('已确定图片');
    } catch (e) {
      this._toast('确定失败: ' + e.message, 'error');
    }
  },

  /* ── 删除 ── */

  async _deleteVariant(id) {
    if (!confirm('删除此变体？')) return;
    try {
      await StudioAPI.deleteVariant(this._company, this._assetKey, id);
      if (this._previewedId === id) {
        this._previewedId = null;
        if (this._onPreview) this._onPreview('');
      }
      await this._loadVariants();
    } catch (e) {
      this._toast('删除失败: ' + e.message, 'error');
    }
  },

  /* ── 排序 ── */

  _sortVariants(variants) {
    const arr = [...(variants || [])];
    const area = (v) => Number(v.width || 0) * Number(v.height || 0);
    switch (this._sortMode) {
      case 'source':
        arr.sort((a, b) => String(a.source_type || '').localeCompare(String(b.source_type || '')) || (b.final_score || 0) - (a.final_score || 0));
        break;
      case 'size':
        arr.sort((a, b) => area(b) - area(a));
        break;
      case 'selected':
        arr.sort((a, b) => Number(b.is_selected || 0) - Number(a.is_selected || 0) || (b.final_score || 0) - (a.final_score || 0));
        break;
      case 'time':
        arr.sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
        break;
      default:
        arr.sort((a, b) => (b.final_score || 0) - (a.final_score || 0));
    }
    return arr;
  },

  /* ── 版权弹窗 ── */

  showCopyrightModal(imageData) {
    if (imageData.source !== 'tavily' && !sessionStorage.getItem('copyright_shown')) {
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
      overlay.querySelector('.attr-btn').addEventListener('click', () => overlay.remove());
      overlay.querySelector('.skip-btn').addEventListener('click', () => overlay.remove());
      overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    }
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
