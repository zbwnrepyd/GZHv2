const ConfirmManager = {
  confirmed: new Set(),

  _totalCards() {
    return (window.EditorApp ? EditorApp.currentSetKey : 'v1') === 'v2' ? 7 : 8;
  },

  setConfirmed(cards) {
    this.confirmed = new Set((cards || []).map(Number));
    this.updateButtons();
  },

  confirm(cardIndex) {
    this.confirmed.add(Number(cardIndex));
    this.updateButtons();
  },

  isConfirmed(cardIndex) {
    return this.confirmed.has(Number(cardIndex));
  },

  allConfirmed() {
    const total = this._totalCards();
    for (let i = 1; i <= total; i++) {
      if (!this.confirmed.has(i)) return false;
    }
    return true;
  },

  updateButtons() {
    document.querySelectorAll('.editor-card-btn').forEach((button) => {
      const cardIndex = Number(button.dataset.card);
      const baseLabel = button.dataset.label || button.textContent.replace(/\s*✓$/, '');
      button.dataset.label = baseLabel;
      button.classList.toggle('confirmed', this.confirmed.has(cardIndex));
      button.textContent = this.confirmed.has(cardIndex) ? `${baseLabel} ✓` : baseLabel;
    });
  },
};
