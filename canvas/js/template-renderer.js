/* template-renderer.js — GZHv2 模板渲染引擎
   输入：render-data card + template JSON + layout overrides
   输出：HTML 字符串

   核心原则：模板 region 绑定 display_role，不绑定具体字段名。
*/

const TemplateRenderer = {
  /* 默认 fallback 模板（当 card 没有 template 时使用） */
  DEFAULT_TEMPLATE: {
    canvas: { width: 900, height: 1200 },
    background: { type: "color", value: "#FFFFFF" },
    regions: [
      { id: "title", type: "text", role: "title", x: 68, y: 80, w: 764, h: 90,
        style: { fontFamily: "Noto Sans SC", fontSize: 48, fontWeight: 700, color: "#111", textAlign: "left" } },
      { id: "body", type: "text", role: "body", x: 68, y: 200, w: 764, h: 920,
        style: { fontFamily: "Noto Sans SC", fontSize: 24, fontWeight: 400, color: "#333", lineHeight: 1.55 } },
    ],
    decorations: [],
  },

  /* ── 主渲染入口 ── */
  render(cardData) {
    const template = cardData.template || this.DEFAULT_TEMPLATE;
    const layout = cardData.layout || {};
    const items = cardData.items || [];

    // 1. 按 display_role 分组 items
    const roleMap = this._groupByRole(items);

    // 2. 合并 layout overrides 到 regions
    const regions = this._mergeOverrides(
      template.regions || [],
      layout.overrides || {},
    );

    // 3. 渲染每个 region
    const canvas = template.canvas || { width: 900, height: 1200 };
    const bg = this._renderBackground(template.background);

    const regionHTML = regions.map(region =>
      this._renderRegion(region, roleMap, canvas)
    ).join('\n');

    // 4. 装饰层
    const decoHTML = (template.decorations || []).map(d =>
      this._renderDecoration(d, canvas)
    ).join('\n');

    return this._wrapHTML(canvas, bg, regionHTML, decoHTML);
  },

  /* ── 按 role 分组 items ── */
  _groupByRole(items) {
    const map = {};
    for (const item of items) {
      const role = item.display_role || 'body';
      if (!map[role]) map[role] = [];
      map[role].push(item);
    }
    return map;
  },

  /* ── 合并 layout overrides ── */
  _mergeOverrides(regions, overrides) {
    return regions.map(region => {
      const override = overrides[region.id];
      if (!override) return region;
      return this._deepMerge(region, override);
    });
  },

  _deepMerge(base, override) {
    const result = { ...base };
    for (const [k, v] of Object.entries(override)) {
      if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
        result[k] = this._deepMerge(result[k] || {}, v);
      } else {
        result[k] = v;
      }
    }
    return result;
  },

  /* ── 背景 ── */
  _renderBackground(bg) {
    if (!bg) return 'background: #FFFFFF;';
    if (bg.type === 'gradient') return `background: ${bg.value};`;
    if (bg.type === 'image') return `background: url(${bg.value}) center/cover;`;
    return `background: ${bg.value || '#FFFFFF'};`;
  },

  /* ── 渲染单个 region ── */
  _renderRegion(region, roleMap, canvas) {
    const role = region.role || 'body';
    const style = this._buildStyle(region);
    const type = region.type || 'text';

    if (type === 'image' || type === 'chart' || type === 'logo') {
      const mediaItems = (roleMap[role] || roleMap['hero_image'] || roleMap['chart'] || []);
      // 优先按 bind 精确匹配 item_key，再按 role fallback；避免多图同 role 时重复取第一张
      const bindKey = region.bind;
      const media = bindKey
        ? (mediaItems.find(m => m.item_key === bindKey) || mediaItems[0])
        : mediaItems[0];
      const url = media?.url || media?.local_path || '';
      if (!url) {
        // placeholder
        return `<div data-od-id="${this._escAttr(region.id || role)}" style="${style}display:flex;align-items:center;justify-content:center;color:rgba(0,0,0,0.15);font-size:14px">[${role}]</div>`;
      }
      const fit = (region.style || {}).objectFit || 'contain';
      return `<img data-od-id="${this._escAttr(region.id || role)}" src="${this._escAttr(url)}" style="${style}object-fit:${fit};display:block" alt="">`;
    }

    if (type === 'shape') {
      // 纯装饰形状
      return `<div data-od-id="${this._escAttr(region.id || role)}" style="${style}"></div>`;
    }

    // text region — 按 markdown 规则渲染
    const fieldItems = roleMap[role] || roleMap['body'] || [];
    const texts = fieldItems.map(item => item.value || '').filter(Boolean);

    if (!texts.length) return '';

    const combined = texts.join('\n\n');
    const textAlign = (region.style || {}).textAlign || 'left';
    const lineHeight = (region.style || {}).lineHeight || 1.55;
    const mdHTML = this._markdownToHTML(combined);

    return `<div data-od-id="${this._escAttr(region.id || role)}" style="${style}text-align:${textAlign};line-height:${lineHeight}">${mdHTML}</div>`;
  },

  /* ── 构建 CSS 样式字符串 ── */
  _buildStyle(region) {
    const s = region.style || {};
    const css = [
      `position:absolute`,
      `left:${region.x || 0}px`,
      `top:${region.y || 0}px`,
      `width:${region.w || 100}px`,
      `height:${region.h || 100}px`,
    ];
    if (s.fontFamily) css.push(`font-family:'${s.fontFamily}', 'Noto Sans SC', sans-serif`);
    if (s.fontSize) css.push(`font-size:${s.fontSize}px`);
    if (s.fontWeight) css.push(`font-weight:${s.fontWeight}`);
    if (s.color) css.push(`color:${s.color}`);
    if (s.letterSpacing) css.push(`letter-spacing:${s.letterSpacing}`);
    if (s.opacity !== undefined) css.push(`opacity:${s.opacity}`);
    if (s.borderRadius) css.push(`border-radius:${s.borderRadius}px`);
    if (s.borderWidth && s.borderColor) css.push(`border:${s.borderWidth}px solid ${s.borderColor}`);
    if (s.shadow) css.push(`box-shadow:${s.shadow}`);
    if (s.backgroundColor) css.push(`background:${s.backgroundColor}`);
    css.push('overflow:hidden');
    return css.join(';') + ';';
  },

  _renderDecoration(deco, canvas) {
    if (deco.type === 'noise') {
      return `<div data-od-id="${this._escAttr(deco.id || 'decoration')}" style="position:absolute;inset:0;opacity:${deco.opacity||0.05};pointer-events:none;z-index:1;
        background-image:url('data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22200%22><filter id=%22n%22><feTurbulence type=%22fractalNoise%22 baseFrequency=%220.7%22/></filter><rect width=%22200%22 height=%22200%22 filter=%22url(%23n)%22 opacity=%220.5%22/></svg>');background-size:200px"></div>`;
    }
    return '';
  },

  /* ── 包裹为可嵌入片段：iframe srcdoc 和单卡页都能直接消费 ── */
  _wrapHTML(canvas, bgStyle, regionHTML, decoHTML) {
    return `<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@500;700&family=Noto+Sans+SC:wght@400;700;900&display=swap');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    width: ${canvas.width}px;
    height: ${canvas.height}px;
    overflow: hidden;
    position: relative;
    ${bgStyle}
  }
  .knowledge-card {
    position: relative;
    width: ${canvas.width}px;
    height: ${canvas.height}px;
    overflow: hidden;
  }
</style>
<article class="knowledge-card" data-od-id="card-root">
  ${decoHTML}
  ${regionHTML}
</article>`;
  },

  /* ── Markdown → HTML（标题 #/##/###、列表 -/*、加粗、斜体、段落）── */
  _markdownToHTML(md) {
    let html = this._esc(md);

    // 代码块（```...``` 或 ~~~...~~~）
    html = html.replace(/(```|~~~)([\s\S]*?)\1/g, (_, __, code) => {
      return `<pre><code>${this._esc(code.trim())}</code></pre>`;
    });

    // 行内代码 `...`
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // 粗斜体 ***...***
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    // 粗体 **...**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // 斜体 *...*（不匹配 **）
    html = html.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '<em>$1</em>');

    // 按双换行拆分为块
    const blocks = html.split(/\n\n+/);
    const processed = blocks.map(block => {
      const lines = block.split('\n');
      const result = [];

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) { result.push('<br>'); continue; }

        // 标题 # ## ###
        const hMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
        if (hMatch) {
          const level = hMatch[1].length;
          const text = hMatch[2];
          result.push(`<h${level}>${text}</h${level}>`);
          continue;
        }

        // 无序列表 - 或 *
        const ulMatch = trimmed.match(/^[-*]\s+(.+)$/);
        if (ulMatch) {
          result.push(`<li>${ulMatch[1]}</li>`);
          continue;
        }

        // 有序列表 1. 2. 等
        const olMatch = trimmed.match(/^\d+\.\s+(.+)$/);
        if (olMatch) {
          result.push(`<li>${olMatch[1]}</li>`);
          continue;
        }

        // 水平线 --- 或 ***
        if (/^[-*_]{3,}$/.test(trimmed)) {
          result.push('<hr>');
          continue;
        }

        // 引用 >
        if (trimmed.startsWith('> ')) {
          result.push(`<blockquote>${trimmed.substring(2)}</blockquote>`);
          continue;
        }

        // 普通段落
        result.push(`<p>${trimmed}</p>`);
      }

      // 连续 li 包裹 ul
      let grouped = [];
      for (let i = 0; i < result.length; i++) {
        if (result[i].startsWith('<li>')) {
          const liGroup = [];
          while (i < result.length && result[i].startsWith('<li>')) {
            liGroup.push(result[i]);
            i++;
          }
          i--;
          grouped.push(`<ul>${liGroup.join('')}</ul>`);
        } else {
          grouped.push(result[i]);
        }
      }
      return grouped.join('\n');
    });

    return processed.join('\n');
  },

  /* ── 工具 ── */
  _esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); },
  _escAttr(s) { return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;'); },
};

/* 导出全局 */
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { TemplateRenderer };
}
