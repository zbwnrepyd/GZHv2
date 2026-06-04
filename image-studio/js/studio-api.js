/* studio-api.js — 图片定稿台 API 封装 */
const StudioAPI = {
  async overview(company) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}`);
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async variants(company, assetKey) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/variants`);
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async rescoreVariants(company, assetKey) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/rescore`, {
      method: 'POST',
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async search(company, assetKey, { query, source, lang, page, perPage }) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, source, lang, page, per_page: perPage }),
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async fetch(company, assetKey, imageData) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/fetch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(imageData),
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async generateQueries(company, assetKey, cardMarkdown) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_markdown: cardMarkdown }),
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async importUrl(company, assetKey, url) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async importFile(company, assetKey, file) {
    const form = new FormData();
    form.append('file', file);
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/import`, {
      method: 'POST',
      body: form,
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async selectVariant(company, assetKey, variantId) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/select`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ variant_id: variantId }),
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async deleteVariant(company, assetKey, variantId) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/variants/${variantId}`, {
      method: 'DELETE',
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async chartData(company, assetKey) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/chart-data`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async previewChart(company, assetKey, params, data) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ params, data }),
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.text();
  },

  async renderChart(company, assetKey, templateId, params) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/render-svg`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id: templateId, params }),
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async renderChartHtml(company, assetKey, html, params) {
    const r = await fetch(`/api/image-studio/${encodeURIComponent(company)}/${assetKey}/render-html`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html, params }),
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },

  async generateImage(company, assetKey, prompt) {
    const r = await fetch('/api/generate-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        company_name: company,
        asset_key: assetKey,
      }),
    });
    if (!r.ok) throw new Error(await _err(r));
    return r.json();
  },
};

async function _err(r) {
  try {
    const d = await r.json();
    return d.error || r.statusText;
  } catch { return r.statusText; }
}
