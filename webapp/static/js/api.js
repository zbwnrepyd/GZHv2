// API 调用封装
const API = {
  async getCompanies() {
    const res = await fetch('/api/companies');
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getAllVersions(company) {
    const res = await fetch(`/api/research/${encodeURIComponent(company)}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getResearch(company, version) {
    const res = await fetch(`/api/research/${encodeURIComponent(company)}/${version}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async startResearch(companyName, companyUrl) {
    const res = await fetch('/api/research/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_name: companyName,
        company_url: companyUrl
      })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getResearchStatus(jobId) {
    const res = await fetch(`/api/research/status/${encodeURIComponent(jobId)}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async saveFinal(companyName, cardIndex, fields, imgPaths) {
    const res = await fetch('/api/final/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_name: companyName,
        card_index: cardIndex,
        fields: fields,
        img_paths: imgPaths || {}
      })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async exportCompany(company) {
    const res = await fetch(`/api/final/export/${encodeURIComponent(company)}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async checkStatus(company) {
    const res = await fetch(`/api/check/${encodeURIComponent(company)}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async generateImage(companyName, fieldName, prompt) {
    const res = await fetch('/api/generate-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_name: companyName,
        field_name: fieldName,
        prompt: prompt
      })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async splitText(text, segmentCount) {
    const res = await fetch('/api/split-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text, segment_count: segmentCount })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
};
