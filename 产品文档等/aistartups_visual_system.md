# aistartups.cn 卡片视觉技术方案
## 字体 · 点缀图形 · 插图 · 完整实施指南

> 版权已由用户自行授权处理，本文档聚焦技术选型与实施路径。

---

## 一、设计语言定义

### 1.1 概念方向

**"深海控制台"** — 把 AI 初创公司的信息密度和技术感，用终端/仪表盘的视觉语言表达。不是科技蓝的廉价感，而是像 Bloomberg Terminal 遇上 Monocle 杂志：克制、信息密、有一种冷静的权威感。

三个核心记忆点：
1. **∞ 符号** 贯穿全套，取代闪电——无限/永续，比闪电更有品牌语义
2. **青色细线** 作为全局标记系统，像仪表盘上的活跃指示灯
3. **字体的中西双轨**：英文极度几何，中文极度黑体，形成张力

---

## 二、字体方案

### 2.1 选型逻辑

一套卡片需要 4 个字重层级：
- **Display**（大标题、公司名）：要有强烈性格，不能 generic
- **UI**（导航、字段标签）：精确、等宽感
- **Body**（正文、字段值）：可读性优先，有轻微技术感
- **中文**（全部中文内容）：与英文等重，不能像系统字体

### 2.2 最终选型

#### 英文字体组合

| 层级 | 字体 | 字重 | 用途 |
|------|------|------|------|
| Display | **Bebas Neue** | Regular（唯一） | page1 公司名、page8 大标题 |
| Display Alt | **DM Serif Display** | Regular / Italic | 章节标题斜体点缀 |
| UI / Label | **IBM Plex Mono** | 500 / 700 | 字段标签、页码、导航、数据 |
| Body | **Instrument Sans** | 400 / 600 | 正文内容、字段值 |

**理由：**
- Bebas Neue：全大写几何无衬线，极度视觉冲击，公司名用它会被记住
- IBM Plex Mono：等宽字体用在 label 上，天然带有"终端/仪表盘"感，且是 IBM 开源字体，极少见于内容卡片
- Instrument Sans：Google 2023 年推出，比 Inter 更有曲线性格，不 generic
- DM Serif Display：偶尔出现的斜体衬线，制造视觉节奏的"意外"

#### 中文字体选型

| 层级 | 字体 | 备注 |
|------|------|------|
| 标题中文 | **思源黑体 Heavy（Source Han Sans CN 900）** | Adobe + Google 联合出品，开源，字重极重 |
| 正文中文 | **思源黑体 Regular（Source Han Sans CN 400）** | 同族，统一感强 |
| 数字/英文混排 | 用英文字体覆盖，CSS `unicode-range` 拆分 | 避免中文字体渲染英文数字 |

**为什么选思源黑体而不是其他：**
- 字重覆盖完整（100–900），一套字体解决所有中文层级
- 与 IBM Plex Mono 的几何感配合好，同属"精密工程"气质
- 开源免费，自托管无版权问题

#### Web 字体加载方案

```css
/* Google Fonts 加载（网络可用时） */
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Serif+Display:ital@0;1&family=IBM+Plex+Mono:wght@500;700&family=Instrument+Sans:wght@400;600&family=Noto+Sans+SC:wght@400;700;900&display=swap');

/* 自托管方案（Puppeteer 截图必用，避免网络依赖） */
/* 字体文件放到 /opt/ai/fonts/ */
@font-face {
  font-family: 'Bebas Neue';
  src: url('/fonts/BebasNeue-Regular.woff2') format('woff2');
  font-weight: 400;
  font-display: block; /* 截图场景用 block，防止 FOUT */
}
@font-face {
  font-family: 'IBM Plex Mono';
  src: url('/fonts/IBMPlexMono-Medium.woff2') format('woff2'),
       url('/fonts/IBMPlexMono-Bold.woff2') format('woff2');
  font-display: block;
}
@font-face {
  font-family: 'Source Han Sans CN';
  src: url('/fonts/SourceHanSansCN-Regular.woff2') format('woff2');
  font-weight: 400;
  font-display: block;
}
@font-face {
  font-family: 'Source Han Sans CN';
  src: url('/fonts/SourceHanSansCN-Heavy.woff2') format('woff2');
  font-weight: 900;
  font-display: block;
}

/* CSS 变量绑定 */
:root {
  --font-display:  'Bebas Neue', 'Source Han Sans CN', sans-serif;
  --font-serif:    'DM Serif Display', serif;
  --font-mono:     'IBM Plex Mono', monospace;
  --font-body:     'Instrument Sans', 'Source Han Sans CN', sans-serif;
  --font-zh:       'Source Han Sans CN', sans-serif;
}
```

#### Puppeteer 字体预加载（关键）

```js
// screenshot.js 中加入
await page.evaluateHandle('document.fonts.ready');
// 等价于等待所有 @font-face 加载完成，避免截图时字体降级
```

#### 字体文件下载地址

| 字体 | 许可 | 下载地址 |
|------|------|---------|
| Bebas Neue | OFL | fonts.google.com/specimen/Bebas+Neue |
| DM Serif Display | OFL | fonts.google.com/specimen/DM+Serif+Display |
| IBM Plex Mono | OFL | github.com/IBM/plex |
| Instrument Sans | OFL | fonts.google.com/specimen/Instrument+Sans |
| Source Han Sans CN | OFL | github.com/adobe-fonts/source-han-sans |

全部 OFL（SIL Open Font License），商业使用免费，无需归因。

---

## 三、点缀图形系统

### 3.1 设计原则

点缀不是装饰，是**信息密度的视觉呼吸**。分为三类：

| 类型 | 位置 | 作用 |
|------|------|------|
| 结构线 | 卡片边缘、字段分隔 | 制造"仪表盘面板"感 |
| 符号标记 | 数据前、列表项、强调处 | 替代传统 bullet，统一视觉语言 |
| 背景层 | 卡片底层，低不透明度 | 制造深度，区分每张卡片的"温度" |

### 3.2 SVG 点缀组件库（直接用于 CSS/HTML）

#### 组件1：∞ 水印背景（每张卡片通用）

```css
.card::before {
  content: '∞';
  font-family: var(--font-display);
  font-size: 720px;
  font-weight: 400;
  color: rgba(255,255,255, 0.025);
  position: absolute;
  right: -60px;
  bottom: -80px;
  line-height: 1;
  pointer-events: none;
  z-index: 0;
  letter-spacing: -0.08em;
  user-select: none;
}
```

#### 组件2：青色 accent bar（字段标签前）

```css
.accent-bar {
  width: 36px;
  height: 2px;
  background: #29B8D4;
  margin-bottom: 6px;
  /* 可变体：渐变消隐 */
}
.accent-bar.fade {
  background: linear-gradient(90deg, #29B8D4 0%, transparent 100%);
  width: 80px;
}
```

#### 组件3：网格点阵背景（page1 专属）

```css
.grid-bg {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle, rgba(41,184,212,0.15) 1px, transparent 1px);
  background-size: 32px 32px;
  opacity: 0.4;
  pointer-events: none;
  /* 从右上角向左下角消隐 */
  mask-image: linear-gradient(135deg, rgba(0,0,0,0.8) 0%, transparent 60%);
  -webkit-mask-image: linear-gradient(135deg, rgba(0,0,0,0.8) 0%, transparent 60%);
}
```

#### 组件4：扫描线纹理（内页卡片，制造终端感）

```css
.scanlines {
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 3px,
    rgba(0,0,0,0.03) 3px,
    rgba(0,0,0,0.03) 4px
  );
  pointer-events: none;
  z-index: 1;
}
```

#### 组件5：青色辉光球（glow blob，每张位置不同）

```css
.glow-blob {
  position: absolute;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgba(41,184,212,0.12) 0%,
    rgba(41,184,212,0.04) 40%,
    transparent 70%
  );
  pointer-events: none;
  z-index: 0;
  filter: blur(1px);
}
/* 每张卡片设置不同位置和尺寸，制造差异 */
.card-p1 .glow-blob { width: 600px; height: 600px; top: -200px; left: -100px; }
.card-p2 .glow-blob { width: 500px; height: 500px; top: -150px; right: -150px; }
/* ... 依此类推 */
```

#### 组件6：SVG 线框装饰（page4 产品卡专属）

```html
<!-- 右上角小型 SVG 装饰，模拟 UI 线框 -->
<svg class="ui-deco" viewBox="0 0 120 80" fill="none" xmlns="http://www.w3.org/2000/svg"
     style="position:absolute; top:60px; right:72px; width:120px; opacity:0.15;">
  <rect x="0.5" y="0.5" width="119" height="79" stroke="#29B8D4"/>
  <line x1="0" y1="20" x2="120" y2="20" stroke="#29B8D4" stroke-width="0.5"/>
  <rect x="8" y="28" width="60" height="6" rx="2" fill="#29B8D4" opacity="0.4"/>
  <rect x="8" y="40" width="40" height="4" rx="2" fill="#29B8D4" opacity="0.2"/>
  <rect x="8" y="50" width="50" height="4" rx="2" fill="#29B8D4" opacity="0.2"/>
  <circle cx="100" cy="56" r="12" stroke="#29B8D4" stroke-width="0.5"/>
</svg>
```

#### 组件7：数据标签徽章（竞品数据等）

```css
.data-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid rgba(41,184,212,0.3);
  border-radius: 4px;
  background: rgba(41,184,212,0.06);
  font-family: var(--font-mono);
  font-size: 14px;
  color: #29B8D4;
  letter-spacing: 0.06em;
}
.data-badge::before {
  content: '◆';
  font-size: 8px;
}
```

#### 组件8：timeline 节点系统

```html
<!-- 时间线竖线用 CSS border 实现，不依赖图片 -->
<style>
.tl-track {
  position: relative;
  padding-left: 28px;
}
.tl-track::before {
  content: '';
  position: absolute;
  left: 4px; top: 8px; bottom: 0;
  width: 1px;
  background: linear-gradient(
    to bottom,
    #29B8D4 0%,
    rgba(41,184,212,0.3) 60%,
    transparent 100%
  );
}
.tl-node {
  position: absolute;
  left: 0;
  width: 9px; height: 9px;
  border-radius: 50%;
  background: #29B8D4;
  box-shadow: 0 0 0 3px rgba(41,184,212,0.15);
  top: 6px;
}
</style>
```

### 3.3 各页点缀配置表

| 页 | 背景层 | 结构点缀 | 符号标记 |
|---|---|---|---|
| page1 封面 | 网格点阵 + 大∞水印 | 左侧竖线装饰 + 顶部∞徽章 | 类型 pill badge |
| page2 公司介绍 | 右上 glow blob | accent bar + 字段分隔线 | 列表项 `—` |
| page3 发展沿袭 | 左上 glow blob | timeline 轨道线 | 时间节点 ● |
| page4 主产品 | 右下 glow blob + UI 线框 SVG | highlight badge | 成就 `◆` 标签 |
| page5 其他产品 | 右上小 glow | 产品图占位框（1px 描边） | 产品列表 `—` |
| page6 商业模式 | 左下 glow blob | 2列网格线 | 飞轮项 `→` |
| page7 竞争格局 | 无 glow（最暗） | 竞品表格线 + 左侧壁垒框 | 排名 `TOP N` |
| page8 总结 | 中心大 glow + 巨∞装饰 | 底部品牌区横线 | CTA 箭头 `→` |

---

## 四、插图方案

### 4.1 插图策略

参考图（体系B）用 3D 渲染插图，体系A用信息流。对应到你的 8 张卡片：

- **page1 封面**：主视觉插图（公司 logo 3D 版 或 产品截图渲染）
- **page4/5 产品页**：产品 UI 截图 + 浅色卡片包装
- **page7 竞争格局**：无插图，纯数据
- 其余页：无大插图，依赖点缀图形撑场

### 4.2 三种插图生产路径

---

#### 路径A：AI 生成 3D 渲染图（参考图体系B的路线）

**工具：** Midjourney v6 / DALL-E 3 / Ideogram 2.0

**Prompt 模板（可批量化）：**

```
3D icon render of [公司名/产品名] logo concept,
clay material, smooth matte surface,
deep navy blue and cyan color palette (#1B2A4A, #29B8D4),
soft studio lighting with subtle rim light,
floating on pure white background,
isometric angle, 45 degree view,
Blender 3D style, high detail,
product visualization quality
--ar 1:1 --style raw --v 6
```

**变体（不同公司类型）：**
```
# SaaS 工具类
...a glowing terminal window with cyan code text...

# AI 模型类
...abstract neural network sphere, deep blue with cyan nodes...

# 硬件/机器人类
...miniature robot figure, matte clay finish...
```

**批量生产流程：**
1. 准备 20 个公司名
2. 套用 Prompt 模板批量提交（Midjourney 支持 `--repeat 4`）
3. 下载后用 remove.bg 或 Photoshop 去白底
4. 保存为 PNG with transparency，放到 `/opt/ai/assets/logos/<company>/3d.png`

**成本估算：** $0.02–0.05/张（Midjourney Basic 计划）

---

#### 路径B：CSS/SVG 生成式插图（无成本，可批量）

不用外部图片，直接在 HTML 模板里用 CSS + SVG 生成图形。适合技术类公司（Coding、API、CLI 工具）。

**模板1：终端窗口（适合 Coding Agent 类公司）**

```html
<div class="terminal-card">
  <div class="terminal-header">
    <div class="dot red"></div>
    <div class="dot yellow"></div>
    <div class="dot green"></div>
    <span class="terminal-title">claude --code</span>
  </div>
  <div class="terminal-body">
    <div class="line"><span class="prompt">$</span> claude "fix the auth bug in user.ts"</div>
    <div class="line muted">Reading codebase... <span class="cyan">1,247 files</span></div>
    <div class="line muted">Analyzing auth flow...</div>
    <div class="line"><span class="cyan">✓</span> Found issue in line 42</div>
    <div class="line"><span class="cyan">✓</span> Patch applied, tests passing</div>
    <div class="line blink">█</div>
  </div>
</div>

<style>
.terminal-card {
  background: #0A0F1A;
  border: 1px solid #1E3A5F;
  border-radius: 8px;
  overflow: hidden;
  font-family: var(--font-mono);
}
.terminal-header {
  background: #111827;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #1E3A5F;
}
.dot { width: 10px; height: 10px; border-radius: 50%; }
.dot.red    { background: #FF5F56; }
.dot.yellow { background: #FFBD2E; }
.dot.green  { background: #27C93F; }
.terminal-title { color: #4A6080; font-size: 13px; margin-left: 8px; }
.terminal-body { padding: 16px; display: flex; flex-direction: column; gap: 8px; }
.line { font-size: 18px; color: rgba(255,255,255,0.7); line-height: 1.4; }
.line.muted { color: #4A6080; }
.prompt { color: #29B8D4; margin-right: 8px; }
.cyan { color: #29B8D4; }
.blink { animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }
</style>
```

**模板2：API 请求可视化（适合 API/Platform 类）**

```html
<div class="api-visual">
  <div class="api-endpoint">
    <span class="method">POST</span>
    <span class="path">/v1/messages</span>
  </div>
  <div class="api-flow">
    <div class="api-node client">Client</div>
    <div class="api-arrow">
      <div class="arrow-line"></div>
      <span class="arrow-label">request</span>
    </div>
    <div class="api-node api">API</div>
    <div class="api-arrow">
      <div class="arrow-line"></div>
      <span class="arrow-label">stream</span>
    </div>
    <div class="api-node response">Response</div>
  </div>
  <div class="api-metric">
    <span class="metric-val">200K</span>
    <span class="metric-label">context window</span>
  </div>
</div>
```

**模板3：数据飞轮图（适合商业模式页）**

```html
<svg viewBox="0 0 300 300" class="flywheel-svg">
  <!-- 外圆 -->
  <circle cx="150" cy="150" r="120" fill="none" stroke="#1B2A4A" stroke-width="1"/>
  <!-- 4个节点 -->
  <g class="node" transform="translate(150,30)">
    <circle r="24" fill="#0F1E35" stroke="#29B8D4" stroke-width="1.5"/>
    <text y="5" text-anchor="middle" fill="#29B8D4" font-size="11" font-family="IBM Plex Mono">开发者</text>
  </g>
  <!-- 箭头弧线 -->
  <path d="M 210 90 A 80 80 0 0 1 240 170" fill="none" stroke="#29B8D4" stroke-width="1"
        stroke-dasharray="4 4" marker-end="url(#arrow)"/>
  <!-- ... 其余节点 -->
  <defs>
    <marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#29B8D4"/>
    </marker>
  </defs>
</svg>
```

---

#### 路径C：产品截图 → 设备 Mockup（最真实）

**步骤：**
1. 截取公司产品的官网/App 截图（1600×900px）
2. 套入设备 mockup 框架（Mockup 类工具：shots.so 导出 SVG，或自建 CSS 框架）
3. 叠加青色色调滤镜：`filter: hue-rotate(-20deg) saturate(0.8)`
4. 放入卡片的图片槽位

**CSS 设备框架（无需外部图片）：**

```css
.device-mockup {
  border: 2px solid #1E3A5F;
  border-radius: 12px;
  overflow: hidden;
  background: #0A0F1A;
  position: relative;
}
.device-mockup::before {
  /* 顶部摄像头 */
  content: '';
  display: block;
  width: 60px; height: 6px;
  background: #1B2A4A;
  border-radius: 0 0 4px 4px;
  margin: 0 auto;
}
.device-mockup img {
  width: 100%;
  display: block;
  /* 青色色调 */
  filter: hue-rotate(-10deg) saturate(0.75) brightness(0.9);
  mix-blend-mode: normal;
}
/* 扫描线叠加 */
.device-mockup::after {
  content: '';
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg, transparent, transparent 2px,
    rgba(41,184,212,0.03) 2px, rgba(41,184,212,0.03) 3px
  );
  pointer-events: none;
}
```

---

### 4.3 插图与卡片的集成方式

**集成到 GZHv2 的字段系统：**

```python
# markdown_builder.py 中，main_product_img_src 字段
# 存储路径格式：
#   /assets/logos/<company>/3d.png      → 路径A AI生成
#   template:terminal                    → 路径B CSS模板名
#   /assets/screenshots/<company>/ui.png → 路径C 截图

# html-card-renderer.js 中扩展 imageHTML()：
def imageHTML(cardData):
  src = cardData.get('main_product_img_src', '')
  if src.startswith('template:'):
    template_name = src.replace('template:', '')
    return f'<div class="template-illustration {template_name}"></div>'
  elif src:
    return f'<img class="card-image" src="{src}" alt="">'
  else:
    return '<div class="card-image placeholder"></div>'
```

---

## 五、颜色系统（完整版）

```css
:root {
  /* ── 主色 ── */
  --navy-900:  #060D1A;  /* 最深背景，body */
  --navy-800:  #0B1629;  /* 卡片主背景 */
  --navy-700:  #111E35;  /* 卡片渐变深色端 */
  --navy-600:  #1B2A4A;  /* 卡片渐变浅色端 */
  --navy-500:  #243559;  /* border、分隔线 */
  --navy-400:  #2E4470;  /* hover 状态 */

  /* ── 强调色 ── */
  --cyan-500:  #29B8D4;  /* 主强调，所有高亮 */
  --cyan-400:  #4DCAE0;  /* hover/active */
  --cyan-600:  #1A8FA3;  /* 次级强调 */
  --cyan-glow: rgba(41,184,212,0.12);  /* 辉光背景 */

  /* ── 中性色 ── */
  --white:     #FFFFFF;
  --white-80:  rgba(255,255,255,0.80);  /* 主文字 */
  --white-60:  rgba(255,255,255,0.60);  /* 次级文字 */
  --white-30:  rgba(255,255,255,0.30);  /* 弱文字 */
  --white-08:  rgba(255,255,255,0.08);  /* 微背景 */
  --white-04:  rgba(255,255,255,0.04);  /* 极弱背景 */

  /* ── 语义色 ── */
  --muted:     #6B82A0;  /* 标签、日期 */
  --muted-dim: #3D546E;  /* 分隔线文字 */

  /* ── 各卡片背景 ── */
  --bg-p1: linear-gradient(160deg, #0D1A2E 0%, #0B1629 100%);
  --bg-p2: linear-gradient(160deg, #111E35 0%, #0B1629 100%);
  --bg-p3: #0B1629;
  --bg-p4: linear-gradient(135deg, #0D1A2E 0%, #1B2A4A 100%);
  --bg-p5: #0B1629;
  --bg-p6: linear-gradient(180deg, #0D1A2E 0%, #111E35 100%);
  --bg-p7: linear-gradient(160deg, #0B1629 0%, #060D1A 100%);
  --bg-p8: #111E35;
}
```

---

## 六、Typography Scale（完整）

```css
/* Display — Bebas Neue，仅用于封面大字 */
.t-display {
  font-family: var(--font-display);
  font-size: 96px;
  line-height: 0.92;
  letter-spacing: -0.02em;
  color: var(--white);
}

/* Heading 1 — 章节标题 */
.t-h1 {
  font-family: var(--font-display);  /* Bebas Neue */
  font-size: 52px;
  line-height: 1.0;
  letter-spacing: -0.01em;
  color: var(--white);
}

/* Heading 2 — 中文大标题 */
.t-h2 {
  font-family: var(--font-zh);  /* Source Han Sans Heavy */
  font-weight: 900;
  font-size: 36px;
  line-height: 1.1;
  color: var(--white);
}

/* Label — 字段标签（IBM Plex Mono）*/
.t-label {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--cyan-500);
}

/* Body — 字段内容 */
.t-body {
  font-family: var(--font-body);
  font-size: 26px;
  line-height: 1.52;
  color: var(--white-80);
}

/* Body Small */
.t-body-sm {
  font-family: var(--font-body);
  font-size: 20px;
  line-height: 1.5;
  color: var(--white-60);
}

/* Data — 数字、指标 */
.t-data {
  font-family: var(--font-mono);
  font-size: 28px;
  font-weight: 700;
  color: var(--cyan-500);
  letter-spacing: -0.02em;
}

/* Caption — 页码、小注 */
.t-caption {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.14em;
  color: var(--muted-dim);
}
```

---

## 七、文件组织结构

```
GZHv2-main/
  canvas/
    fonts/                        ← 自托管字体（Puppeteer 必需）
      BebasNeue-Regular.woff2
      IBMPlexMono-Medium.woff2
      IBMPlexMono-Bold.woff2
      InstrumentSans-Regular.woff2
      InstrumentSans-SemiBold.woff2
      SourceHanSansCN-Regular.woff2
      SourceHanSansCN-Heavy.woff2
    assets/
      logos/                      ← 路径A：AI 生成 3D 图
        anthropic/
          3d.png
          3d@2x.png
      screenshots/                ← 路径C：产品截图 mockup
        claude-code/
          ui.png
    js/
      html-card-renderer.js       ← 已改造
      bg-loader.js                ← 背景图注入
      illustrations.js            ← 新增：路径B CSS模板注册表
    css/
      tokens.css                  ← 颜色 + 字体变量
      typography.css              ← 字号 scale
      decorations.css             ← 点缀组件
      illustrations.css           ← 路径B CSS插图样式
    card.html
    card-renderer.html
```

---

## 八、实施优先级

| 优先级 | 任务 | 工时估算 |
|--------|------|---------|
| P0 | 下载 5 个字体文件，配置 @font-face 自托管 | 1h |
| P0 | 将颜色 token 和 typography scale 写入 tokens.css | 1h |
| P1 | 实现点缀组件1–5（CSS，无图片依赖） | 2h |
| P1 | 替换 html-card-renderer.js 用新字体变量 | 1h |
| P2 | 路径B：实现 terminal、API、flywheel 三个 CSS 插图模板 | 3h |
| P2 | 路径A：为前 5 家公司生成 AI 3D logo，测试集成 | 2h |
| P3 | 路径C：截图 mockup CSS 框架 + 滤镜调色 | 2h |
| P3 | Puppeteer 加入 `document.fonts.ready` 等待 | 0.5h |

**总计约 12–13 小时，可分两个工作日完成。**
