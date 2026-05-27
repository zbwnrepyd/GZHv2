const CARD_COUNT = 8;

const ResearchDesk = {
  pollTimer: null,

  init() {
    document.getElementById('btn-start-research').addEventListener('click', () => this.startResearch());
    document.getElementById('btn-refresh-companies').addEventListener('click', () => this.loadCompanies());
    this.loadCompanies();
  },

  async loadCompanies() {
    const body = document.getElementById('company-table-body');
    body.innerHTML = '<tr><td colspan="5">加载中...</td></tr>';
    try {
      const companies = await API.getCompanies();
      if (!companies.length) {
        body.innerHTML = '<tr><td colspan="5">暂无公司，先发起一次研究。</td></tr>';
        return;
      }
      body.innerHTML = companies.map(company => this.renderCompanyRow(company)).join('');
    } catch (e) {
      body.innerHTML = `<tr><td colspan="5">公司库加载失败：${this.esc(e.message)}</td></tr>`;
    }
  },

  renderCompanyRow(company) {
    const completeness = Number(company.completeness || 0);
    const level = completeness >= 80 ? 'high' : completeness >= 60 ? 'mid' : 'low';
    const researchedAt = this.formatDate(company.researched_at || company.created_at);
    const name = this.esc(company.company_name);
    const confirmed = Number(company.confirmed || 0);
    const total = Number(company.total || CARD_COUNT);
    return `<tr>
      <td>${name}</td>
      <td>${researchedAt}</td>
      <td><span class="completeness ${level}">${completeness}%</span></td>
      <td>${confirmed}/${total}</td>
      <td>
        <a class="btn btn-sm" href="/editor?company=${encodeURIComponent(company.company_name)}">定稿</a>
        <button class="btn btn-sm" onclick="ResearchDesk.refillResearch('${encodeURIComponent(company.company_name)}')">重研</button>
      </td>
    </tr>`;
  },

  refillResearch(encodedName) {
    document.getElementById('research-company-name').value = decodeURIComponent(encodedName);
    document.getElementById('research-company-url').focus();
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

    clearInterval(this.pollTimer);
    btn.disabled = true;
    this.setProgress('running', '启动', '正在提交研究任务...');

    try {
      const job = await API.startResearch(companyName, companyUrl);
      this.pollJob(job.job_id, companyName, btn);
    } catch (e) {
      btn.disabled = false;
      this.setProgress('failed', '研究失败', e.message);
    }
  },

  pollJob(jobId, companyName, btn) {
    const poll = async () => {
      try {
        const job = await API.getResearchStatus(jobId);
        if (job.status === 'done') {
          clearInterval(this.pollTimer);
          btn.disabled = false;
          this.setProgress('done', '研究完成', job.detail || '已写入数据库');
          document.getElementById('research-complete').classList.remove('hidden');
          document.getElementById('research-complete').innerHTML =
            `<a class="btn btn-primary" href="/editor?company=${encodeURIComponent(companyName)}">研究完成 · 进入定稿 →</a>`;
          await this.loadCompanies();
        } else if (job.status === 'failed') {
          clearInterval(this.pollTimer);
          btn.disabled = false;
          this.setProgress('failed', '研究失败', job.error || job.detail || '未知错误');
        } else {
          this.setProgress(job.status, job.stage || 'running', job.detail || '');
        }
      } catch (e) {
        clearInterval(this.pollTimer);
        btn.disabled = false;
        this.setProgress('failed', '研究失败', e.message);
      }
    };
    poll();
    this.pollTimer = setInterval(poll, 2000);
  },

  setProgress(status, stage, detail) {
    const progress = document.getElementById('research-progress');
    progress.classList.remove('hidden');
    const percent = this.stagePercent(stage, status);
    document.getElementById('research-stage').textContent = stage;
    document.getElementById('research-percent').textContent = `${percent}%`;
    document.getElementById('research-progress-fill').style.width = `${percent}%`;
    document.getElementById('research-detail').textContent = detail || '';
    progress.dataset.status = status;
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
