const DbFieldsPanel = {
  _loaded: false,
  _popup: null,

  async init(companyName) {
    if (this._loaded) return;
    this._loaded = true;
    await this.load(companyName);
  },

  async load(companyName) {
    const tbody = document.querySelector('#db-fields-table tbody');
    const countEl = document.getElementById('db-fields-count');
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="padding:20px;text-align:center;color:var(--text-subtle);">加载中...</td></tr>';

    try {
      const resp = await fetch(`/api/company/${encodeURIComponent(companyName)}/all-fields`);
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();

      const rc = data.research_counts || {};
      if (countEl) countEl.textContent = `共 ${data.total} 字段 (S:${rc.standard||0} / B:${rc.business||0} / SP:${rc.spread||0} / 定稿:${data.final_count||0})`;

      if (!data.fields.length) {
        if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="padding:20px;text-align:center;color:var(--text-subtle);">暂无数据</td></tr>';
        return;
      }

      if (tbody) {
        tbody.innerHTML = data.fields.map(f => {
          const fv = f.final_value;
          const fvDisplay = fv === null ? '<span class="cell-empty">—</span>' : (fv === '' ? '<span class="cell-empty">(已清空)</span>' : this._esc(fv));
          const statusBadge = f.final_status === 'confirmed' ? '✅' : (f.final_status === 'draft' ? '📝' : '');
          return `<tr>
            <td title="${this._esc(f.field_key)}">${this._esc(f.field_key)}</td>
            <td>${this._esc(f.field_label || '')}</td>
            <td class="col-ver" data-full="${this._esc(f.value_standard||'')}">${this._esc(f.value_standard||'')}</td>
            <td class="col-ver" data-full="${this._esc(f.value_business||'')}">${this._esc(f.value_business||'')}</td>
            <td class="col-ver" data-full="${this._esc(f.value_spread||'')}">${this._esc(f.value_spread||'')}</td>
            <td>${fvDisplay}</td>
            <td>${statusBadge} ${this._esc(f.final_status || '')}</td>
          </tr>`;
        }).join('');

        // click-to-expand on version cells
        tbody.addEventListener('click', (e) => {
          const cell = e.target.closest('.col-ver');
          if (!cell) { this._closePopup(); return; }
          const text = cell.dataset.full || '';
          if (!text) { this._closePopup(); return; }
          this._showPopup(cell, text);
        });
      }
    } catch (e) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="padding:20px;text-align:center;color:#EF4444;">加载失败: ${this._esc(e.message)}</td></tr>`;
    }
  },

  _showPopup(anchor, text) {
    this._closePopup();
    const popup = document.createElement('div');
    popup.className = 'db-cell-popup';
    popup.textContent = text;
    document.body.appendChild(popup);

    // position near the anchor cell
    const rect = anchor.getBoundingClientRect();
    const popupW = Math.min(520, window.innerWidth - 32);
    let left = rect.left;
    if (left + popupW > window.innerWidth - 8) left = window.innerWidth - popupW - 8;
    if (left < 8) left = 8;

    popup.style.left = left + 'px';
    popup.style.top = (rect.bottom + 4) + 'px';
    popup.style.maxWidth = popupW + 'px';
    popup.style.display = 'block';

    this._popup = popup;

    // close on outside click
    const onOutside = (ev) => {
      if (!popup.contains(ev.target) && ev.target !== anchor) {
        this._closePopup();
        document.removeEventListener('click', onOutside);
        document.removeEventListener('keydown', onEsc);
      }
    };
    const onEsc = (ev) => {
      if (ev.key === 'Escape') {
        this._closePopup();
        document.removeEventListener('click', onOutside);
        document.removeEventListener('keydown', onEsc);
      }
    };
    setTimeout(() => {
      document.addEventListener('click', onOutside);
      document.addEventListener('keydown', onEsc);
    }, 0);
  },

  _closePopup() {
    if (this._popup) {
      this._popup.remove();
      this._popup = null;
    }
  },

  _esc(s) {
    return String(s || '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;',
    }[ch]));
  },
};
