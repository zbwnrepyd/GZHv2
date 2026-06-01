/* studio-app.js — 图片定稿台主控制器 */
const StudioApp = {
  _company: '',
  _slots: [],
  _activeSlot: null,
  _cardMarkdown: {},

  async init() {
    const params = new URLSearchParams(window.location.search);
    this._company = params.get('company') || '';
    if (!this._company) {
      document.body.innerHTML = '<div class="empty-state"><p>缺少 ?company= 参数</p></div>';
      return;
    }

    document.querySelector('.company-name').textContent = this._company;
    document.querySelector('.back-btn').addEventListener('click', () => {
      window.location.href = `/editor?company=${encodeURIComponent(this._company)}`;
    });
    document.getElementById('btn-recollect')?.addEventListener('click', () => this._recollectAssets());

    QueryGen.init();

    // 初始化子面板
    SearchPanel.init(document.getElementById('search-panel'), {
      onFetch: (imageData) => {
        VariantSidebar._onFetchImage(imageData);
      },
    });
    VariantSidebar.init(document.getElementById('action-sidebar'), {
      onSelect: (variant) => {
        this._refreshSlots();
      },
    });

    // 载入总览
    await this._loadSlots();

    // 支持 ?slot=xxx 自动选中槽位
    const slotParam = params.get('slot');
    if (slotParam) {
      const target = this._slots.find(s => s.asset_key === slotParam);
      if (target) this._selectSlot(target);
    } else {
      const editable = this._slots.filter(s => s.asset_key !== 'logo' && s.asset_key !== 'flywheel' && s.asset_key !== 'timeline');
      if (editable.length) this._selectSlot(editable[0]);
    }
  },

  async _loadSlots() {
    try {
      const data = await StudioAPI.overview(this._company);
      this._slots = data.slots || [];
      this._renderSlotList();
    } catch (err) {
      console.error('加载总览失败:', err);
    }
  },

  async _refreshSlots() {
    await this._loadSlots();
  },

  async _recollectAssets() {
    const btn = document.getElementById('btn-recollect');
    if (btn) { btn.disabled = true; btn.textContent = '采集中...'; }
    try {
      const r = await fetch(`/api/assets/collect/${encodeURIComponent(this._company)}`, { method: 'POST' });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
      await this._loadSlots();
      // 重新选中当前槽位以刷新视图
      if (this._activeSlot) {
        const refreshed = this._slots.find(s => s.asset_key === this._activeSlot.asset_key);
        if (refreshed) this._selectSlot(refreshed);
      }
    } catch (e) {
      alert('采集失败: ' + e.message);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '重新采集图片'; }
    }
  },

  _renderSlotList() {
    const list = document.getElementById('slot-list');
    if (!list) return;

    const labels = {
      logo: '卡片1 — Logo',
      office: '卡片2 — 公司形象',
      timeline: '卡片3 — 时间线',
      product_main: '卡片4 — 主产品',
      products_other: '卡片5 — 其他产品',
      flywheel: '卡片6 — 增长飞轮',
      competitors: '卡片7 — 竞争格局',
    };

    const isSvgSlot = (key) => key === 'flywheel' || key === 'timeline';

    list.innerHTML = this._slots.map(s => {
      const thumbHtml = s.local_path
        ? `<img src="${this._escape(s.local_path)}" alt="">`
        : `<div class="slot-thumb placeholder">${isSvgSlot(s.asset_key) ? '&#9881;' : '&#128247;'}</div>`;

      let metaText;
      if (isSvgSlot(s.asset_key)) {
        metaText = s.status === 'ready' ? 'SVG 信息图 · 已就绪' : 'SVG 信息图 · 待生成';
      } else {
        metaText = s.status === 'ready' ? '已就绪' : '待配图';
        if (s.variant_count > 0) metaText += ` · ${s.variant_count} 变体`;
      }

      return `
        <li class="slot-item" data-key="${s.asset_key}">
          <div class="slot-thumb">${thumbHtml}</div>
          <div class="slot-info">
            <div class="slot-label">${labels[s.asset_key] || s.asset_key}</div>
            <div class="slot-meta">${metaText}</div>
          </div>
          <span class="slot-badge ${s.status}"></span>
        </li>
      `;
    }).join('');

    list.querySelectorAll('.slot-item').forEach(item => {
      item.addEventListener('click', () => {
        const key = item.dataset.key;
        const slot = this._slots.find(s => s.asset_key === key);
        if (slot) this._selectSlot(slot);
      });
    });
  },

  async _selectSlot(slot) {
    this._activeSlot = slot;

    // 高亮
    document.querySelectorAll('.slot-item').forEach(el => {
      el.classList.toggle('active', el.dataset.key === slot.asset_key);
    });

    // 设置上下文
    SearchPanel.setContext(this._company, slot.asset_key);
    VariantSidebar.setContext(this._company, slot.asset_key);

    // SVG 槽位特殊处理
    if (slot.asset_key === 'flywheel' || slot.asset_key === 'timeline') {
      SearchPanel.setSlotImage('');
      VariantSidebar.showSvgRender(true);
      this._showSvgSlot(slot);
      return;
    }
    VariantSidebar.showSvgRender(false);

    // Logo 只读
    if (slot.asset_key === 'logo') {
      SearchPanel.setSlotImage('');
      this._showLogoSolt(slot);
      return;
    }

    // 恢复搜索 UI 并显示当前已有图片
    this._showSearchUI();
    SearchPanel.setSlotImage(slot.local_path);

    // 加载查询词
    let queries = QueryGen.get(this._company, slot.asset_key);
    if (!queries) {
      const markdown = await this._loadCardMarkdown(slot.card_index);
      if (markdown) {
        queries = await QueryGen.fetch(this._company, slot.asset_key, markdown);
      }
      if (!queries) {
        queries = QueryGen.fallback(slot.asset_key);
      }
    }
    SearchPanel.setQueries(queries);
    SearchPanel.search();
  },

  _svTemplates: [],
  _svSelectedTpl: null,
  _svParams: {},
  _svDataByKey: {},
  _svPreviewTimer: 0,

  async _showSvgSlot(slot) {
    this._hideSearchUI();
    this._activeSlot = slot;

    // 加载模板列表
    if (!this._svTemplates.length) {
      try {
        const r = await fetch('/api/svg-templates');
        const data = await r.json();
        this._svTemplates = data.templates || [];
      } catch (e) {
        this._svTemplates = [];
      }
    }

    const filtered = this._svTemplates.filter(t => t.asset_key === slot.asset_key);
    if (!filtered.length) {
      this._renderSvgEmpty('暂无可用模板');
      return;
    }

    // 默认选中第一个
    if (!this._svSelectedTpl || this._svSelectedTpl.asset_key !== slot.asset_key) {
      this._svSelectedTpl = filtered[0];
      this._svParams = {};
      (this._svSelectedTpl.params || []).forEach(p => {
        this._svParams[p.key] = p.default;
      });
    }

    // 每个 SVG 槽位的数据结构不同，必须按 asset_key 缓存。
    if (!this._svDataByKey[slot.asset_key]) {
      try {
        const r = await fetch(
          `/api/image-studio/${encodeURIComponent(this._company)}/${encodeURIComponent(slot.asset_key)}/extract-data`,
          { method: 'POST' }
        );
        const d = await r.json();
        if (r.ok && d.data) {
          this._svDataByKey[slot.asset_key] = d.data;
        }
      } catch (e) {
        console.error('提取结构化数据失败:', e);
      }
    }

    this._renderSvgEditor(filtered);
    VariantSidebar.setContext(this._company, slot.asset_key);

    // 首次渲染预览
    if (this._svDataByKey[slot.asset_key]) this._updatePreview();
  },

  _renderSvgEditor(templates) {
    const grid = document.querySelector('.candidate-grid');
    if (!grid) return;
    const tpl = this._svSelectedTpl;

    grid.innerHTML = `
      <div class="svg-editor">
        <div class="svg-tpl-tabs">
          ${templates.map(t => `
            <button class="svg-tpl-tab ${t.id === tpl.id ? 'active' : ''}" data-tpl-id="${t.id}">
              <span class="tpl-badge ${t.builtin ? 'builtin' : 'custom'}">${t.builtin ? '内置' : '自定义'}</span>
              <span class="tpl-name">${this._escape(t.name)}</span>
            </button>
          `).join('')}
          <label class="svg-tpl-upload-btn" title="上传本机 Python 模板 (.py 文件)">
            <input type="file" accept=".py" style="display:none" onchange="StudioApp._uploadTemplate(this)">
            +<span style="font-size:10px;margin-left:2px;color:var(--ink-muted)">上传模板</span>
          </label>
        </div>
        <div class="svg-params">
          ${this._renderParamControls(tpl.params || [])}
        </div>
        <div class="svg-preview" id="svg-preview">
          <div class="svg-preview-label">实时预览</div>
          <div class="svg-preview-stage" id="svg-preview-stage"></div>
        </div>
      </div>
    `;

    // 模板切换事件
    grid.querySelectorAll('.svg-tpl-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        const tid = btn.dataset.tplId;
        const t = templates.find(x => x.id === tid);
        if (t) {
          this._svSelectedTpl = t;
          this._svParams = {};
          (t.params || []).forEach(p => {
            this._svParams[p.key] = p.default;
          });
          this._renderSvgEditor(templates);
        }
      });
    });
  },

  _renderParamControls(params) {
    return params.map(p => {
      const val = this._svParams[p.key] !== undefined ? this._svParams[p.key] : p.default;
      if (p.type === 'range') {
        return `
          <div class="ctrl-row">
            <label>${this._escape(p.label)}</label>
            <input type="range" min="${p.min}" max="${p.max}" step="${p.step}" value="${val}" data-key="${p.key}"
                   oninput="StudioApp._onParamChange(this)">
            <span class="ctrl-val" id="pv-${p.key}">${val}</span>
          </div>`;
      }
      if (p.type === 'color') {
        return `
          <div class="ctrl-row">
            <label>${this._escape(p.label)}</label>
            <input type="color" value="${val}" data-key="${p.key}" oninput="StudioApp._onParamChange(this)">
          </div>`;
      }
      return '';
    }).join('');
  },

  _onParamChange(el) {
    const key = el.dataset.key;
    this._svParams[key] = el.type === 'range' ? parseInt(el.value) : el.value;
    const valSpan = document.getElementById('pv-' + key);
    if (valSpan) valSpan.textContent = el.value;
    this._schedulePreview();
  },

  _schedulePreview() {
    clearTimeout(this._svPreviewTimer);
    this._svPreviewTimer = setTimeout(() => this._updatePreview(), 200);
  },

  async _updatePreview() {
    const stage = document.getElementById('svg-preview-stage');
    const activeKey = this._activeSlot ? this._activeSlot.asset_key : '';
    const svgData = this._svDataByKey[activeKey];
    if (!stage || !svgData || !this._svSelectedTpl) return;

    try {
      const r = await fetch('/api/svg-templates/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: this._svSelectedTpl.id,
          params: this._svParams,
          data: svgData,
        }),
      });

      if (!r.ok) {
        stage.innerHTML = `<div class="svg-preview-error">预览失败: ${r.status}</div>`;
        return;
      }

      const svgText = await r.text();
      stage.innerHTML = svgText;
    } catch (e) {
      stage.innerHTML = `<div class="svg-preview-error">预览失败</div>`;
    }
  },

  async _renderSvg() {
    const btn = document.querySelector('.svg-render-btn-sidebar');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '渲染中...';
    }

    try {
      const r = await fetch(
        `/api/image-studio/${encodeURIComponent(this._company)}/${encodeURIComponent(this._activeSlot.asset_key)}/render-svg`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            template_id: this._svSelectedTpl.id,
            params: this._svParams,
          }),
        }
      );
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || '渲染失败');

      // 刷新变体库和槽位列表
      VariantSidebar.setContext(this._company, this._activeSlot.asset_key);
      await this._refreshSlots();
    } catch (e) {
      alert('SVG 渲染失败: ' + e.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '生成当前参数 SVG';
      }
    }
  },

  async _uploadTemplate(input) {
    const file = input.files[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    try {
      const r = await fetch('/api/svg-templates/upload', {
        method: 'POST',
        headers: { 'X-Template-Upload-Intent': 'local-dev' },
        body: form,
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || '上传失败');
      // 重新加载模板列表
      const r2 = await fetch('/api/svg-templates');
      const all = await r2.json();
      this._svTemplates = all.templates || [];
      if (this._activeSlot) this._showSvgSlot(this._activeSlot);
    } catch (e) {
      alert('模板上传失败: ' + e.message);
    }
    input.value = '';
  },

  _renderSvgEmpty(msg) {
    const grid = document.querySelector('.candidate-grid');
    if (grid) {
      grid.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">&#9881;</div>
          <p>${this._escape(msg)}</p>
        </div>
      `;
    }
  },

  _showLogoSolt(slot) {
    this._hideSearchUI();
    const grid = document.querySelector('.candidate-grid');
    if (grid) {
      grid.innerHTML = `
        <div class="empty-state">
          ${slot.local_path ? `<img src="${this._escape(slot.local_path)}" style="max-width:240px;max-height:120px;border-radius:8px;margin-bottom:12px" alt="">` : '<div class="empty-icon" style="font-size:48px">&#127760;</div>'}
          <p style="font-size:14px;color:var(--ink)">Logo 自动采集</p>
          <p style="font-size:12px;margin-top:4px">来源：Clearbit / Favicon</p>
          ${!slot.local_path ? '<p style="font-size:12px;color:var(--ink-muted);margin-top:8px">暂未获取到 Logo</p>' : ''}
        </div>
      `;
    }
  },

  _hideSearchUI() {
    const searchSection = document.querySelector('.search-section');
    if (searchSection) searchSection.style.display = 'none';
  },

  _showSearchUI() {
    const searchSection = document.querySelector('.search-section');
    if (searchSection) searchSection.style.display = '';
  },

  async _loadCardMarkdown(cardIndex) {
    if (this._cardMarkdown[cardIndex]) return this._cardMarkdown[cardIndex];
    try {
      const r = await fetch(`/api/final/card/${encodeURIComponent(this._company)}/${cardIndex}`);
      if (!r.ok) return null;
      const data = await r.json();
      this._cardMarkdown[cardIndex] = data.markdown_content || '';
      return this._cardMarkdown[cardIndex];
    } catch {
      return null;
    }
  },

  _escape(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },
};

document.addEventListener('DOMContentLoaded', () => StudioApp.init());
