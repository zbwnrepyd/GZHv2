/* search-panel.js — 图库搜索 + 候选网格 + 翻页 */
const SearchPanel = {
  _company: '',
  _assetKey: '',
  _currentQuery: '',
  _currentSource: 'pexels',
  _currentLang: 'en',
  _currentPage: 1,
  _totalResults: 0,
  _perPage: 9,
  _loading: false,
  _onFetch: null, // callback(imageData) — 用户点击候选图时触发
  _slotImage: '',  // 当前槽位已有的图片 local_path

  init(container, { onFetch }) {
    this._container = container;
    this._onFetch = onFetch;
    this._render();
  },

  setContext(company, assetKey) {
    this._company = company;
    this._assetKey = assetKey;
    this._currentPage = 1;
    this._totalResults = 0;
  },

  setSlotImage(localPath) {
    this._slotImage = localPath || '';
    this._renderCurrentImage();
  },

  setQueries(queries) {
    this._queries = queries;
    // 渲染关键词展示标签，不预填搜索框
    this._renderKeywordGroups();
  },

  search(query) {
    if (query !== undefined) this._currentQuery = query;
    this._currentPage = 1;
    this._doSearch();
  },

  _doSearch() {
    if (this._loading) return;
    if (!this._currentQuery.trim()) return;

    this._loading = true;
    this._renderGridLoading();

    StudioAPI.search(this._company, this._assetKey, {
      query: this._currentQuery,
      source: this._currentSource,
      lang: this._currentLang,
      page: this._currentPage,
      perPage: this._perPage,
    }).then(data => {
      this._totalResults = data.total || 0;
      this._renderGrid(data.results || []);
      this._renderDefaultCandidates(data.results || []);
      this._renderPagination();
      this._loading = false;
      if (data.error) this._showEmpty(data.error);
    }).catch(err => {
      this._showEmpty(err.message);
      this._loading = false;
    });
  },

  /* ── Render ── */

  _render() {
    this._container.innerHTML = `
      <!-- 1. 搜索区 -->
      <div class="search-section">
        <div class="search-row">
          <input class="search-input" type="text" placeholder="输入搜索关键词..." value="">
          <select class="source-select">
            <option value="pexels">Pexels</option>
            <option value="unsplash">Unsplash</option>
            <option value="tavily">Tavily</option>
          </select>
          <button class="search-btn">搜索</button>
        </div>
      </div>
      <!-- 2. 关键词标签（展示用） -->
      <div class="keyword-tags-section hidden" id="keyword-tags-section">
        <div class="keyword-tags-row" id="keyword-tags-row"></div>
      </div>
      <!-- 3. 当前图片 -->
      <div class="current-image-section hidden"><span class="current-image-label">当前图片</span><div class="current-image-preview"></div></div>
      <!-- 4. 已入库候选 -->
      <div class="variant-library-section">
        <div class="variant-library-head">
          <h4>候选图片</h4>
          <span id="variant-count-label">0 张</span>
        </div>
        <div class="variant-list variant-list-main" id="variant-list-main"></div>
      </div>
      <!-- 5. 默认+候选 -->
      <div class="default-candidates-section hidden" id="default-candidates-section">
        <h4>推荐候选</h4>
        <div class="default-candidate-row" id="default-candidate-row"></div>
      </div>
      <!-- 6. 搜索结果网格 -->
      <div class="candidate-grid-container">
        <div class="candidate-grid"></div>
        <div class="pagination"></div>
      </div>
    `;

    // Events
    this._container.querySelector('.search-btn').addEventListener('click', () => {
      this._currentQuery = this._container.querySelector('.search-input').value;
      this.search();
    });
    this._container.querySelector('.search-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        this._currentQuery = e.target.value;
        this.search();
      }
    });
    this._container.querySelector('.source-select').addEventListener('change', (e) => {
      this._currentSource = e.target.value;
      if (this._currentSource === 'unsplash') this._currentLang = 'en';
      else if (this._currentSource === 'pexels') this._currentLang = 'zh';
      if (this._queries && this._queries.length) {
        const q = this._queries[0];
        this._currentQuery = this._currentLang === 'zh' ? q.zh : q.en;
        this._container.querySelector('.search-input').value = this._currentQuery;
      }
      this.search();
    });
  },

  _renderCurrentImage() {
    const section = this._container.querySelector('.current-image-section');
    const preview = this._container.querySelector('.current-image-preview');
    if (!section || !preview) return;
    if (this._slotImage) {
      section.classList.remove('hidden');
      preview.innerHTML = `<img src="${this._escape(this._slotImage)}" alt="当前图片" onerror="this.parentElement.innerHTML='<span style=color:var(--ink-muted);font-size:12px>图片加载失败</span>'">`;
    } else {
      section.classList.add('hidden');
      preview.innerHTML = '';
    }
  },

  _renderKeywordGroups() {
    const section = document.getElementById('keyword-tags-section');
    const row = document.getElementById('keyword-tags-row');
    if (!section || !row) return;
    const queries = this._queries || [];
    if (!queries.length) {
      section.classList.add('hidden');
      return;
    }
    section.classList.remove('hidden');
    row.innerHTML = queries.map((q) => {
      const zh = this._escape(q.zh || '');
      const en = this._escape(q.en || '');
      return `<span class="keyword-tag-display" title="${en}">${zh}</span>`;
    }).join('');
    // 展示用，不绑定点击
  },

  _renderDefaultCandidates(results) {
    const section = document.getElementById('default-candidates-section');
    const row = document.getElementById('default-candidate-row');
    if (!section || !row) return;

    const candidates = results.slice(0, 3);
    if (!this._slotImage && !candidates.length) {
      section.classList.add('hidden');
      return;
    }
    section.classList.remove('hidden');

    const cards = [];
    if (this._slotImage) {
      cards.push({
        src: this._slotImage,
        label: '当前选择',
        isDefault: true,
        data: null,
      });
    }
    candidates.forEach((img, i) => {
      cards.push({
        src: img.thumbnail_url || img.full_url,
        label: `候选 ${i + 1}`,
        isDefault: false,
        data: img,
      });
    });

    row.innerHTML = cards.map(c => `
      <div class="default-candidate-card ${c.isDefault ? 'selected' : ''}"
           data-json="${c.isDefault ? '' : this._escape(JSON.stringify(c.data || {}))}">
        <img src="${this._escape(c.src)}" alt="" loading="lazy"
             onerror="this.parentElement.style.opacity='0.5'">
        <div class="card-label">${c.label}</div>
      </div>
    `).join('');

    row.querySelectorAll('.default-candidate-card').forEach(card => {
      card.addEventListener('click', () => {
        try {
          const json = card.dataset.json;
          if (json) {
            const data = JSON.parse(json);
            if (this._onFetch) this._onFetch(data);
          }
        } catch { /* ignore */ }
      });
    });
  },

  _renderGrid(results) {
    const grid = this._container.querySelector('.candidate-grid');
    if (!grid) return;
    if (!results.length) {
      grid.innerHTML = `<div class="empty-state"><div class="empty-icon">&#128269;</div><p>没有找到相关图片</p></div>`;
      return;
    }
    grid.innerHTML = results.map(img => `
      <div class="candidate-card" data-id="${this._escape(img.id)}" data-json="${this._escape(JSON.stringify(img))}">
        <img src="${this._escape(img.thumbnail_url || img.full_url)}" alt="" loading="lazy"
             onerror="this.parentElement.style.opacity='0.5'">
        <div class="card-overlay">
          <span>${this._escape(img.author || '')}</span>
          <span class="source-badge">${img.source === 'pexels' ? 'P' : img.source === 'unsplash' ? 'U' : 'T'}</span>
        </div>
        ${img.source === 'tavily' ? '<div class="tavily-warn">&#9888; 版权未核实</div>' : ''}
      </div>
    `).join('');

    grid.querySelectorAll('.candidate-card').forEach(card => {
      card.addEventListener('click', () => {
        try {
          const data = JSON.parse(card.dataset.json);
          if (this._onFetch) this._onFetch(data);
        } catch { /* ignore */ }
      });
    });
  },

  _renderGridLoading() {
    const grid = this._container.querySelector('.candidate-grid');
    if (!grid) return;
    grid.innerHTML = `<div class="empty-state"><div class="empty-icon">&#8987;</div><p>搜索中...</p></div>`;
  },

  _renderPagination() {
    const el = this._container.querySelector('.pagination');
    if (!el) return;
    const totalPages = Math.max(1, Math.ceil(this._totalResults / this._perPage));
    el.innerHTML = `
      <button class="prev-btn" ${this._currentPage <= 1 ? 'disabled' : ''}>&#8592; 前一页</button>
      <span>第 ${this._currentPage} / ${totalPages} 页</span>
      <button class="next-btn" ${this._currentPage >= totalPages ? 'disabled' : ''}>下一页 &#8594;</button>
    `;
    el.querySelector('.prev-btn')?.addEventListener('click', () => {
      if (this._currentPage > 1) { this._currentPage--; this._doSearch(); }
    });
    el.querySelector('.next-btn')?.addEventListener('click', () => {
      const tp = Math.ceil(this._totalResults / this._perPage);
      if (this._currentPage < tp) { this._currentPage++; this._doSearch(); }
    });
  },

  _showEmpty(msg) {
    const grid = this._container.querySelector('.candidate-grid');
    if (!grid) return;
    grid.innerHTML = `<div class="empty-state"><div class="empty-icon">&#9888;</div><p>${this._escape(msg || '搜索失败')}</p></div>`;
  },

  _escape(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },
};
