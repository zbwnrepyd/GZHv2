// 背景图管理：支持三种来源
// 1. URL 参数 ?bg=<base64 data URL>（Puppeteer 注入）
// 2. localStorage 缓存的 base64
// 3. 用户在制作台手动上传

const BgLoader = (() => {
  const STORAGE_KEY = 'aistartups_bg_image';

  function applyBg(dataUrl) {
    let style = document.getElementById('__bg_style');
    if (!style) {
      style = document.createElement('style');
      style.id = '__bg_style';
      document.head.appendChild(style);
    }
    style.textContent = `
      .knowledge-card {
        position: relative;
      }
      .knowledge-card::before {
        content: '';
        position: absolute;
        inset: 0;
        background-image: url('${dataUrl}');
        background-size: cover;
        background-position: center;
        opacity: var(--watermark-opacity, 0.05);
        pointer-events: none;
        z-index: 0;
      }
      .knowledge-card > * {
        position: relative;
        z-index: 1;
      }
    `;
  }

  function init() {
    const params = new URLSearchParams(window.location.search);
    const bgParam = params.get('bg');
    if (bgParam) {
      applyBg(decodeURIComponent(bgParam));
      localStorage.setItem(STORAGE_KEY, decodeURIComponent(bgParam));
      return;
    }
    const cached = localStorage.getItem(STORAGE_KEY);
    if (cached) {
      applyBg(cached);
    }
  }

  function loadFromFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const dataUrl = e.target.result;
        localStorage.setItem(STORAGE_KEY, dataUrl);
        applyBg(dataUrl);
        resolve(dataUrl);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function clear() {
    localStorage.removeItem(STORAGE_KEY);
    const style = document.getElementById('__bg_style');
    if (style) style.textContent = '';
  }

  return { init, loadFromFile, clear };
})();
