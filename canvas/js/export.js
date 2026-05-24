// PNG 导出逻辑

function exportCardAsPNG(cardIndex) {
  if (!canvas) return;

  const dataURL = canvas.toDataURL({
    format: 'png',
    multiplier: 1,
    quality: 1,
  });

  downloadDataURL(dataURL, `card_${cardIndex}.png`);
}

async function exportAllCards(allCardData, companyName) {
  showStatus('正在生成全部 7 张卡片...', 'info');

  const cardDataURLs = await renderAllCards(allCardData);
  const keys = Object.keys(cardDataURLs);

  if (keys.length === 0) {
    showStatus('没有可导出的卡片', 'error');
    return;
  }

  // 逐个下载（浏览器限制同域下载，加延迟）
  for (let i = 0; i < keys.length; i++) {
    const idx = keys[i];
    const dataURL = cardDataURLs[idx];
    const safeName = (companyName || 'company').replace(/[/\\?%*:|"<>]/g, '_');
    setTimeout(() => {
      downloadDataURL(dataURL, `${safeName}_card${idx}.png`);
    }, i * 500);
  }

  // 重新显示当前卡片
  const currentIdx = parseInt(document.getElementById('card-nav-select')?.value || '1');
  const parserData = window._currentCardData;
  if (parserData && parserData[currentIdx]) {
    displayCard(currentIdx, parserData[currentIdx]);
  }

  showStatus(`已导出 ${keys.length} 张卡片`, 'success');
}

function downloadDataURL(dataURL, filename) {
  const link = document.createElement('a');
  link.href = dataURL;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function showStatus(msg, type) {
  const el = document.getElementById('status-msg');
  if (!el) return;
  el.textContent = msg;
  el.className = `status-msg status-${type}`;
  if (type !== 'error') {
    setTimeout(() => { el.textContent = ''; el.className = 'status-msg'; }, 3000);
  }
}
