// 卡片确认流程

const ConfirmManager = {
  _confirmed: new Set(),
  _company: null,

  _storageKey() {
    return `confirmed_${this._company}`;
  },

  init(company) {
    this._company = company;
    this._confirmed = new Set();

    // 先从 localStorage 恢复
    try {
      const raw = localStorage.getItem(this._storageKey());
      if (raw) {
        JSON.parse(raw).forEach(c => this._confirmed.add(c));
        this._updateAccordions();
      }
    } catch {}

    // 再从服务端同步（服务端数据优先）
    API.checkStatus(company).then(data => {
      if (data.confirmed_cards) {
        this._confirmed = new Set(data.confirmed_cards);
        this._persist();
        this._updateAccordions();
      }
    }).catch(() => {});
  },

  _persist() {
    try {
      localStorage.setItem(this._storageKey(), JSON.stringify([...this._confirmed]));
    } catch {}
  },

  isConfirmed(cardIndex) {
    return this._confirmed.has(cardIndex);
  },

  confirm(cardIndex) {
    this._confirmed.add(cardIndex);
    this._persist();
    this._updateAccordions();
  },

  _updateAccordions() {
    document.querySelectorAll('.accordion-card').forEach(details => {
      const ci = parseInt(details.dataset.card);
      const summary = details.querySelector('summary');
      if (!summary) return;
      const title = CARD_TITLES[ci] || `卡片${ci}`;
      if (this._confirmed.has(ci)) {
        summary.innerHTML = `卡片${ci}：${title} <span class="accordion-confirmed">已确认</span>`;
      } else {
        summary.textContent = `卡片${ci}：${title}`;
      }
    });
  },

  getNextUnconfirmed(currentIndex) {
    for (let i = currentIndex + 1; i <= 7; i++) {
      if (!this._confirmed.has(i)) return i;
    }
    return null;
  },

  allConfirmed() {
    for (let i = 1; i <= 7; i++) {
      if (!this._confirmed.has(i)) return false;
    }
    return true;
  },

  // 获取当前卡片对应的 final_db 字段
  getCardFields(cardIndex, fieldValues) {
    const fieldDefs = CARD_FIELD_MAP[cardIndex] || [];
    const result = {};
    for (const def of fieldDefs) {
      result[def.key] = fieldValues[def.key] || '';
    }
    return result;
  }
};
