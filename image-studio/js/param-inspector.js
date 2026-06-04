/* param-inspector.js — 生成图右侧参数检查器 */
const ParamInspector = {
  GROUPS: [
    { id: 'content', title: '数据与文字' },
    { id: 'layout', title: '画布与版式' },
    { id: 'visual', title: '字体与颜色' },
    { id: 'chart', title: '图表专属' },
    { id: 'output', title: '输出版本' },
  ],

  render(container, schema, values, callbacks = {}, options = {}) {
    if (!container) return;
    const active = schema.activeGroup || 'content';
    if (options.mode === 'compact') {
      this._renderCompact(container, schema, values, callbacks, active);
      return;
    }
    container.innerHTML = `
      <div class="param-inspector">
        <div class="param-inspector-head">
          <h3>图表参数</h3>
          <span>${this._esc(schema.label || '生成图')}</span>
        </div>
        <div class="param-groups">
          ${this.GROUPS.map(group => this._renderGroup(group, schema, values, active)).join('')}
        </div>
        <div class="param-inspector-actions">
          <button class="btn-param-secondary" data-action="reset">恢复默认</button>
          <button class="btn-param-primary" data-action="render">生成版本</button>
          <button class="btn-param-confirm" data-action="confirm">确定这张图片</button>
        </div>
      </div>`;

    container.querySelectorAll('.param-group-title').forEach(btn => {
      btn.addEventListener('click', () => {
        schema.activeGroup = btn.dataset.group;
        this.render(container, schema, values, callbacks);
      });
    });
    container.querySelectorAll('[data-param-key]').forEach(input => {
      input.addEventListener(input.type === 'range' ? 'input' : 'change', () => {
        const key = input.dataset.paramKey;
        values[key] = this._readInput(input);
        const val = container.querySelector(`[data-param-value="${key}"]`);
        if (val) val.textContent = this._formatValue(values[key]);
        if (callbacks.onChange) callbacks.onChange(values, key);
      });
    });
    container.querySelector('[data-action="reset"]')?.addEventListener('click', () => callbacks.onReset && callbacks.onReset());
    container.querySelector('[data-action="render"]')?.addEventListener('click', () => callbacks.onRender && callbacks.onRender());
    container.querySelector('[data-action="confirm"]')?.addEventListener('click', () => callbacks.onConfirm && callbacks.onConfirm());
  },

  _renderCompact(container, schema, values, callbacks, active) {
    const fields = schema.fields || [];
    const activeFields = fields.filter(f => f.group === active);
    container.innerHTML = `
      <div class="param-inspector param-inspector-compact">
        <div class="param-compact-tabs">
          ${this.GROUPS.map(group => {
            const count = fields.filter(f => f.group === group.id).length;
            return `<button class="${active === group.id ? 'active' : ''}" data-group="${group.id}" type="button">
              <span>${group.title}</span><b>${count}</b>
            </button>`;
          }).join('')}
        </div>
        <div class="param-compact-fields">
          ${activeFields.length ? activeFields.map(field => this._renderField(field, values[field.key])).join('') : '<p class="param-empty">此组暂无参数</p>'}
        </div>
        <div class="param-compact-actions">
          <button class="btn-param-secondary" data-action="reset">默认</button>
          <button class="btn-param-primary" data-action="render">生成</button>
          <button class="btn-param-confirm" data-action="confirm">确定图片</button>
        </div>
      </div>`;

    container.querySelectorAll('[data-group]').forEach(btn => {
      btn.addEventListener('click', () => {
        schema.activeGroup = btn.dataset.group;
        this._renderCompact(container, schema, values, callbacks, schema.activeGroup);
      });
    });
    container.querySelectorAll('[data-param-key]').forEach(input => {
      input.addEventListener(input.type === 'range' ? 'input' : 'change', () => {
        const key = input.dataset.paramKey;
        values[key] = this._readInput(input);
        const val = container.querySelector(`[data-param-value="${key}"]`);
        if (val) val.textContent = this._formatValue(values[key]);
        if (callbacks.onChange) callbacks.onChange(values, key);
      });
    });
    container.querySelector('[data-action="reset"]')?.addEventListener('click', () => callbacks.onReset && callbacks.onReset());
    container.querySelector('[data-action="render"]')?.addEventListener('click', () => callbacks.onRender && callbacks.onRender());
    container.querySelector('[data-action="confirm"]')?.addEventListener('click', () => callbacks.onConfirm && callbacks.onConfirm());
  },

  schemaFor(assetKey, chartData) {
    const base = [
      { group: 'content', key: 'title', label: '标题', type: 'text' },
      { group: 'content', key: 'subtitle', label: '副标题', type: 'text' },
      { group: 'content', key: 'note', label: '图下注释', type: 'textarea' },
      { group: 'layout', key: 'width', label: '宽度', type: 'range', min: 640, max: 1200, step: 20 },
      { group: 'layout', key: 'height', label: '高度', type: 'range', min: 420, max: 1200, step: 20 },
      { group: 'visual', key: 'theme', label: '主题', type: 'select', options: [['dark', '深色'], ['light', '浅色']] },
      { group: 'visual', key: 'accent_color', label: '强调色', type: 'color' },
      { group: 'visual', key: 'title_size', label: '标题字号', type: 'range', min: 12, max: 30, step: 1 },
      { group: 'visual', key: 'label_size', label: '标签字号', type: 'range', min: 8, max: 18, step: 1 },
      { group: 'visual', key: 'show_label', label: '显示标签', type: 'checkbox' },
    ];
    const chartSpecific = {
      chart_competitive: [
        { group: 'chart', key: 'x_split', label: 'X 分割线', type: 'range', min: 1, max: 9, step: 0.5 },
        { group: 'chart', key: 'y_split', label: 'Y 分割线', type: 'range', min: 1, max: 9, step: 0.5 },
        { group: 'chart', key: 'quadrant_tl', label: '左上象限', type: 'text' },
        { group: 'chart', key: 'quadrant_tr', label: '右上象限', type: 'text' },
        { group: 'chart', key: 'quadrant_bl', label: '左下象限', type: 'text' },
        { group: 'chart', key: 'quadrant_br', label: '右下象限', type: 'text' },
        { group: 'chart', key: 'point_size', label: '基础气泡', type: 'range', min: 4, max: 28, step: 1 },
      ],
      chart_ecosystem: [
        { group: 'chart', key: 'value_threshold', label: '价值阈值', type: 'range', min: 1, max: 10, step: 0.5 },
        { group: 'chart', key: 'jitter', label: '散点抖动', type: 'range', min: 0, max: 0.5, step: 0.05 },
        { group: 'chart', key: 'point_size', label: '基础气泡', type: 'range', min: 4, max: 28, step: 1 },
      ],
      flywheel: [
        { group: 'chart', key: 'template_id', label: '模板', type: 'select', options: this._templateOptions(chartData) },
        { group: 'chart', key: 'radius', label: '环半径', type: 'range', min: 120, max: 280, step: 10 },
        { group: 'chart', key: 'node_radius', label: '节点半径', type: 'range', min: 28, max: 72, step: 2 },
        { group: 'chart', key: 'arrow_curve', label: '箭头曲率', type: 'range', min: 10, max: 80, step: 5 },
        { group: 'chart', key: 'show_desc', label: '显示描述', type: 'checkbox' },
      ],
      timeline: [
        { group: 'chart', key: 'template_id', label: '模板', type: 'select', options: this._templateOptions(chartData) },
        { group: 'chart', key: 'row_h', label: '行高', type: 'range', min: 60, max: 150, step: 5 },
        { group: 'chart', key: 'axis_x', label: '轴位置', type: 'range', min: 80, max: 320, step: 10 },
        { group: 'chart', key: 'node_size', label: '节点大小', type: 'range', min: 4, max: 18, step: 1 },
        { group: 'chart', key: 'wrap_text', label: '长文换行', type: 'checkbox' },
      ],
    };
    return {
      label: chartData?.params?.title || assetKey,
      activeGroup: 'content',
      fields: base.concat(chartSpecific[assetKey] || []),
    };
  },

  _renderGroup(group, schema, values, active) {
    const fields = (schema.fields || []).filter(f => f.group === group.id);
    const open = active === group.id;
    return `
      <section class="param-group ${open ? 'open' : ''}">
        <button class="param-group-title" data-group="${group.id}" type="button">
          <span>${group.title}</span><b>${open ? '-' : '+'}</b>
        </button>
        <div class="param-group-body">
          ${fields.length ? fields.map(field => this._renderField(field, values[field.key])).join('') : '<p class="param-empty">此组暂无参数</p>'}
        </div>
      </section>`;
  },

  _renderField(field, value) {
    const safeValue = value !== undefined && value !== null ? value : '';
    const valueText = this._formatValue(safeValue);
    if (field.type === 'textarea') {
      return `<label class="param-field"><span>${this._esc(field.label)}</span><textarea data-param-key="${field.key}">${this._esc(safeValue)}</textarea></label>`;
    }
    if (field.type === 'select') {
      const options = field.options || [];
      return `<label class="param-field"><span>${this._esc(field.label)}</span><select data-param-key="${field.key}">${options.map(([val, label]) => `<option value="${this._esc(val)}" ${String(val) === String(safeValue) ? 'selected' : ''}>${this._esc(label)}</option>`).join('')}</select></label>`;
    }
    if (field.type === 'color') {
      return `<label class="param-field compact"><span>${this._esc(field.label)}</span><input type="color" value="${this._esc(safeValue || '#29B8D4')}" data-param-key="${field.key}"></label>`;
    }
    if (field.type === 'checkbox') {
      return `<label class="param-field inline"><input type="checkbox" data-param-key="${field.key}" ${safeValue ? 'checked' : ''}><span>${this._esc(field.label)}</span></label>`;
    }
    if (field.type === 'range') {
      return `<label class="param-field"><span>${this._esc(field.label)} <b data-param-value="${field.key}">${valueText}</b></span><input type="range" min="${field.min}" max="${field.max}" step="${field.step}" value="${this._esc(safeValue)}" data-param-key="${field.key}"></label>`;
    }
    return `<label class="param-field"><span>${this._esc(field.label)}</span><input type="text" value="${this._esc(safeValue)}" data-param-key="${field.key}"></label>`;
  },

  _templateOptions(chartData) {
    const templates = chartData?.templates || [];
    if (!templates.length) return [['', '默认模板']];
    return templates.map(t => [t.id, t.name || t.id]);
  },

  _readInput(input) {
    if (input.type === 'checkbox') return input.checked;
    if (input.type === 'range') return Number(input.value);
    return input.value;
  },

  _formatValue(value) {
    if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2);
    return String(value ?? '');
  },

  _esc(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },
};
