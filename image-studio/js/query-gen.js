/* query-gen.js — 智能搜索词生成 + localStorage 缓存 */
const QueryGen = {
  CACHE_KEY: 'img_studio_queries',

  _cache: {},

  init() {
    try {
      const raw = localStorage.getItem(this.CACHE_KEY);
      if (raw) this._cache = JSON.parse(raw);
    } catch { this._cache = {}; }
  },

  _cacheKey(company, assetKey) {
    return `${company}::${assetKey}`;
  },

  get(company, assetKey) {
    const entry = this._cache[this._cacheKey(company, assetKey)];
    if (entry && entry.queries && entry.queries.length) return entry.queries;
    return null;
  },

  set(company, assetKey, queries) {
    this._cache[this._cacheKey(company, assetKey)] = {
      queries,
      ts: Date.now(),
    };
    try {
      localStorage.setItem(this.CACHE_KEY, JSON.stringify(this._cache));
    } catch { /* quota exceeded, ignore */ }
  },

  async fetch(company, assetKey, cardMarkdown) {
    try {
      const result = await StudioAPI.generateQueries(company, assetKey, cardMarkdown);
      if (result.queries && result.queries.length) {
        this.set(company, assetKey, result.queries);
        return result.queries;
      }
    } catch { /* fall through to fallback */ }
    return null;
  },

  /** 返回默认 fallback 查询词 */
  fallback(assetKey) {
    const map = {
      office: [
        { en: 'modern office workspace technology', zh: '科技公司 办公室 团队' },
        { en: 'startup office interior design', zh: '创业公司 办公环境' },
        { en: 'tech company headquarters building', zh: '科技 总部 大楼' },
      ],
      product_main: [
        { en: 'software application interface UI', zh: '软件 产品 界面 截图' },
        { en: 'technology product dashboard', zh: '科技 产品 仪表盘 手机' },
        { en: 'app screen design technology', zh: '应用 界面 科技 设计' },
      ],
      products_other: [
        { en: 'software product feature showcase', zh: '软件 功能 科技 工具' },
        { en: 'technology tool dashboard panel', zh: '科技 工具 仪表盘' },
        { en: 'digital product screen capture', zh: '数字 产品 界面 展示' },
      ],
      positioning_charts: [
        { en: 'competitive landscape matrix', zh: '竞争格局 矩阵 图' },
        { en: 'market positioning bubble chart', zh: '市场定位 气泡图' },
        { en: 'value chain ecosystem map', zh: '产业链 生态位 图' },
      ],
      competitors: [
        { en: 'technology startup landscape competition', zh: '科技 创业公司 行业 竞争' },
        { en: 'market analysis comparison chart', zh: '市场 格局 对比 分析' },
        { en: 'business competition strategy', zh: '商业 竞争 战略' },
      ],
    };
    return map[assetKey] || [{ en: `${assetKey} technology`, zh: `科技 产品` }];
  },
};
