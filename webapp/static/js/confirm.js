// 卡片确认流程

const ConfirmManager = {
  _confirmed: new Set(),

  init(company) {
    this._confirmed = new Set();
    // 从服务器加载已确认的卡片
    API.checkStatus(company).then(data => {
      if (data.confirmed_cards) {
        data.confirmed_cards.forEach(c => this._confirmed.add(c));
      }
      this._updateTabs();
    }).catch(() => {});
  },

  isConfirmed(cardIndex) {
    return this._confirmed.has(cardIndex);
  },

  confirm(cardIndex) {
    this._confirmed.add(cardIndex);
    this._updateTabs();
  },

  _updateTabs() {
    document.querySelectorAll('.card-tab').forEach(tab => {
      const ci = parseInt(tab.dataset.card);
      if (this._confirmed.has(ci)) {
        tab.classList.add('confirmed');
      } else {
        tab.classList.remove('confirmed');
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
