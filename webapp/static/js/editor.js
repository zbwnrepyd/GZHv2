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
  currentSection: 'card-settings',
  _imageIframeLoaded: false,
  _slots: null,
  _activeSlot: null,

  async init() {
    this.companyName = new URLSearchParams(window.location.search).get('company') || '';
    this.bindEvents();
    if (!this.companyName) {
      document.getElementById('editor-company-label').textContent = '请从研究台选择公司进入定稿台';
      return;
    }

    document.getElementById('editor-company-label').textContent = `定稿台 · ${this.companyName}`;
    document.getElementById('btn-go-canvas').href = `/canvas/?company=${encodeURIComponent(this.companyName)}`;

    const delBtn = document.getElementById('btn-delete-company');
    if (delBtn) {
      delBtn.classList.remove('hidden');
      delBtn.addEventListener('click', () => this.deleteCompany());
    }

    await this.loadStatus();
    this.switchSection('card-settings');
    if (this.companyName) {
      CardSettingsPanel.init(this.companyName);
    }
  },

  bindEvents() {
    document.querySelectorAll('.accordion-header').forEach(header => {
      header.addEventListener('click', () => {
        this.switchSection(header.dataset.section);
      });
    });

    document.getElementById('btn-recollect-editor')?.addEventListener('click', () => this.recollectAssets());

  },

  /* ── 手风琴切换 ── */

  switchSection(section) {
    this.currentSection = section;

    document.querySelectorAll('.accordion-header').forEach(h => {
      h.classList.toggle('open', h.dataset.section === section);
    });
    document.querySelectorAll('.accordion-body').forEach(b => {
      if (b.dataset.section === 'card-settings' || b.dataset.section === 'text-finalize') {
        b.classList.remove('open');
      } else {
        b.classList.toggle('open', b.dataset.section === section);
      }
    });

    const modeHandlers = {
      'image':          () => { this.showImageMode(); },
      'card-settings':  () => { this.showCardSettingsMode(); },
      'text-finalize':  () => { this.showTextFinalizeMode(); },
    };
    const handler = modeHandlers[section];
    if (handler) handler();
  },

  /* ── 模式切换 ── */

  _OVERLAY_IDS: ['image-studio-frame', 'card-settings-mode', 'text-finalize-mode'],

  _closeAllOverlays() {
    this._OVERLAY_IDS.forEach(id => document.getElementById(id).classList.remove('open'));
  },

  _hidePanesShowOverlay(overlayId) {
    document.getElementById('editor-middle-pane').style.display = 'none';
    document.getElementById('editor-right-pane').style.display = 'none';
    this._closeAllOverlays();
    document.getElementById(overlayId).classList.add('open');
  },

  showImageMode() {
    this._hidePanesShowOverlay('image-studio-frame');

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
  },

  showTextFinalizeMode() {
    this._hidePanesShowOverlay('text-finalize-mode');
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

  _esc(s) {
    return String(s || '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;',
    }[ch]));
  },
};

document.addEventListener('DOMContentLoaded', () => EditorApp.init());
