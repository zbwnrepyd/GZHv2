/* studio-app.js — 图片定稿台主控制器 v3 */
const DEMAND_LABELS = {
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

const DEMAND_META = {
  logo: { type: '抓取图', usage: '官网 / Clearbit' },
  website_screenshot: { type: '抓取图', usage: '官网首页' },
  office: { type: '抓取图', usage: '地图 / 办公场景' },
  product_main: { type: '抓取图', usage: '产品页 / 搜索' },
  products_other: { type: '抓取图', usage: '多产品候选' },
  competitors: { type: '抓取图', usage: '竞品截图' },
  competitors_logo_strip: { type: '生成图', usage: '16:9 Logo 拼图' },
  chart_competitive: { type: '生成图', usage: 'ECharts' },
  chart_ecosystem: { type: '生成图', usage: 'ECharts' },
  flywheel: { type: '生成图', usage: 'SVG' },
  timeline: { type: '生成图', usage: 'SVG' },
};

const DEMAND_ORDER = [
  'logo', 'website_screenshot', 'office', 'product_main', 'products_other',
  'competitors', 'competitors_logo_strip', 'chart_competitive', 'chart_ecosystem', 'flywheel', 'timeline',
];

const GENERATED_DEMANDS = ['chart_competitive', 'chart_ecosystem', 'flywheel', 'timeline'];
const AUTO_GENERATED_IMAGE_DEMANDS = ['competitors_logo_strip'];

window.DEMAND_LABELS = DEMAND_LABELS;

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

    QueryGen.init();

    // 初始化中间栏
    SearchPanel.init(document.getElementById('editor-area'), {
      onFetch: (imageData) => this._onFetchImage(imageData),
      onRefresh: () => this._onRefreshCandidates(),
    });

    // 初始化右栏候选面板
    VariantSidebar.init(document.getElementById('candidate-panel'), {
      onSelect: (variant) => {
        this._refreshSlots();
      },
      onPreview: (imageSrc) => {
        if (imageSrc) {
          SearchPanel.showPreviewImage(imageSrc);
        } else {
          SearchPanel.showPreviewImage('');
        }
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
      const editable = this._slots.filter(s => s.asset_key !== 'logo');
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

  async _onRefreshCandidates() {
    await VariantSidebar.refresh();
  },

  /* 搜索点击 → 下载入库 → 刷新右栏 */
  async _onFetchImage(imageData) {
    try {
      const result = await StudioAPI.fetch(this._company, this._activeSlot.asset_key, imageData);
      // 版权披露
      VariantSidebar.showCopyrightModal(imageData);
      // 刷新右栏候选
      await VariantSidebar.refresh();
      // 自动预览刚下载的图
      if (result && result.id) {
        const v = VariantSidebar._variants.find(v => v.id === result.id);
        if (v) {
          VariantSidebar._previewVariant(v.id);
        }
      }
    } catch (err) {
      this._toast(err.message, 'error');
    }
  },

  _renderSlotList() {
    const list = document.getElementById('slot-list');
    if (!list) return;

    const ordered = DEMAND_ORDER.map(key => this._slots.find(s => s.asset_key === key)).filter(Boolean);
    list.innerHTML = ordered.map(s => {
      const meta = DEMAND_META[s.asset_key] || { type: '图片', usage: '' };
      const isGenerated = GENERATED_DEMANDS.includes(s.asset_key) || AUTO_GENERATED_IMAGE_DEMANDS.includes(s.asset_key);
      const thumbHtml = s.local_path
        ? `<img src="${this._escape(s.local_path)}" alt="">`
        : `<div class="slot-thumb placeholder">${isGenerated ? '&#9881;' : '&#128247;'}</div>`;

      let metaText;
      if (isGenerated) {
        metaText = `${meta.type} · ${meta.usage} · ${s.status === 'ready' ? '已确定' : '待生成'}`;
      } else {
        metaText = `${meta.type} · ${meta.usage} · ${s.status === 'ready' ? '已确定' : '待配图'}`;
        if (s.variant_count > 0) metaText += ` · ${s.variant_count} 变体`;
      }

      return `
        <li class="slot-item" data-key="${s.asset_key}">
          <div class="slot-thumb">${thumbHtml}</div>
          <div class="slot-info">
            <div class="slot-label">${DEMAND_LABELS[s.asset_key] || s.asset_key}</div>
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

    if (GENERATED_DEMANDS.includes(slot.asset_key)) {
      await WorkspaceChart.mount({
        company: this._company,
        slot,
        editorArea: document.getElementById('editor-area'),
        candidatePanel: document.getElementById('candidate-panel'),
        onRefresh: () => this._refreshSlots(),
        onToast: (msg, type) => this._toast(msg, type),
      });
      return;
    }

    await WorkspaceImage.mount({
      company: this._company,
      slot,
      editorArea: document.getElementById('editor-area'),
      candidatePanel: document.getElementById('candidate-panel'),
      onRefresh: () => this._refreshSlots(),
      onToast: (msg, type) => this._toast(msg, type),
      loadCardMarkdown: (cardIndex) => this._loadCardMarkdown(cardIndex),
    });
  },

  /* ── SVG 槽位 ── */

  _svTemplates: [],
  _svSelectedTpl: null,
  _svParams: {},
  _svDataByKey: {},
  _svPreviewTimer: 0,

  /* ── 图表类槽位统一入口 ── */
  async _showChartSlot(slot) {
    this._activeSlot = slot;
    await VariantSidebar.setContext(this._company, slot.asset_key);

    const isChartSlot = slot.asset_key === 'chart_competitive' || slot.asset_key === 'chart_ecosystem';

    if (isChartSlot) {
      this._renderChartUI(slot, null);
    } else {
      // flywheel / timeline: 加载模板
      if (!this._svTemplates.length) {
        try {
          const r = await fetch('/api/svg-templates');
          this._svTemplates = (await r.json()).templates || [];
        } catch (e) { this._svTemplates = []; }
      }
      const filtered = this._svTemplates.filter(t => t.asset_key === slot.asset_key);
      if (!filtered.length) { this._renderChartEmpty('暂无可用模板'); return; }

      if (!this._svSelectedTpl || this._svSelectedTpl.asset_key !== slot.asset_key) {
        this._svSelectedTpl = filtered[0];
        this._svParams = {};
        (this._svSelectedTpl.params || []).forEach(p => { this._svParams[p.key] = p.default; });
      }
      if (!this._svDataByKey[slot.asset_key]) {
        try {
          const r = await fetch(`/api/image-studio/${encodeURIComponent(this._company)}/${encodeURIComponent(slot.asset_key)}/extract-data`, { method: 'POST' });
          const d = await r.json();
          if (r.ok && d.data) this._svDataByKey[slot.asset_key] = d.data;
        } catch (e) { /* non-blocking */ }
      }
      this._renderChartUI(slot, filtered);
      if (this._svDataByKey[slot.asset_key]) this._updatePreview();
    }
  },

  /* 渲染图表 UI（实时预览 iframe + 功能区 bar） */
  _chartPreviewTimer: 0,

  _renderChartUI(slot, templates) {
    document.querySelector('.preview-toggle-bar')?.classList.add('hidden');
    document.getElementById('search-results-area')?.classList.add('hidden');
    const stage = document.getElementById('preview-stage');
    stage?.classList.remove('hidden');
    if (!stage) return;

    const isChartSlot = slot.asset_key === 'chart_competitive' || slot.asset_key === 'chart_ecosystem';
    stage.innerHTML = `<iframe id="chart-preview-iframe" style="width:100%;height:100%;border:none;background:#fff"></iframe>`;

    // ECharts 散点图：立即加载实时预览
    if (isChartSlot) {
      this._updateChartPreview();
    }

    // 功能区 bar
    const toolbar = document.getElementById('toolbar-section');
    if (toolbar) {
      toolbar.classList.remove('hidden');
      toolbar.innerHTML = `<div class="chart-func-bar">
        <div class="chart-func-bar-header">图表调节</div>
        <div class="chart-func-bar-body">${isChartSlot ? this._chartRenderBar(slot) : this._svgTemplateBar(templates)}</div>
      </div>`;
    }

    if (!isChartSlot && templates) {
      document.querySelectorAll('.bar-tpl-tab').forEach(btn => {
        btn.addEventListener('click', () => {
          const t = templates.find(x => x.id === btn.dataset.tplId);
          if (t) {
            this._svSelectedTpl = t;
            this._svParams = {};
            (t.params || []).forEach(p => { this._svParams[p.key] = p.default; });
            this._renderChartUI(slot, templates);
            if (this._svDataByKey[slot.asset_key]) this._updateChartPreview();
          }
        });
      });
    }
    this._bindChartRenderButtons();
    if (!isChartSlot && this._svDataByKey[slot.asset_key]) this._updateChartPreview();
    else if (isChartSlot) this._updateChartPreview();
  },

  _updateChartPreview() {
    clearTimeout(this._chartPreviewTimer);
    this._chartPreviewTimer = setTimeout(() => this._doUpdateChartPreview(), 200);
  },

  async _doUpdateChartPreview() {
    const iframe = document.getElementById('chart-preview-iframe');
    if (!iframe || !this._activeSlot) return;
    const slot = this._activeSlot;
    try {
      if (slot.asset_key === 'chart_competitive' || slot.asset_key === 'chart_ecosystem') {
        const params = this._svParams || {};
        const r = await fetch(
          `/api/image-studio/${encodeURIComponent(this._company)}/${encodeURIComponent(slot.asset_key)}/preview`,
          { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ params: params }) }
        );
        if (r.ok) iframe.srcdoc = await r.text();
      } else {
        const svgData = this._svDataByKey[slot.asset_key];
        if (!svgData || !this._svSelectedTpl) return;
        const r = await fetch('/api/svg-templates/preview', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ template_id: this._svSelectedTpl.id, params: this._svParams, data: svgData }),
        });
        if (r.ok) iframe.srcdoc = `<html><body style="margin:0;display:flex;align-items:center;justify-content:center;background:#fff">${await r.text()}</body></html>`;
      }
    } catch (e) { /* non-blocking */ }
  },

  _buildScatterPreview(chartType, companies, params) {
    const p = params || {};
    const accent = p.accent_color || '#29B8D4';
    const pt = p.point_size || 10, ts = p.title_size || 16, as = p.axis_size || 12;
    const theme = p.theme || 'dark';
    const showLabel = p.show_label !== false;
    const title = chartType === 'competitive_landscape' ? '竞争格局矩阵' : 'AI Stack 定位图';
    const hi = this._company, hiData = [], otData = [];
    const stMap = { infrastructure:1, foundation_model:2, middleware:3, vertical_app:4, distribution:5 };
    for (const c of (companies||[])) {
      const n = c.company_name || '';
      if (chartType === 'competitive_landscape') {
        const dx = parseFloat(c.score_defensibility||0), dy = parseFloat(c.score_incumbent_attention||0);
        if (!dx&&!dy) continue;
        (n===hi?hiData:otData).push([dx,dy,n]);
      } else {
        const sx = stMap[c.stack_layer||'vertical_app']||3, dy = parseFloat(c.score_value_capture||0);
        if (!dy) continue;
        (n===hi?hiData:otData).push([sx,dy,n]);
      }
    }
    const ds = [];
    if (hiData.length) ds.push({name:hi,data:hiData});
    if (otData.length) ds.push({name:'其他公司',data:otData});
    const dsj = JSON.stringify(ds);
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{margin:0;width:100%;height:100%;overflow:hidden;background:${theme==='dark'?'#0B1629':'#fff'}}
#chart{width:100%;height:100%}</style></head><body>
<div id="chart"></div>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js"></script>
<script>
var ds=${dsj};
var series=ds.map(function(d){return{name:d.name,type:'scatter',data:d.data,
  symbolSize:${pt},
  label:{show:${showLabel},formatter:function(p){return p.value[2]||''},fontSize:10,color:'${theme==="dark"?"rgba(255,255,255,0.6)":"#666"}'},
  emphasis:{focus:'series'}
}});
echarts.init(document.getElementById('chart')).setOption({
  title:{text:'${title}',left:'center',textStyle:{color:'${theme==="dark"?"#fff":"#333"}',fontSize:${ts},fontWeight:700}},
  tooltip:{formatter:function(p){return p.value[2]+'<br/>('+p.value[0]+', '+p.value[1]+')'}},
  legend:{bottom:10,textStyle:{color:'${theme==="dark"?"rgba(255,255,255,0.5)":"#999"}',fontSize:11}},
  grid:{left:70,right:40,top:60,bottom:50},
  xAxis:{name:'${chartType==='competitive_landscape'?'Defensibility':'Stack Layer'}',nameTextStyle:{color:'${theme==="dark"?"rgba(255,255,255,0.5)":"#999"}',fontSize:${as}}},
  yAxis:{name:'${chartType==='competitive_landscape'?'Incumbent Attention':'Value Capture'}',nameTextStyle:{color:'${theme==="dark"?"rgba(255,255,255,0.5)":"#999"}',fontSize:${as}}},
  backgroundColor:'${theme==="dark"?"#0B1629":"#fff"}',
  color:["${accent}","#7DD3FC","#F9E2AF","#A7F3D0","#C4B5FD","#FDA4AF"]
});
</script></body></html>`;
  },

  _chartRenderBar(slot) {
    const p = this._svParams || {};
    if (!('accent_color' in p)) { p.accent_color = '#29B8D4'; p.point_size = 10; p.title_size = 16; p.axis_size = 12; p.theme = 'dark'; p.show_label = true; }
    this._svParams = p;
    const chartType = slot.asset_key === 'chart_competitive' ? 'competitive_landscape' : 'stack_positioning';
    const chartLabel = slot.asset_key === 'chart_competitive' ? '竞争格局矩阵' : 'AI Stack 定位图';
    return `
      <div class="bar-controls">
        <div class="bar-control-row">
          <span class="bar-label">颜色</span>
          <input type="color" value="${p.accent_color}" data-chart-param="accent_color" onchange="StudioApp._onChartParamChange(this)">
          <span class="bar-label">点大小</span>
          <input type="range" min="3" max="24" value="${p.point_size}" data-chart-param="point_size" oninput="StudioApp._onChartParamChange(this)">
          <span class="bar-val">${p.point_size}</span>
          <span class="bar-label">标题字</span>
          <input type="range" min="10" max="28" value="${p.title_size}" data-chart-param="title_size" oninput="StudioApp._onChartParamChange(this)">
          <span class="bar-val">${p.title_size}</span>
          <span class="bar-label">轴字</span>
          <input type="range" min="8" max="18" value="${p.axis_size}" data-chart-param="axis_size" oninput="StudioApp._onChartParamChange(this)">
          <span class="bar-val">${p.axis_size}</span>
          <span class="bar-label">主题</span>
          <select data-chart-param="theme" onchange="StudioApp._onChartParamChange(this)" style="font-size:11px">
            <option value="dark" ${p.theme==='dark'?'selected':''}>深色</option>
            <option value="light" ${p.theme==='light'?'selected':''}>浅色</option>
          </select>
          <label style="font-size:11px;display:flex;align-items:center;gap:3px;cursor:pointer">
            <input type="checkbox" data-chart-param="show_label" ${p.show_label?'checked':''} onchange="StudioApp._onChartParamChangeB(this)"> 标签
          </label>
        </div>
        <div class="bar-actions">
          <span class="chart-type-label" style="font-size:11px;color:var(--ink-muted);margin-right:8px">${chartLabel}</span>
          <button class="bar-btn-reset" onclick="StudioApp._resetChartParams()">重置</button>
          <button class="bar-btn-render" onclick="StudioApp._renderChart('${chartType}')">渲染保存</button>
          <span class="chart-status"></span>
        </div>
      </div>`;
  },

  _onChartParamChangeB(el) {
    const key = el.dataset.chartParam;
    if (!this._svParams) this._svParams = {};
    this._svParams[key] = el.checked;
    this._updateChartPreview();
  },

  _resetChartParams() {
    this._svParams = { accent_color:'#29B8D4', point_size:10, title_size:16, axis_size:12, theme:'dark', show_label:true };
    this._renderChartUI(this._activeSlot, null);
    this._updateChartPreview();
  },

  _onChartParamChange(el) {
    const key = el.dataset.chartParam;
    const val = el.type === 'range' ? parseInt(el.value) : el.value;
    if (!this._svParams) this._svParams = {};
    this._svParams[key] = val;
    if (el.type === 'range') {
      const span = el.nextElementSibling;
      if (span && span.classList.contains('bar-val')) span.textContent = val;
    }
    this._updateChartPreview();
  },

  _svgTemplateBar(templates) {
    const tpl = this._svSelectedTpl || templates[0];
    return `
      <div class="bar-controls">
        <div class="bar-tpl-tabs">
          ${templates.map(t => `<button class="bar-tpl-tab ${t.id===tpl.id?'active':''}" data-tpl-id="${t.id}">${t.builtin?'内置':'自'}: ${this._escape(t.name)}</button>`).join('')}
          <label title="上传模板" style="cursor:pointer;font-size:11px;color:var(--ink-muted)"><input type="file" accept=".py" style="display:none" onchange="StudioApp._uploadTemplate(this)">+</label>
        </div>
        <div class="bar-params">${this._renderParamControls((tpl&&tpl.params)||[])}</div>
        <div class="bar-actions">
          <button class="btn-chart-render" data-chart="${tpl?.id||''}">生成 SVG</button>
        </div>
      </div>`;
  },

  _svgTemplateControls(templates) {
    const tpl = this._svSelectedTpl || templates[0];
    return `
      <div class="svg-tpl-tabs" style="margin-bottom:8px">
        ${templates.map(t => `
          <button class="svg-tpl-tab ${t.id === tpl.id ? 'active' : ''}" data-tpl-id="${t.id}">
            <span class="tpl-badge ${t.builtin ? 'builtin' : 'custom'}">${t.builtin ? '内置' : '自定义'}</span>
            ${this._escape(t.name)}
          </button>`).join('')}
        <label class="svg-tpl-upload-btn" title="上传模板"><input type="file" accept=".py" style="display:none" onchange="StudioApp._uploadTemplate(this)">+</label>
      </div>
      <div class="svg-params">${this._renderParamControls((tpl && tpl.params) || [])}</div>
      <div style="margin-top:8px;text-align:center">
        <button class="btn-small accent" id="svg-render-btn" style="padding:6px 18px">生成 SVG</button>
      </div>`;
  },

  /* 绑定图表按钮事件 */
  _bindChartRenderButtons() {
    // 图表类型不再需要切换（每个 slot 对应一种图表类型）
    // 渲染保存按钮通过 onclick 内联绑定
  },

  async _renderChart(templateId) {
    const isSvg = templateId.startsWith('flywheel') || templateId.startsWith('timeline');
    const params = isSvg ? this._svParams : (this._svParams || {});
    const r = await fetch(
      `/api/image-studio/${encodeURIComponent(this._company)}/${encodeURIComponent(this._activeSlot.asset_key)}/render-svg`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: templateId, params: params }) }
    );
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || '渲染失败');
    await this._refreshSlots();
    await VariantSidebar.refresh();
  },

  _renderChartEmpty(msg) {
    const stage = document.getElementById('preview-stage');
    if (stage) stage.innerHTML = `<div class="empty-state"><div class="empty-icon">&#9881;</div><p>${this._escape(msg)}</p></div>`;
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
      const r2 = await fetch('/api/svg-templates');
      const all = await r2.json();
      this._svTemplates = all.templates || [];
      if (this._activeSlot) this._showChartSlot(this._activeSlot);
    } catch (e) {
      this._toast('模板上传失败: ' + e.message, 'error');
    }
    input.value = '';
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

document.addEventListener('DOMContentLoaded', () => StudioApp.init());
