// ─── Fabric.js 卡片参数可视化编辑器 ──────────────────────────

const ParamEditor = (() => {
  // ── 常量 ──
  const CARD_W = 900;
  const CARD_H = 1200;
  const STORAGE_KEY = 'aistartups.paramTuning';

  // ── 默认参数（与 html-card-renderer.js CSS 变量一致）──
  const DEFAULT_PARAMS = {
    $schema: 'card-params/v1',
    typography: {
      fsHero: 96, fsS1: 40, fsS2: 30, fsTagline: 56,
      fsBody: 22, fsBodySm: 17, fsLabel: 11, fsCaption: 10,
      fsData: 26, fsTimeline: 20, lhBody: 1.52, lhTight: 1.08
    },
    spacing: {
      fieldGap: 22, fieldInnerGap: 8, fieldPadY: 12,
      sectionGap: 26, cardPadding: 68
    },
    colors: {
      accent: '#29B8D4',
      inkPrimary: '#0D0D0D', inkSecondary: 'rgba(0,0,0,0.74)', inkMuted: 'rgba(0,0,0,0.50)',
      bgGradientTop: '#0B1629', bgGradientMid: '#7080A0', bgGradientBottom: '#FFFFFF'
    },
    layout: {
      cover: { titleYPercent: 12, logoYPercent: 62, taglineGap: 14 },
      generic: { imageTopPercent: 33, imageMaxHeightPercent: 28, imageWidthPercent: 86 }
    }
  };

  // ── 状态 ──
  let fabricCanvas = null;
  let currentParams = null;
  let viewMode = 'generic';        // 'cover' | 'generic'
  let previewCardIndex = 2;       // 1-8
  let companyName = '';
  let refreshTimer = null;

  // ── 深度克隆默认参数 ──
  function cloneDefaults() {
    return JSON.parse(JSON.stringify(DEFAULT_PARAMS));
  }

  // ── 初始化 ──
  function init(config = {}) {
    companyName = config.companyName || '';

    // 加载保存的参数或使用默认值
    const stored = loadFromStorage();
    currentParams = stored || cloneDefaults();

    // 初始化 Fabric 画布
    initFabric('fabric-canvas');

    // 渲染控件
    renderControlPanel();

    // 绑定事件
    bindToolbar();
    bindPanelToggles();

    // 初始渲染
    renderWireframe();
    syncControlsFromParams();
    refreshPreview();
    fitPreview();

    // 窗口大小变化时自适应
    window.addEventListener('resize', () => {
      fitCanvas();
      renderWireframe();
      fitPreview();
    });

    // 如果传了公司名，加载公司数据
    if (companyName) {
      document.getElementById('company-display').textContent = companyName;
    }
  }

  // ── Fabric 画布初始化 ──
  function initFabric(canvasId) {
    const el = document.getElementById(canvasId);
    if (!el) return;
    fabricCanvas = new fabric.Canvas(canvasId, {
      selection: true,
      preserveObjectStacking: true,
    });
    fitCanvas();
    fabricCanvas.on('object:modified', onObjectModified);
  }

  function fitCanvas() {
    if (!fabricCanvas) return;
    const container = fabricCanvas.getElement().parentElement;
    const maxW = container.clientWidth - 16;
    const maxH = container.clientHeight - 16;
    const scale = Math.min(maxW / CARD_W, maxH / CARD_H, 0.55);
    fabricCanvas.setZoom(scale);
    fabricCanvas.setWidth(CARD_W * scale);
    fabricCanvas.setHeight(CARD_H * scale);
    fabricCanvas.renderAll();
  }

  // ── 清除画布 ──
  function clearCanvas() {
    if (!fabricCanvas) return;
    fabricCanvas.clear();
    fabricCanvas.renderAll();
  }

  // ── 线框渲染 ──
  function renderWireframe() {
    if (!fabricCanvas) return;
    clearCanvas();

    // 卡片底色
    const bg = new fabric.Rect({
      left: 0, top: 0,
      width: CARD_W, height: CARD_H,
      fill: '#FFFFFF',
      selectable: false,
      evented: false,
    });
    fabricCanvas.add(bg);

    // 渐变近似：3 个色块
    const c = currentParams.colors;
    const topH = CARD_H * 0.12;
    const midH = CARD_H * 0.28;
    const rect1 = new fabric.Rect({
      left: 0, top: 0, width: CARD_W, height: topH,
      fill: c.bgGradientTop || '#0B1629',
      selectable: false, evented: false,
    });
    const rect2 = new fabric.Rect({
      left: 0, top: topH, width: CARD_W, height: midH,
      fill: c.bgGradientMid || '#7080A0',
      selectable: false, evented: false,
    });
    const rect3 = new fabric.Rect({
      left: 0, top: topH + midH, width: CARD_W, height: CARD_H - topH - midH,
      fill: c.bgGradientBottom || '#FFFFFF',
      selectable: false, evented: false,
    });
    fabricCanvas.add(rect1);
    fabricCanvas.add(rect2);
    fabricCanvas.add(rect3);

    // 内容区内边距虚线
    const pad = currentParams.spacing.cardPadding || 68;
    const padRect = new fabric.Rect({
      left: pad, top: pad,
      width: CARD_W - pad * 2, height: CARD_H - pad * 2,
      fill: '', stroke: 'rgba(0,0,0,0.12)', strokeWidth: 1,
      strokeDashArray: [8, 4],
      selectable: false, evented: false,
    });
    fabricCanvas.add(padRect);

    // 强调色条
    const accentBar = new fabric.Rect({
      left: pad, top: pad + 6,
      width: 40, height: 3,
      fill: c.accent || '#29B8D4',
      selectable: false, evented: false,
    });
    fabricCanvas.add(accentBar);

    // 根据视图模式渲染不同线框
    if (viewMode === 'cover') {
      buildCoverWireframe(pad);
    } else {
      buildGenericWireframe(pad);
    }

    fabricCanvas.renderAll();
  }

  // ── 封面线框（卡片1）──
  function buildCoverWireframe(pad) {
    const t = currentParams.typography;
    const l = currentParams.layout.cover;
    const centerX = CARD_W / 2;

    // 公众号 Logo 占位
    const gzhBox = new fabric.Rect({
      left: centerX - 90, top: pad,
      width: 180, height: 36,
      fill: '#EEEEEE', stroke: '#CCCCCC', strokeWidth: 1,
      rx: 4, ry: 4,
    });
    const gzhLabel = new fabric.Text('GZH Logo', {
      left: centerX - 90, top: pad + 10,
      fontSize: 11, fill: '#999999',
      fontFamily: 'sans-serif',
    });
    fabricCanvas.add(gzhBox);
    fabricCanvas.add(gzhLabel);

    // 标语
    const taglineY = pad + 60;
    const taglineText = new fabric.Text('「三分钟认识一家AI初创公司」', {
      left: centerX, top: taglineY,
      fontSize: Math.round(t.fsTagline * 0.42), fill: '#000000',
      fontFamily: 'serif', textAlign: 'center',
      originX: 'center',
      selectable: true, hasControls: false,
    });
    fabricCanvas.add(taglineText);

    // 公司名
    const titleY = taglineY + l.taglineGap + 30;
    const titleText = new fabric.Text('公司名称', {
      left: centerX, top: titleY,
      fontSize: Math.round(t.fsHero * 0.50), fill: '#000000',
      fontFamily: 'serif', fontWeight: 'bold', textAlign: 'center',
      originX: 'center',
      selectable: true, hasControls: false,
    });
    fabricCanvas.add(titleText);

    // Logo 区域
    const logoY = (CARD_H * l.logoYPercent) / 100;
    const logoBox = new fabric.Rect({
      left: centerX - 110, top: logoY - 60,
      width: 220, height: 120,
      fill: '#F5F5F5', stroke: '#DDDDDD', strokeWidth: 1,
      rx: 4, ry: 4,
    });
    const logoLabel = new fabric.Text('LOGO', {
      left: centerX, top: logoY - 16,
      fontSize: 14, fill: '#AAAAAA',
      fontFamily: 'sans-serif', textAlign: 'center',
      originX: 'center',
    });
    fabricCanvas.add(logoBox);
    fabricCanvas.add(logoLabel);

    // 类型标签
    const typeY = logoY + 80;
    const typeText = new fabric.Text('公司类型标签', {
      left: centerX, top: typeY,
      fontSize: Math.round(t.fsTagline * 0.42), fill: '#000000',
      fontFamily: 'sans-serif', fontWeight: 'bold', textAlign: 'center',
      originX: 'center',
      selectable: true, hasControls: false,
    });
    fabricCanvas.add(typeText);
  }

  // ── 通用线框（卡片2-8）──
  function buildGenericWireframe(pad) {
    const t = currentParams.typography;
    const l = currentParams.layout.generic;
    const contentW = CARD_W - pad * 2;

    // 章节标题
    const titleText = new fabric.Text('章节标题', {
      left: pad, top: pad + 20,
      fontSize: Math.round(t.fsS1 * 0.50), fill: '#000000',
      fontFamily: 'serif',
      selectable: true, hasControls: false,
    });
    fabricCanvas.add(titleText);

    const imgTop = (CARD_H * l.imageTopPercent) / 100;
    const imgW = (CARD_W * l.imageWidthPercent) / 100;
    const imgH = (CARD_H * l.imageMaxHeightPercent) / 100;
    const imgLeft = (CARD_W - imgW) / 2;

    // 图片标题
    const imgTitleY = imgTop - imgH / 2 - 80;
    if (imgTitleY > pad + 40) {
      const imgTitleText = new fabric.Text('图片标题', {
        left: CARD_W / 2, top: imgTitleY,
        fontSize: Math.round(t.fsTagline * 0.40), fill: '#000000',
        fontFamily: 'sans-serif', fontWeight: 'bold', textAlign: 'center',
        originX: 'center',
        selectable: true, hasControls: false,
      });
      fabricCanvas.add(imgTitleText);
    }

    // 图片区域
    const imgBox = new fabric.Rect({
      left: imgLeft, top: imgTop - imgH / 2,
      width: imgW, height: imgH,
      fill: '#F0F4F8', stroke: '#CBD5E1', strokeWidth: 1,
      rx: 6, ry: 6,
      selectable: true,
    });
    imgBox.set({ _paramKey: 'layout.generic.imageTopPercent' });
    const imgLabel = new fabric.Text('IMAGE', {
      left: CARD_W / 2, top: imgTop - 14,
      fontSize: 16, fill: '#94A3B8',
      fontFamily: 'sans-serif', textAlign: 'center',
      originX: 'center',
    });
    fabricCanvas.add(imgBox);
    fabricCanvas.add(imgLabel);

    // 正文区域
    const bodyY = imgTop + imgH / 2 + 70;
    if (bodyY < CARD_H - pad - 40) {
      const bodyH = CARD_H - pad - bodyY;
      const bodyBox = new fabric.Rect({
        left: pad, top: bodyY,
        width: contentW, height: bodyH,
        fill: '#FAFBFC', stroke: '#E2E8F0', strokeWidth: 1,
        strokeDashArray: [4, 4], rx: 4, ry: 4,
      });
      const bodyCenterY = bodyY + bodyH / 2;
      const bodyLabel1 = new fabric.Text('正文内容', {
        left: CARD_W / 2, top: bodyCenterY - 24,
        fontSize: 16, fill: '#94A3B8',
        fontFamily: 'sans-serif', textAlign: 'center',
        originX: 'center',
      });
      const bodyLabel2 = new fabric.Text('（键值对 · 列表 · 段落）', {
        left: CARD_W / 2, top: bodyCenterY + 4,
        fontSize: 12, fill: '#CBD5E1',
        fontFamily: 'sans-serif', textAlign: 'center',
        originX: 'center',
      });
      fabricCanvas.add(bodyBox);
      fabricCanvas.add(bodyLabel1);
      fabricCanvas.add(bodyLabel2);
    }
  }

  // ── Fabric 对象修改 → 更新参数 ──
  function onObjectModified(e) {
    const obj = e.target;
    if (!obj || !obj._paramKey) return;

    // 根据 paramKey 反算参数值
    // 目前仅支持 imageTopPercent 的拖拽映射
    if (obj._paramKey === 'layout.generic.imageTopPercent') {
      const newTop = obj.top + obj.height / 2;
      const percent = Math.round((newTop / CARD_H) * 100);
      currentParams.layout.generic.imageTopPercent = Math.max(20, Math.min(45, percent));
      syncControlsFromParams();
      scheduleRefresh();
    }
  }

  // ── 控件面板 ──
  function renderControlPanel() {
    renderSliders();
    bindColorPickers();
  }

  function renderSliders() {
    const t = currentParams.typography;
    const s = currentParams.spacing;
    const l = currentParams.layout;

    // 排版滑块
    setSlider('fsHero', t.fsHero, 48, 144, 1);
    setSlider('fsS1', t.fsS1, 24, 72, 1);
    setSlider('fsS2', t.fsS2, 16, 48, 1);
    setSlider('fsTagline', t.fsTagline, 28, 84, 1);
    setSlider('fsBody', t.fsBody, 14, 36, 1);
    setSlider('fsBodySm', t.fsBodySm, 10, 26, 1);
    setSlider('fsLabel', t.fsLabel, 8, 20, 1);
    setSlider('lhBody', t.lhBody, 1.1, 2.0, 0.01);

    // 间距滑块
    setSlider('fieldGap', s.fieldGap, 8, 48, 1);
    setSlider('fieldPadY', s.fieldPadY, 4, 32, 1);
    setSlider('sectionGap', s.sectionGap, 12, 56, 1);
    setSlider('cardPadding', s.cardPadding, 32, 120, 1);

    // 布局滑块
    setSlider('imageTopPercent', l.generic.imageTopPercent, 20, 48, 1);
    setSlider('imageMaxHeightPercent', l.generic.imageMaxHeightPercent, 15, 40, 1);
    setSlider('imageWidthPercent', l.generic.imageWidthPercent, 60, 95, 1);
  }

  function setSlider(id, value, min, max, step) {
    const slider = document.getElementById('slider-' + id);
    const display = document.getElementById('val-' + id);
    if (!slider || !display) return;
    slider.min = min;
    slider.max = max;
    slider.step = step;
    slider.value = value;
    slider._paramKey = id;
    display.textContent = value;
  }

  function bindPanelToggles() {
    document.querySelectorAll('.panel-section-header').forEach(header => {
      header.addEventListener('click', () => {
        const section = header.parentElement;
        const body = section.querySelector('.panel-section-body');
        const icon = header.querySelector('.toggle-icon');
        if (body) {
          const open = body.style.display !== 'none';
          body.style.display = open ? 'none' : 'block';
          if (icon) icon.textContent = open ? '▸' : '▾';
        }
      });
    });
  }

  // ── 颜色选择器 ──
  function bindColorPickers() {
    document.querySelectorAll('.param-color-input').forEach(input => {
      input.addEventListener('input', (e) => {
        const key = e.target.dataset.paramKey;
        if (!key) return;
        const value = e.target.value;
        setParamByPath(key, value);
        syncControlsFromParams();
        renderWireframe();
        scheduleRefresh();
      });
      // 初始值
      const key = input.dataset.paramKey;
      if (key) {
        input.value = getParamByPath(key) || '#000000';
      }
    });
  }

  function getParamByPath(path) {
    const parts = path.split('.');
    let obj = currentParams;
    for (const p of parts) {
      if (!obj) return null;
      obj = obj[p];
    }
    return obj;
  }

  function setParamByPath(path, value) {
    const parts = path.split('.');
    let obj = currentParams;
    for (let i = 0; i < parts.length - 1; i++) {
      obj = obj[parts[i]];
    }
    obj[parts[parts.length - 1]] = value;
  }

  // ── 滑块变化处理 ──
  function onSliderInput(e) {
    const slider = e.target;
    const key = slider._paramKey;
    const value = parseFloat(slider.value);
    if (!key) return;

    // 更新显示值
    const display = document.getElementById('val-' + key);
    if (display) display.textContent = value;

    // 更新参数
    updateParamByKey(key, value);

    // 实时更新线框和预览
    renderWireframe();
    scheduleRefresh();
  }

  function updateParamByKey(key, value) {
    const tKeys = ['fsHero','fsS1','fsS2','fsTagline','fsBody','fsBodySm','fsLabel','fsCaption','fsData','fsTimeline','lhBody','lhTight'];
    const sKeys = ['fieldGap','fieldInnerGap','fieldPadY','sectionGap','cardPadding'];
    const lKeys = ['imageTopPercent','imageMaxHeightPercent','imageWidthPercent'];

    if (tKeys.includes(key)) {
      currentParams.typography[key] = value;
    } else if (sKeys.includes(key)) {
      currentParams.spacing[key] = value;
    } else if (lKeys.includes(key)) {
      currentParams.layout.generic[key] = value;
    }
  }

  // ── 同步控件值 ──
  function syncControlsFromParams() {
    const t = currentParams.typography;
    const s = currentParams.spacing;
    const l = currentParams.layout;
    const c = currentParams.colors;

    // 排版
    updateSliderDisplay('fsHero', t.fsHero);
    updateSliderDisplay('fsS1', t.fsS1);
    updateSliderDisplay('fsS2', t.fsS2);
    updateSliderDisplay('fsTagline', t.fsTagline);
    updateSliderDisplay('fsBody', t.fsBody);
    updateSliderDisplay('fsBodySm', t.fsBodySm);
    updateSliderDisplay('fsLabel', t.fsLabel);
    updateSliderDisplay('lhBody', t.lhBody);

    // 间距
    updateSliderDisplay('fieldGap', s.fieldGap);
    updateSliderDisplay('fieldPadY', s.fieldPadY);
    updateSliderDisplay('sectionGap', s.sectionGap);
    updateSliderDisplay('cardPadding', s.cardPadding);

    // 布局
    updateSliderDisplay('imageTopPercent', l.generic.imageTopPercent);
    updateSliderDisplay('imageMaxHeightPercent', l.generic.imageMaxHeightPercent);
    updateSliderDisplay('imageWidthPercent', l.generic.imageWidthPercent);

    // 颜色
    document.querySelectorAll('.param-color-input').forEach(input => {
      const key = input.dataset.paramKey;
      if (key) input.value = getParamByPath(key) || '#000000';
    });
  }

  function updateSliderDisplay(id, value) {
    const slider = document.getElementById('slider-' + id);
    const display = document.getElementById('val-' + id);
    if (slider) slider.value = value;
    if (display) display.textContent = value;
  }

  // ── Unicode-safe base64 编码 ──
  function toBase64(str) {
    const bytes = new TextEncoder().encode(str);
    const chars = [];
    for (let i = 0; i < bytes.length; i++) {
      chars.push(String.fromCharCode(bytes[i]));
    }
    return btoa(chars.join(''));
  }

  // ── 预览刷新（防抖 300ms）──
  function scheduleRefresh() {
    if (refreshTimer) clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refreshPreview, 300);
  }

  function refreshPreview() {
    const iframe = document.getElementById('preview-frame');
    if (!iframe || !companyName) return;
    const json = JSON.stringify(currentParams);
    const base64 = toBase64(json);
    const urlSafe = encodeURIComponent(base64);
    iframe.src = `/canvas/card/${encodeURIComponent(companyName)}/${previewCardIndex}?params=${urlSafe}`;
  }

  // ── iframe 缩放 ──
  function fitPreview() {
    const panel = document.getElementById('preview-panel');
    const iframe = document.getElementById('preview-frame');
    if (!panel || !iframe) return;
    const pw = panel.clientWidth;
    const ph = panel.clientHeight;
    const scale = Math.min(pw / 900, ph / 1200, 0.52);
    iframe.style.transform = `scale(${scale})`;
    iframe.style.width = '900px';
    iframe.style.height = '1200px';
  }

  // ── 工具栏 ──
  function bindToolbar() {
    // 视图模式切换
    document.querySelectorAll('.view-mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.view-mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        setViewMode(btn.dataset.mode);
      });
    });

    // 预览卡片切换
    const cardSelect = document.getElementById('preview-card-select');
    if (cardSelect) {
      cardSelect.value = previewCardIndex;
      cardSelect.addEventListener('change', (e) => {
        previewCardIndex = parseInt(e.target.value) || 2;
        document.getElementById('preview-card-label').textContent = previewCardIndex;
        refreshPreview();
      });
    }

    // 加载默认
    document.getElementById('btn-load-defaults')?.addEventListener('click', () => {
      resetToDefaults();
    });

    // 从 localStorage 加载
    document.getElementById('btn-load-storage')?.addEventListener('click', () => {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        try {
          currentParams = JSON.parse(stored);
          onParamsChanged();
        } catch (e) {
          alert('解析存储的参数失败: ' + e.message);
        }
      } else {
        alert('本地没有保存的参数。');
      }
    });

    // 保存到 localStorage
    document.getElementById('btn-save-storage')?.addEventListener('click', () => {
      saveToStorage();
      alert('参数已保存到本地存储。');
    });

    // 导出 JSON
    document.getElementById('btn-export')?.addEventListener('click', () => {
      exportJSONFile();
    });

    // 导入 JSON
    document.getElementById('btn-import')?.addEventListener('click', () => {
      document.getElementById('import-file-input')?.click();
    });
    document.getElementById('import-file-input')?.addEventListener('change', (e) => {
      importJSONFile(e.target.files[0]);
      e.target.value = '';
    });

    // 滑块事件
    document.getElementById('control-panel').addEventListener('input', (e) => {
      if (e.target.tagName === 'INPUT' && e.target.type === 'range') {
        onSliderInput(e);
      }
    });
  }

  function onParamsChanged() {
    renderWireframe();
    syncControlsFromParams();
    renderSliders();
    refreshPreview();
  }

  function setViewMode(mode) {
    viewMode = mode;
    renderWireframe();
  }

  // ── 序列化 ──
  function loadFromStorage() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch (e) {
      return null;
    }
  }

  function saveToStorage() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(currentParams));
  }

  function exportJSONFile() {
    const json = JSON.stringify(currentParams, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `card-params-${companyName || 'template'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function importJSONFile(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const params = JSON.parse(e.target.result);
        // 基本校验
        if (!params.typography && !params.colors && !params.spacing) {
          alert('无效的参数文件：缺少 typography/colors/spacing 字段。');
          return;
        }
        currentParams = params;
        onParamsChanged();
        alert('参数已导入。');
      } catch (err) {
        alert('JSON 解析失败: ' + err.message);
      }
    };
    reader.readAsText(file);
  }

  function resetToDefaults() {
    currentParams = cloneDefaults();
    onParamsChanged();
  }

  // ── 公开 API ──
  return {
    init,
    loadFromStorage,
    saveToStorage,
    exportJSONFile,
    importJSONFile,
    resetToDefaults,
    setViewMode,
    refreshPreview,
  };
})();
