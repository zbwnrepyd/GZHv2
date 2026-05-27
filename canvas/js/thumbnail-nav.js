// 缩略图导航：为 8 张卡片生成小尺寸预览图

const THUMB_SCALE = 0.12; // 约 130×230 px
let thumbnailDataURLs = {};

async function generateThumbnails(allCardData) {
  thumbnailDataURLs = {};
  const promises = [];

  for (let i = 1; i <= 8; i++) {
    const data = allCardData[i];
    if (!data) continue;

    promises.push(
      (async (cardIndex) => {
        try {
          const dataURL = await renderCardToThumbnail(cardIndex, data);
          thumbnailDataURLs[cardIndex] = dataURL;
          updateThumbnailButton(cardIndex, dataURL);
        } catch (e) {
          console.warn(`缩略图${cardIndex}生成失败:`, e);
        }
      })(i)
    );
  }

  await Promise.all(promises);
}

function renderCardToThumbnail(cardIndex, cardData) {
  return new Promise((resolve, reject) => {
    const offCanvas = document.createElement('canvas');
    offCanvas.width = Math.round(1080 * THUMB_SCALE);
    offCanvas.height = Math.round(1920 * THUMB_SCALE);

    const fab = new fabric.Canvas(offCanvas, {
      width: offCanvas.width,
      height: offCanvas.height,
      backgroundColor: '#FFFFFF',
    });

    const layoutFn = CARD_LAYOUTS[cardIndex];
    if (!layoutFn) {
      fab.dispose();
      reject(new Error(`No layout for card ${cardIndex}`));
      return;
    }

    const elements = layoutFn(cardData);
    elements.forEach(elem => {
      const scaled = scaleElement(elem, THUMB_SCALE);
      // 缩略图中跳过图片（异步加载会引用主canvas）
      if (scaled.type === 'image') {
        const placeholder = new fabric.Rect({
          left: scaled.x || 0,
          top: scaled.y || 0,
          width: scaled.w || 100,
          height: scaled.h || 80,
          fill: '#E8EAEF',
          rx: 4,
        });
        fab.add(placeholder);
        return;
      }
      const obj = createFabricObject(scaled);
      if (Array.isArray(obj)) {
        obj.forEach(o => fab.add(o));
      } else {
        fab.add(obj);
      }
    });

    fab.renderAll();

    // 等待渲染完成
    setTimeout(() => {
      try {
        const dataURL = fab.toDataURL({ format: 'png', multiplier: 1, quality: 0.6 });
        fab.dispose();
        resolve(dataURL);
      } catch (e) {
        fab.dispose();
        reject(e);
      }
    }, 200);
  });
}

function scaleElement(elem, scale) {
  const scaled = { ...elem };
  if (scaled.x != null) scaled.x *= scale;
  if (scaled.y != null) scaled.y *= scale;
  if (scaled.w != null) scaled.w *= scale;
  if (scaled.h != null) scaled.h *= scale;
  if (scaled.r != null) scaled.r *= scale;
  if (scaled.rx != null) scaled.rx *= scale;
  if (scaled.ry != null) scaled.ry *= scale;
  if (scaled.x1 != null) scaled.x1 *= scale;
  if (scaled.y1 != null) scaled.y1 *= scale;
  if (scaled.x2 != null) scaled.x2 *= scale;
  if (scaled.y2 != null) scaled.y2 *= scale;
  if (scaled.cx != null) scaled.cx *= scale;
  if (scaled.cy != null) scaled.cy *= scale;
  if (scaled.maxWidth != null) scaled.maxWidth *= scale;
  if (scaled.strokeWidth != null) scaled.strokeWidth = Math.max(1, scaled.strokeWidth * scale);
  if (scaled.font) {
    const sizeMatch = String(scaled.font).match(/(\d+)px/);
    if (sizeMatch) {
      const newSize = Math.max(6, Math.round(parseInt(sizeMatch[1]) * scale));
      scaled.font = String(scaled.font).replace(/\d+px/, `${newSize}px`);
    }
  }
  return scaled;
}

function updateThumbnailButton(cardIndex, dataURL) {
  const btn = document.querySelector(`.card-nav-btn[data-card="${cardIndex}"]`);
  if (!btn) return;
  btn.innerHTML = '';
  const img = document.createElement('img');
  img.src = dataURL;
  img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:3px';
  btn.appendChild(img);
  btn.title = `卡片${cardIndex}`;
}

function refreshThumbnailNav(allCardData) {
  document.querySelectorAll('.card-nav-btn').forEach(btn => {
    const idx = parseInt(btn.dataset.card);
    if (allCardData && allCardData[idx]) {
      btn.style.opacity = '1';
    } else {
      btn.style.opacity = '0.4';
      btn.title = '无数据';
    }
  });

  // 异步生成缩略图
  generateThumbnails(allCardData);
}
