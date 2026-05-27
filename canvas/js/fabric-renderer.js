// fabric.js 渲染引擎
// 处理中文换行、元素创建和画布管理

let canvas = null;
let cardObjects = {}; // 跟踪每张卡片的 fabric 对象（用于导出前重新渲染）

function initCanvas(canvasId) {
  canvas = new fabric.Canvas(canvasId, {
    width: W,
    height: H,
    backgroundColor: COLORS.white,
    selection: false,
    preserveObjectStacking: true,
  });
  // 缩放以适应屏幕
  scaleCanvasToFit();
  window.addEventListener('resize', scaleCanvasToFit);
  return canvas;
}

function scaleCanvasToFit() {
  const container = document.getElementById('canvas-wrapper');
  if (!container || !canvas) return;
  const maxW = container.clientWidth - 40;
  const maxH = container.clientHeight - 40;
  const scale = Math.min(maxW / W, maxH / H, 0.65);
  canvas.setZoom(scale);
  canvas.setWidth(W * scale);
  canvas.setHeight(H * scale);
  canvas.renderAll();
}

/**
 * 渲染一张卡片
 * @returns {Array} fabric 对象数组
 */
function renderCard(cardIndex, cardData) {
  const layoutFn = CARD_LAYOUTS[cardIndex];
  if (!layoutFn) {
    return [createSingleText('未知卡片类型', PADDING, 200, FONTS.body, COLORS.mediumGray)];
  }

  const elements = layoutFn(cardData);
  const objects = elements.map(e => createFabricObject(e));
  cardObjects[cardIndex] = objects;
  return objects;
}

/**
 * 将布局元素转换为 fabric 对象
 */
function createFabricObject(elem) {
  switch (elem.type) {
    case 'text':
      return createWrappedText(elem);
    case 'rect':
      return new fabric.Rect({
        left: elem.x,
        top: elem.y,
        width: elem.w,
        height: elem.h,
        fill: elem.fill,
        rx: elem.rx || 0,
        ry: elem.ry || 0,
        selectable: false,
      });
    case 'line':
      return new fabric.Line(
        [elem.x1, elem.y1, elem.x2, elem.y2],
        {
          stroke: elem.stroke,
          strokeWidth: elem.strokeWidth || 2,
          selectable: false,
        }
      );
    case 'circle':
      return new fabric.Circle({
        left: elem.cx - elem.r,
        top: elem.cy - elem.r,
        radius: elem.r,
        fill: elem.fill,
        selectable: false,
      });
    case 'image':
      return createImageObject(elem);
    default:
      return createSingleText('[未知元素]', 0, 0, FONTS.small, COLORS.red);
  }
}

/**
 * 创建带中文换行的文本对象
 */
function createWrappedText(elem) {
  const text = String(elem.text || '');
  const font = elem.font || FONTS.body;
  const fontSize = extractFontSize(font);
  const maxWidth = elem.maxWidth || CONTENT_WIDTH;
  const textAlign = elem.textAlign || 'left';
  const fill = elem.fill || COLORS.darkText;
  const x = elem.x || 0;
  const y = elem.y || 0;

  // 使用 fabric.Textbox 而不是 Text — 它有原生的自动换行
  const textbox = new fabric.Textbox(text, {
    left: x,
    top: y,
    width: maxWidth,
    fontSize: fontSize,
    fontFamily: extractFontFamily(font),
    fontWeight: extractFontWeight(font),
    fill: fill,
    textAlign: textAlign,
    lineHeight: 1.6,
    charSpacing: 0,
    splitByGrapheme: true, // 对 CJK 字符按字形分割
    selectable: false,
  });

  return textbox;
}

/**
 * 创建图片对象（支持 base64 和本地路径）
 */
function createImageObject(elem) {
  const src = elem.src || '';
  if (!src) return createSingleText('[无图片]', elem.x, elem.y, FONTS.small, COLORS.mediumGray);

  // fabric.Image.fromURL 是异步的，这里用同步占位符
  const placeholder = new fabric.Rect({
    left: elem.x,
    top: elem.y,
    width: elem.w || 400,
    height: elem.h || 300,
    fill: COLORS.lightGray,
    rx: 8,
    selectable: false,
  });

  const loadingText = new fabric.Textbox('加载中...', {
    left: elem.x + 20,
    top: elem.y + (elem.h || 300) / 2 - 20,
    fontSize: 20,
    fill: COLORS.mediumGray,
    selectable: false,
  });

  // 异步加载图片
  fabric.Image.fromURL(src, (img) => {
    const scaleX = (elem.w || 400) / (img.width || 1);
    const scaleY = (elem.h || 300) / (img.height || 1);
    const scale = Math.min(scaleX, scaleY);
    img.set({
      left: elem.x + ((elem.w || 400) - img.width * scale) / 2,
      top: elem.y + ((elem.h || 300) - img.height * scale) / 2,
      scaleX: scale,
      scaleY: scale,
      selectable: false,
    });
    canvas.remove(placeholder);
    canvas.remove(loadingText);
    canvas.add(img);
    canvas.renderAll();
  }, { crossOrigin: 'anonymous' });

  return [placeholder, loadingText];
}

/**
 * 创建简单文本（兜底）
 */
function createSingleText(text, x, y, font, fill) {
  return new fabric.Textbox(text, {
    left: x,
    top: y,
    width: CONTENT_WIDTH,
    fontSize: extractFontSize(font),
    fontFamily: extractFontFamily(font),
    fontWeight: extractFontWeight(font),
    fill: fill || COLORS.mediumGray,
    textAlign: 'left',
    lineHeight: 1.5,
    splitByGrapheme: true,
    selectable: false,
  });
}

function extractFontSize(fontStr) {
  const match = String(fontStr).match(/(\d+)px/);
  return match ? parseInt(match[1]) : 28;
}

function extractFontFamily(fontStr) {
  const cleaned = String(fontStr).replace(/bold\s+|italic\s+|\d+px\s+/g, '').replace(/"/g, '');
  return cleaned.split(',')[0].trim() || 'sans-serif';
}

function extractFontWeight(fontStr) {
  return String(fontStr).startsWith('bold') ? 'bold' : 'normal';
}

/**
 * 清除画布
 */
function clearCanvas() {
  if (!canvas) return;
  canvas.clear();
  cardObjects = {};
}

/**
 * 显示卡片到画布
 */
function displayCard(cardIndex, cardData) {
  clearCanvas();
  const objects = renderCard(cardIndex, cardData);
  const flatObjects = objects.flat();
  flatObjects.forEach(obj => canvas.add(obj));
  canvas.renderAll();
}

/**
 * 渲染所有 8 张卡片（用于批量导出）
 */
async function renderAllCards(allCardData) {
  const results = {};
  for (let i = 1; i <= 8; i++) {
    const data = allCardData[i];
    if (data) {
      clearCanvas();
      const objects = renderCard(i, data);
      const flatObjects = objects.flat();
      flatObjects.forEach(obj => canvas.add(obj));
      canvas.renderAll();

      // 等待所有图片加载完成
      await waitForImages(canvas);

      results[i] = canvas.toDataURL({
        format: 'png',
        multiplier: 1,
        quality: 1,
      });
    }
  }
  return results;
}

function waitForImages(c) {
  return new Promise(resolve => {
    const images = c.getObjects().filter(obj => obj instanceof fabric.Image);
    let loaded = 0;
    if (images.length === 0) {
      resolve();
      return;
    }
    images.forEach(img => {
      if (img.complete) {
        loaded++;
      } else {
        img.onload = () => {
          loaded++;
          if (loaded >= images.length) resolve();
        };
      }
    });
    if (loaded >= images.length) resolve();
    // 超时保护
    setTimeout(resolve, 3000);
  });
}
