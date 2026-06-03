// ─── 卡片参数调节控件（无 Fabric 依赖）─────────────────────
// 在卡片制作台中间栏下方渲染手风琴式参数面板。
// 所有参数变更通过 onChange 回调通知 Workbench 实时更新预览。

const ParamControls = (() => {
  const STORAGE_KEY = 'aistartups.paramTuning';

  // ⚠️ 与 html-card-renderer.js CSS 变量保持同步
  const DEFAULT_PARAMS = {
    typography: {
      fsHero: 96, fsS1: 40, fsS2: 30, fsTagline: 56,
      fsBody: 22, fsBodySm: 17, fsLabel: 11,
      lhBody: 1.52
    },
    colors: {
      accent: '#29B8D4',
      inkPrimary: '#0D0D0D',
      inkSecondary: 'rgba(0,0,0,0.74)',
      inkMuted: 'rgba(0,0,0,0.50)',
      bgGradientTop: '#0B1629',
      bgGradientMid: '#7080A0',
      bgGradientBottom: '#FFFFFF'
    },
    spacing: {
      fieldGap: 22, fieldPadY: 12, sectionGap: 26, cardPadding: 68
    },
    layout: {
      imageTopPercent: 33, imageMaxHeightPercent: 28, imageWidthPercent: 86
    }
  };

  const TYPO_KEYS   = ['fsHero','fsS1','fsS2','fsTagline','fsBody','fsBodySm','fsLabel','lhBody'];
  const COLOR_KEYS  = ['accent','inkPrimary','inkSecondary','inkMuted','bgGradientTop','bgGradientMid','bgGradientBottom'];
  const SPACE_KEYS  = ['fieldGap','fieldPadY','sectionGap','cardPadding'];
  const LAYOUT_KEYS = ['imageTopPercent','imageMaxHeightPercent','imageWidthPercent'];

  // rgba 颜色值使用文本输入
  const RGBA_KEYS = new Set(['inkSecondary', 'inkMuted']);

  let currentParams = null;
  let onChange = null;
  let debounceTimer = null;

  function cloneDefaults() {
    return JSON.parse(JSON.stringify(DEFAULT_PARAMS));
  }

  // ══ 公开 API ══

  function init(config) {
    onChange = (config && config.onChange) || null;
    currentParams = loadFromStorage();
    if (!currentParams) {
      currentParams = cloneDefaults();
      saveToStorage();
    }
    buildControls();
    bindEvents();
    syncControlsFromParams();
    updateSavedBadge();
  }

  function getParams() {
    return currentParams;
  }

  function loadFromStorage() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  }

  function saveToStorage() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(currentParams)); } catch { /* quota */ }
    updateSavedBadge();
  }

  function resetDefaults() {
    currentParams = cloneDefaults();
    syncControlsFromParams();
    saveToStorage();
    notify();
  }

  function exportJSON() {
    const blob = new Blob([JSON.stringify(currentParams, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'card-params.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  function importJSON(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const p = JSON.parse(e.target.result);
        if (!p.typography && !p.colors) throw new Error('缺少 typography/colors 字段');
        currentParams = p;
        syncControlsFromParams();
        saveToStorage();
        notify();
      } catch (err) { alert('JSON 解析失败: ' + err.message); }
    };
    reader.readAsText(file);
  }

  // ══ 控件构建 ══

  function buildControls() {
    const container = document.getElementById('param-bar-body');
    if (!container) return;

    container.innerHTML = `
      <div class="param-sections">
        <div class="param-section" data-section="typography">
          <button class="param-section-header">排版参数</button>
          <div class="param-section-content">
            ${slider('fsHero','封面标题',48,144,1,'px')}
            ${slider('fsS1','章节标题',24,72,1,'px')}
            ${slider('fsS2','子章节',16,48,1,'px')}
            ${slider('fsTagline','标语字号',28,84,1,'px')}
            ${slider('fsBody','正文',14,36,1,'px')}
            ${slider('fsBodySm','小号正文',10,26,1,'px')}
            ${slider('fsLabel','标签',8,20,1,'px')}
            ${slider('lhBody','行高',1.1,2.0,0.01,'')}
          </div>
        </div>

        <div class="param-section" data-section="colors">
          <button class="param-section-header">颜色</button>
          <div class="param-section-content">
            <div class="param-colors">
              ${colorInput('accent','强调色')}
              ${colorInput('inkPrimary','主文字')}
              ${colorInput('inkSecondary','次文字')}
              ${colorInput('inkMuted','弱文字')}
              ${colorInput('bgGradientTop','背景顶部')}
              ${colorInput('bgGradientMid','背景中部')}
              ${colorInput('bgGradientBottom','背景下部')}
            </div>
          </div>
        </div>

        <div class="param-section" data-section="spacing">
          <button class="param-section-header">间距</button>
          <div class="param-section-content">
            ${slider('fieldGap','字段间距',8,48,1,'px')}
            ${slider('fieldPadY','字段内边距',4,32,1,'px')}
            ${slider('sectionGap','章节间距',12,56,1,'px')}
            ${slider('cardPadding','卡片边距',32,120,1,'px')}
          </div>
        </div>

        <div class="param-section" data-section="layout">
          <button class="param-section-header">布局（内页）</button>
          <div class="param-section-content">
            ${slider('imageTopPercent','图片位置 %',20,48,1,'%')}
            ${slider('imageMaxHeightPercent','图片最大高度 %',15,40,1,'%')}
            ${slider('imageWidthPercent','图片宽度 %',60,95,1,'%')}
          </div>
        </div>
      </div>

      <div class="param-bar-actions">
        <button class="btn btn-sm" id="btn-params-reset">重置默认</button>
        <button class="btn btn-sm" id="btn-params-save">保存</button>
        <button class="btn btn-sm" id="btn-params-export">导出JSON</button>
        <button class="btn btn-sm" id="btn-params-import">导入JSON</button>
        <input type="file" id="params-import-input" accept=".json" style="display:none">
      </div>
    `;
  }

  function slider(key, label, min, max, step, unit) {
    const id = 'ps-' + key;
    return `
      <div class="param-row">
        <label for="${id}">${label}</label>
        <input type="range" id="${id}" min="${min}" max="${max}" step="${step}" value="0">
        <span class="param-val" id="pv-${key}">0${unit}</span>
      </div>`;
  }

  function colorInput(key, label) {
    const id = 'pc-' + key;
    const isRgba = RGBA_KEYS.has(key);
    return `
      <div class="param-color-item">
        <label for="${id}">${label}</label>
        ${isRgba
          ? `<input type="text" id="${id}" class="param-color-text" size="22" spellcheck="false">`
          : `<input type="color" id="${id}" class="param-color-hex">`}
        <span class="param-color-swatch" id="pswatch-${key}" title="${isRgba ? '透明度预览' : ''}"></span>
      </div>`;
  }

  // ══ 事件绑定 ══

  function bindEvents() {
    const body = document.getElementById('param-bar-body');
    if (!body) return;

    // 单段手风琴：同一时间只展开一个 section
    body.querySelectorAll('.param-section-header').forEach(header => {
      header.addEventListener('click', () => {
        const target = header.nextElementSibling;
        if (!target) return;
        const opening = target.style.display === 'none';
        // 关闭所有
        body.querySelectorAll('.param-section-content').forEach(c => { c.style.display = 'none'; });
        body.querySelectorAll('.param-section-header').forEach(h => { h.classList.add('collapsed'); });
        // 打开当前
        if (opening) {
          target.style.display = '';
          header.classList.remove('collapsed');
        }
      });
    });
    // 默认展开第一个
    const firstHeader = body.querySelector('.param-section-header');
    if (firstHeader) firstHeader.click();

    // Slider + color change（所有 input 事件统一处理）
    body.addEventListener('input', (e) => {
      const el = e.target;

      if (el.type === 'range') {
        // 滑块
        const key = el.id.replace('ps-', '');
        const val = parseFloat(el.value);
        updateSliderDisplay(key, val);
        setParam(key, val);
        scheduleNotify();
      } else if (el.type === 'color') {
        // 颜色（hex）
        const key = el.id.replace('pc-', '');
        const val = el.value;
        updateSwatch(key, val);
        setParam(key, val);
        scheduleNotify();
      } else if (el.classList.contains('param-color-text')) {
        // 颜色（rgba text）
        const key = el.id.replace('pc-', '');
        const val = el.value.trim();
        updateSwatch(key, val);
        setParam(key, val);
        scheduleNotify();
      }
    });

    // Buttons
    document.getElementById('btn-params-reset')?.addEventListener('click', resetDefaults);
    document.getElementById('btn-params-save')?.addEventListener('click', () => {
      saveToStorage();
      const badge = document.getElementById('param-bar-saved');
      if (badge) { badge.textContent = '✓ 已保存'; setTimeout(() => { badge.textContent = ''; }, 2000); }
    });
    document.getElementById('btn-params-export')?.addEventListener('click', exportJSON);
    document.getElementById('btn-params-import')?.addEventListener('click', () => {
      document.getElementById('params-import-input')?.click();
    });
    document.getElementById('params-import-input')?.addEventListener('change', (e) => {
      importJSON(e.target.files[0]);
      e.target.value = '';
    });
  }

  // ══ 参数读写 ══

  function setParam(key, value) {
    if (TYPO_KEYS.includes(key))   currentParams.typography[key] = value;
    else if (COLOR_KEYS.includes(key)) currentParams.colors[key] = value;
    else if (SPACE_KEYS.includes(key)) currentParams.spacing[key] = value;
    else if (LAYOUT_KEYS.includes(key)) currentParams.layout[key] = value;
  }

  function updateSliderDisplay(key, value) {
    const slider = document.getElementById('ps-' + key);
    const display = document.getElementById('pv-' + key);
    if (slider) slider.value = value;
    if (display) display.textContent = value;
  }

  function updateSwatch(key, value) {
    const swatch = document.getElementById('pswatch-' + key);
    if (swatch) swatch.style.backgroundColor = value;
  }

  function syncControlsFromParams() {
    const t = currentParams.typography;
    for (const [k, v] of Object.entries(t)) updateSliderDisplay(k, v);
    const s = currentParams.spacing;
    for (const [k, v] of Object.entries(s)) updateSliderDisplay(k, v);
    const l = currentParams.layout;
    for (const [k, v] of Object.entries(l)) updateSliderDisplay(k, v);
    const c = currentParams.colors;
    for (const [k, v] of Object.entries(c)) {
      const input = document.getElementById('pc-' + k);
      if (input) {
        if (input.type === 'color') {
          // color input 只接受 hex，rgba 值降级为 #000
          input.value = v.startsWith('#') ? v : v.startsWith('rgb') ? '#000000' : v;
        } else {
          input.value = v;
        }
      }
      updateSwatch(k, v);
    }
  }

  // ══ 通知 ──

  function scheduleNotify() {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(notify, 200);
  }

  function notify() {
    saveToStorage();
    if (onChange) onChange(currentParams);
  }

  function updateSavedBadge() {
    const badge = document.getElementById('param-bar-saved');
    if (badge) badge.textContent = '';
  }

  return {
    init, getParams,
    loadFromStorage, saveToStorage,
    resetDefaults, exportJSON, importJSON,
  };
})();
