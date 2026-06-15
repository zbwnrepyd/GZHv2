/* render-data-loader.js — GZHv2 渲染数据加载器
   从 /api/render-data/<company> 加载渲染数据，替代旧 API */
const RenderDataLoader = {
  _cache: {},

  async load(company) {
    if (this._cache[company]) return this._cache[company];

    const r = await fetch(`/api/render-data/${encodeURIComponent(company)}`);
    if (!r.ok) throw new Error(`render-data API ${r.status}`);
    const data = await r.json();
    this._cache[company] = data;
    return data;
  },

  async loadCard(company, cardId, setKey = '') {
    const effectiveSet = setKey || new URLSearchParams(window.location.search).get('set') || '';
    const setQuery = effectiveSet ? `?set=${encodeURIComponent(effectiveSet)}` : '';
    const r = await fetch(`/api/render-data/${encodeURIComponent(company)}/${encodeURIComponent(cardId)}${setQuery}`);
    if (!r.ok) throw new Error(`render-data single card API ${r.status}`);
    return await r.json();
  },

  clearCache(company) {
    delete this._cache[company];
  },

  /* 从 render-data 中提取卡片列表（enabled cards） */
  getEnabledCards(data) {
    return (data.cards || []).filter(c => c.enabled !== false);
  },

  /* 按 card_index 排序 */
  getSortedCards(data) {
    return this.getEnabledCards(data).sort((a, b) => (a.card_index || 0) - (b.card_index || 0));
  },
};
