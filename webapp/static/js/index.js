const CARD_COUNT = 8;
const SOURCE_LABELS = {
  tavily: 'Tavily 搜索',
  github: 'GitHub',
  youtube: 'YouTube',
  website: '官网抓取',
};
const SOURCE_ORDER = ['tavily', 'github', 'youtube', 'website'];

const ResearchDesk = {
  pollTimer: null,
  activeJobId: null,
  pollInFlight: false,
  companies: [],
  expandedCompany: '',
  detailsByCompany: {},

  init() {
    document.getElementById('btn-start-research').addEventListener('click', () => this.startResearch());
    document.getElementById('btn-refresh-companies').addEventListener('click', () => this.loadCompanies());
    document.getElementById('company-table-body').addEventListener('click', (event) => {
      const refillButton = event.target.closest('[data-refill-company]');
      if (refillButton) {
        this.refillResearch(refillButton.dataset.refillCompany, refillButton.dataset.refillUrl || '');
        return;
      }
      if (event.target.closest('a, button')) return;
      const row = event.target.closest('.company-row');
      if (!row) return;
      this.toggleCompanyDetails(decodeURIComponent(row.dataset.company));
    });
    this.loadCompanies();
  },

  async loadCompanies() {
    const body = document.getElementById('company-table-body');
    body.innerHTML = '<tr><td colspan="5">加载中...</td></tr>';
    try {
      const companies = await API.getCompanies();
      this.companies = companies;
      if (!companies.length) {
        body.innerHTML = '<tr><td colspan="5">暂无公司，先发起一次研究。</td></tr>';
        return;
      }
      this.renderCompanies();
    } catch (e) {
      body.innerHTML = `<tr><td colspan="5">公司库加载失败：${this.esc(e.message)}</td></tr>`;
    }
  },

  renderCompanies() {
    const body = document.getElementById('company-table-body');
    body.innerHTML = this.companies.map(company => {
      const rows = [this.renderCompanyRow(company)];
      if (company.company_name === this.expandedCompany) {
        rows.push(this.renderCompanyDetailRow(company.company_name));
      }
      return rows.join('');
    }).join('');
  },

  renderCompanyRow(company) {
    const completeness = Number(company.completeness || 0);
    const level = completeness >= 80 ? 'high' : completeness >= 60 ? 'mid' : 'low';
    const researchedAt = this.formatDate(company.researched_at || company.created_at);
    const name = this.esc(company.company_name);
    const encodedName = encodeURIComponent(company.company_name);
    const encodedUrl = encodeURIComponent(company.company_url || company.website_url || '');
    const confirmed = Number(company.confirmed || 0);
    const total = Number(company.total || CARD_COUNT);
    const expanded = company.company_name === this.expandedCompany;
    return `<tr class="company-row ${expanded ? 'is-expanded' : ''}" data-company="${encodedName}" title="点击展开研究信息">
      <td><span class="row-caret">${expanded ? '▾' : '▸'}</span>${name}</td>
      <td>${researchedAt}</td>
      <td><span class="completeness ${level}">${completeness}%</span></td>
      <td>${confirmed}/${total}</td>
      <td>
        <a class="btn btn-sm" href="/editor?company=${encodedName}">定稿</a>
        <button class="btn btn-sm" data-refill-company="${this.esc(encodedName)}" data-refill-url="${this.esc(encodedUrl)}">重研</button>
      </td>
    </tr>`;
  },

  async toggleCompanyDetails(companyName) {
    if (this.expandedCompany === companyName) {
      this.expandedCompany = '';
      this.renderCompanies();
      return;
    }

    this.expandedCompany = companyName;
    this.renderCompanies();

    if (this.detailsByCompany[companyName]) return;
    try {
      this.detailsByCompany[companyName] = await API.getAllVersions(companyName);
    } catch (e) {
      this.detailsByCompany[companyName] = { _error: e.message };
    }
    if (this.expandedCompany === companyName) this.renderCompanies();
  },

  renderCompanyDetailRow(companyName) {
    const details = this.detailsByCompany[companyName];
    const encodedName = encodeURIComponent(companyName);
    let content = '<div class="company-detail-loading">正在读取研究信息...</div>';
    if (details?._error) {
      content = `<div class="company-detail-error">研究信息加载失败：${this.esc(details._error)}</div>`;
    } else if (details) {
      content = this.renderCompanyDetails(details, encodedName);
    }
    return `<tr class="company-detail-row" data-company-detail="${encodedName}">
      <td colspan="5">${content}</td>
    </tr>`;
  },

  renderCompanyDetails(versions, encodedName) {
    const standard = versions.standard || versions.business || versions.spread || {};
    const facts = [
      ['类型', standard.company_type],
      ['地点', standard.location],
      ['创始人', standard.founder_name],
      ['学历背景', standard.founder_edu],
      ['工作背景', standard.founder_bg],
      ['过往成就', standard.founder_achievement],
      ['团队', standard.team_size],
      ['融资', standard.funding_info],
      ['主产品', standard.main_product_name],
      ['置信度', standard.data_confidence],
    ];
    return `<div class="company-detail-panel">
      <div class="company-detail-top">
        <div>
          <div class="company-detail-title">研究信息</div>
          <div class="company-detail-subtitle">点击其他公司会自动收起当前详情。</div>
        </div>
        <a class="btn btn-sm" href="/editor?company=${encodedName}">进入定稿</a>
      </div>
      <div class="detail-fact-grid">
        ${facts.map(([label, value]) => `<div class="detail-fact"><span>${this.esc(label)}</span><strong>${this.esc(this.compactValue(value))}</strong></div>`).join('')}
      </div>
    </div>`;
  },

  compactValue(value, maxLength = 80) {
    const text = this.stringifyValue(value).replace(/\s+/g, ' ').trim();
    if (!text) return '暂缺';
    return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
  },

  stringifyValue(value) {
    if (value === null || value === undefined || value === '') return '';
    if (Array.isArray(value)) {
      return value.map(item => this.stringifyValue(item)).filter(Boolean).join('；');
    }
    if (typeof value === 'object') {
      return Object.values(value).map(item => this.stringifyValue(item)).filter(Boolean).join(' / ');
    }
    return String(value);
  },

  refillResearch(encodedName, encodedUrl = '') {
    document.getElementById('research-company-name').value = decodeURIComponent(encodedName);
    const urlInput = document.getElementById('research-company-url');
    urlInput.value = decodeURIComponent(encodedUrl);
    urlInput.focus();
  },

  async startResearch() {
    const nameInput = document.getElementById('research-company-name');
    const urlInput = document.getElementById('research-company-url');
    const btn = document.getElementById('btn-start-research');
    const companyName = nameInput.value.trim();
    const companyUrl = urlInput.value.trim();
    if (!companyName || !companyUrl) {
      this.setProgress('failed', '研究失败', '请填写公司名和官网 URL');
      return;
    }
    if (btn.disabled || this.activeJobId) return;

    clearInterval(this.pollTimer);
    this.pollTimer = null;
    this.activeJobId = 'starting';
    this.pollInFlight = false;
    btn.disabled = true;
    document.getElementById('research-complete').classList.add('hidden');
    document.getElementById('research-complete').innerHTML = '';
    this.setProgress('running', '启动', '正在提交研究任务...', {});

    try {
      const job = await API.startResearch(companyName, companyUrl);
      this.activeJobId = job.job_id;
      this.pollJob(job.job_id, companyName, btn);
    } catch (e) {
      this.activeJobId = null;
      btn.disabled = false;
      this.setProgress('failed', '研究失败', e.message);
    }
  },

  pollJob(jobId, companyName, btn) {
    clearInterval(this.pollTimer);
    const poll = async () => {
      if (this.activeJobId !== jobId || this.pollInFlight) return;
      this.pollInFlight = true;
      try {
        const job = await API.getResearchStatus(jobId);
        if (job.status === 'done') {
          clearInterval(this.pollTimer);
          this.pollTimer = null;
          this.activeJobId = null;
          btn.disabled = false;
          this.setProgress('done', '研究完成', job.detail || '已写入数据库', job.sources || {});
          document.getElementById('research-complete').classList.remove('hidden');
          document.getElementById('research-complete').innerHTML =
            `<a class="btn btn-primary" href="/editor?company=${encodeURIComponent(companyName)}">研究完成 · 进入定稿 →</a>`;
          await this.loadCompanies();
        } else if (job.status === 'failed') {
          clearInterval(this.pollTimer);
          this.pollTimer = null;
          this.activeJobId = null;
          btn.disabled = false;
          this.setProgress('failed', '研究失败', job.error || job.detail || '未知错误', job.sources || {});
        } else {
          this.setProgress(job.status, job.stage || 'running', job.detail || '', job.sources || {});
        }
      } catch (e) {
        clearInterval(this.pollTimer);
        this.pollTimer = null;
        this.activeJobId = null;
        btn.disabled = false;
        this.setProgress('failed', '研究失败', e.message, {});
      } finally {
        this.pollInFlight = false;
      }
    };
    poll();
    this.pollTimer = setInterval(poll, 2000);
  },

  setProgress(status, stage, detail, sources) {
    const progress = document.getElementById('research-progress');
    progress.classList.remove('hidden');
    const percent = this.stagePercent(stage, status);
    document.getElementById('research-stage').textContent = stage;
    document.getElementById('research-percent').textContent = `${percent}%`;
    document.getElementById('research-progress-fill').style.width = `${percent}%`;
    document.getElementById('research-detail').textContent = this.detailText(detail);
    this.renderSourceStatus(sources || {});
    progress.dataset.status = status;
  },

  detailText(detail) {
    if (!detail) return '';
    if (typeof detail === 'object') return detail.message || '';
    return String(detail);
  },

  renderSourceStatus(sources) {
    const grid = document.getElementById('source-status-grid');
    grid.innerHTML = SOURCE_ORDER.map((key) => {
      const source = sources[key] || {};
      const status = source.status || 'pending';
      const label = source.label || SOURCE_LABELS[key] || key;
      const count = Number(source.count || 0);
      const unit = source.unit || '条';
      const detail = source.detail || '等待采集';
      return `<div class="source-card source-${status}">
        <div class="source-card-head">
          <span class="source-name">${this.esc(label)}</span>
          <span class="source-badge">${this.sourceStatusLabel(status)}</span>
        </div>
        <div class="source-metric">${count}<span>${this.esc(unit)}</span></div>
        <div class="source-detail">${this.esc(detail)}</div>
      </div>`;
    }).join('');
  },

  sourceStatusLabel(status) {
    return {
      ok: '有效',
      empty: '空',
      failed: '失败',
      skipped: '跳过',
      pending: '等待',
    }[status] || status;
  },

  stagePercent(stage, status) {
    if (status === 'done') return 100;
    if (status === 'failed') return 100;
    const normalized = String(stage || '').toLowerCase();
    if (normalized.includes('collect') || normalized.includes('采集')) return 20;
    if (normalized.includes('l0') || normalized.includes('layer0') || normalized.includes('清洗')) return 35;
    if (normalized.includes('l1') || normalized.includes('layer1')) return 50;
    if (normalized.includes('l2') || normalized.includes('layer2')) return 65;
    if (normalized.includes('l3') || normalized.includes('layer3')) return 80;
    if (normalized.includes('写入')) return 95;
    return 10;
  },

  formatDate(value) {
    if (!value) return '暂缺';
    const date = new Date(String(value).replace(' ', 'T'));
    if (Number.isNaN(date.getTime())) return value;
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    const hour = `${date.getHours()}`.padStart(2, '0');
    const minute = `${date.getMinutes()}`.padStart(2, '0');
    return `${month}月${day}日 ${hour}:${minute}`;
  },

  esc(value) {
    return String(value || '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;',
    }[ch]));
  },
};

document.addEventListener('DOMContentLoaded', () => ResearchDesk.init());
