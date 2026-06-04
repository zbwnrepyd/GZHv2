/* workspace-chart.js — 生成图工作区 */
const WorkspaceChart = {
  _company: '',
  _slot: null,
  _params: {},
  _defaults: {},
  _data: null,
  _schema: null,
  _previewTimer: 0,
  _latestPreviewHtml: '',
  _latestVariantId: null,
  _onRefresh: null,
  _toast: null,

  async mount({ company, slot, editorArea, candidatePanel, onRefresh, onToast }) {
    if (!editorArea || !candidatePanel || !slot) return;
    this._company = company;
    this._slot = slot;
    this._latestVariantId = slot.selected_variant ? slot.selected_variant.id : null;
    this._onRefresh = onRefresh;
    this._toast = onToast || (() => {});
    document.body.classList.add('chart-mode');

    editorArea.classList.remove('image-editor-area');
    editorArea.classList.add('chart-editor-area');
    candidatePanel.classList.remove('candidate-panel');
    candidatePanel.classList.add('param-panel');
    editorArea.innerHTML = this._shell(slot);
    candidatePanel.innerHTML = '<div class="param-loading">加载图表参数...</div>';

    try {
      this._data = await StudioAPI.chartData(company, slot.asset_key);
      this._defaults = Object.assign({}, this._data.params || {});
      this._params = Object.assign({}, this._defaults);
      this._schema = ParamInspector.schemaFor(slot.asset_key, this._data);
      this._renderInspector(candidatePanel);
      await this._updatePreviewNow();
    } catch (e) {
      candidatePanel.innerHTML = `<div class="param-error">加载失败：${this._esc(e.message)}</div>`;
      this._setPreviewError(e.message);
    }
  },

  _shell(slot) {
    const label = this._label(slot.asset_key);
    const isEcharts = slot.asset_key === 'chart_competitive' || slot.asset_key === 'chart_ecosystem';
    return `
      <section class="demand-workspace chart-workspace ${isEcharts ? 'echarts-workspace' : ''}">
        <header class="workspace-header">
          <div>
            <h2>${this._esc(label)}</h2>
            <p>生成图 · 实时预览 · 参数调整后不会自动确定</p>
          </div>
          <span class="workspace-status ${slot.status || 'missing'}">${slot.status === 'ready' ? '已确定' : '待确定'}</span>
        </header>
        <div class="chart-preview-stage">
          <iframe id="chart-live-preview" title="${this._esc(label)}预览"></iframe>
        </div>
        <div id="chart-param-bottom" class="chart-param-bottom"></div>
        <footer class="workspace-footer">
          <button class="workspace-secondary" type="button" data-chart-action="refresh">刷新预览</button>
          <span id="chart-workspace-status">参数变化后自动预览</span>
        </footer>
      </section>`;
  },

  _renderInspector(candidatePanel) {
    const paramHost = document.getElementById('chart-param-bottom');
    if (this._isEchartsSlot()) {
      candidatePanel.innerHTML = this._rightCodeShell();
    } else {
      candidatePanel.innerHTML = this._rightActionShell();
    }
    ParamInspector.render(paramHost, this._schema, this._params, {
      onChange: () => this._schedulePreview(),
      onReset: () => {
        this._params = Object.assign({}, this._defaults);
        this._renderInspector(candidatePanel);
        this._schedulePreview();
      },
      onRender: () => this._renderVersion(),
      onConfirm: () => this._confirmLatest(),
    }, { mode: 'compact' });
    document.querySelector('[data-chart-action="refresh"]')?.addEventListener('click', () => this._updatePreviewNow());
    document.querySelector('[data-chart-action="render"]')?.addEventListener('click', () => this._renderVersion());
    document.querySelector('[data-chart-action="confirm"]')?.addEventListener('click', () => this._confirmLatest());
    this._bindCodeEditor();
    this._syncCodeEditor();
  },

  _rightCodeShell() {
    return `
      <div class="chart-right-dock code-only">
        <section class="echarts-code-panel">
          <div class="echarts-code-head">
            <div>
              <h3>ECharts 代码</h3>
              <span>修改后实时刷新预览</span>
            </div>
          </div>
          <div class="chart-code-editor-wrap">
            <pre id="chart-code-highlight" class="chart-code-highlight" aria-hidden="true"><code></code></pre>
            <textarea id="chart-code-editor" class="chart-code-editor" spellcheck="false" autocapitalize="off" autocomplete="off"></textarea>
          </div>
        </section>
        ${this._confirmDock()}
      </div>`;
  },

  _rightActionShell() {
    return `
      <div class="chart-right-dock">
        <section class="chart-action-panel">
          <div class="echarts-code-head">
            <div>
              <h3>图表操作</h3>
              <span>参数在下方调整，预览实时刷新</span>
            </div>
          </div>
          <div class="chart-action-copy">
            <p>当前图表使用 SVG 模板渲染。先在下方调整文字、尺寸、颜色和模板参数，再生成 PNG 版本。</p>
            <p>生成后点击右下角确定图片，会写入图片夹供排版画布使用。</p>
          </div>
        </section>
        ${this._confirmDock()}
      </div>`;
  },

  _confirmDock() {
    return `
      <div class="chart-confirm-dock">
        <button class="workspace-secondary" type="button" data-chart-action="render">生成版本</button>
        <button class="workspace-primary" type="button" data-chart-action="confirm">确定图片</button>
      </div>`;
  },

  _bindCodeEditor() {
    const textarea = document.getElementById('chart-code-editor');
    if (!textarea) return;
    textarea.addEventListener('input', () => {
      this._syncCodeHighlight(textarea.value);
      this._applyCodePreview();
    });
    textarea.addEventListener('scroll', () => this._syncCodeScroll());
  },

  _applyCodePreview() {
    const textarea = document.getElementById('chart-code-editor');
    const iframe = document.getElementById('chart-live-preview');
    const status = document.getElementById('chart-workspace-status');
    if (!textarea || !iframe) return;
    this._latestPreviewHtml = textarea.value;
    iframe.srcdoc = this._latestPreviewHtml;
    if (status) status.textContent = '已实时应用代码';
  },

  _syncCodeEditor() {
    const textarea = document.getElementById('chart-code-editor');
    if (!textarea) return;
    textarea.value = this._latestPreviewHtml || '';
    this._syncCodeHighlight(textarea.value);
    this._syncCodeScroll();
  },

  _syncCodeScroll() {
    const textarea = document.getElementById('chart-code-editor');
    const highlight = document.getElementById('chart-code-highlight');
    if (!textarea || !highlight) return;
    highlight.scrollTop = textarea.scrollTop;
    highlight.scrollLeft = textarea.scrollLeft;
  },

  _syncCodeHighlight(value) {
    const code = document.querySelector('#chart-code-highlight code');
    if (!code) return;
    code.innerHTML = this._highlightCode(value || '') + '\n';
  },

  _highlightCode(value) {
    const esc = (s) => this._esc(s);
    let html = esc(value);
    html = html.replace(/(&lt;!--[\s\S]*?--&gt;)/g, '<span class="tok-comment">$1</span>');
    html = html.replace(/('(?:\\\\.|[^'\\\\])*'|"(?:\\\\.|[^"\\\\])*"|`(?:\\\\.|[^`\\\\])*`)/g, '<span class="tok-string">$1</span>');
    html = html.replace(/(&lt;\/?[\s\S]*?&gt;)/g, '<span class="tok-tag">$1</span>');
    html = html.replace(/\b(var|let|const|function|return|if|else|for|while|new|true|false|null|undefined)\b/g, '<span class="tok-keyword">$1</span>');
    html = html.replace(/\b(echarts|setOption|init|series|xAxis|yAxis|grid|graphic|markLine|markArea|tooltip|legend|color|backgroundColor)\b/g, '<span class="tok-api">$1</span>');
    return html;
  },

  _schedulePreview() {
    clearTimeout(this._previewTimer);
    this._previewTimer = setTimeout(() => this._updatePreviewNow(), 300);
  },

  async _updatePreviewNow() {
    const iframe = document.getElementById('chart-live-preview');
    const status = document.getElementById('chart-workspace-status');
    if (!iframe || !this._slot) return;
    if (status) status.textContent = '正在刷新预览...';
    try {
      let html;
      if (this._isEchartsSlot()) {
        html = await StudioAPI.previewChart(this._company, this._slot.asset_key, this._params, this._data?.data || {});
      } else {
        html = await this._previewSvgTemplate();
      }
      this._latestPreviewHtml = html;
      iframe.srcdoc = html;
      this._syncPreviewAspect();
      this._syncCodeEditor();
      if (status) status.textContent = '预览已更新';
    } catch (e) {
      this._setPreviewError(e.message);
      if (status) status.textContent = '预览失败';
    }
  },

  async _previewSvgTemplate() {
    const templateId = this._params.template_id || this._defaults.template_id;
    const r = await fetch('/api/svg-templates/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template_id: templateId,
        params: this._params,
        data: this._data?.data || {},
      }),
    });
    if (!r.ok) throw new Error(await r.text());
    const svg = await r.text();
    return `<html><head><style>
      html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#f8fafc}
      body{display:flex;align-items:center;justify-content:center;box-sizing:border-box;padding:12px}
      svg{display:block;max-width:86%;max-height:86%;width:auto;height:auto}
    </style></head><body>${svg}</body></html>`;
  },

  _syncPreviewAspect() {
    const iframe = document.getElementById('chart-live-preview');
    if (!iframe) return;
    const w = Number(this._params.width || this._defaults.width || 900);
    const h = Number(this._params.height || this._defaults.height || 600);
    const aspect = w > 0 && h > 0 ? `${w} / ${h}` : '16 / 9';
    iframe.style.setProperty('--chart-aspect', aspect);
  },

  async _renderVersion() {
    if (!this._slot) return;
    const status = document.getElementById('chart-workspace-status');
    const templateId = this._params.template_id || this._data?.chart_type || this._slot.asset_key;
    try {
      if (status) status.textContent = '正在生成 PNG 版本...';
      let result;
      const codeEditor = document.getElementById('chart-code-editor');
      if (this._isEchartsSlot() && codeEditor) {
        result = await StudioAPI.renderChartHtml(this._company, this._slot.asset_key, codeEditor.value, this._params);
      } else {
        result = await StudioAPI.renderChart(this._company, this._slot.asset_key, templateId, this._params);
      }
      this._latestVariantId = result.variant_id;
      if (status) status.textContent = '已生成版本，可点击确定';
      this._toast('已生成图表版本');
      if (this._onRefresh) this._onRefresh();
    } catch (e) {
      if (status) status.textContent = '生成失败';
      this._toast('生成失败: ' + e.message, 'error');
    }
  },

  async _confirmLatest() {
    if (!this._latestVariantId) {
      this._toast('请先生成一个版本，或选择已有版本', 'error');
      return;
    }
    try {
      await StudioAPI.selectVariant(this._company, this._slot.asset_key, this._latestVariantId);
      this._toast('已确定这张图片');
      if (this._onRefresh) this._onRefresh();
    } catch (e) {
      this._toast('确定失败: ' + e.message, 'error');
    }
  },

  _setPreviewError(message) {
    const iframe = document.getElementById('chart-live-preview');
    if (!iframe) return;
    iframe.srcdoc = `<html><body style="margin:0;display:flex;align-items:center;justify-content:center;height:100vh;font:14px sans-serif;color:#64748b;background:#f8fafc">预览失败：${this._esc(message)}</body></html>`;
  },

  _isEchartsSlot() {
    return this._slot && (this._slot.asset_key === 'chart_competitive' || this._slot.asset_key === 'chart_ecosystem');
  },

  _label(assetKey) {
    return (window.DEMAND_LABELS && window.DEMAND_LABELS[assetKey]) || assetKey;
  },

  _esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },
};
