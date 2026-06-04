# Batch 1: Pipeline → research_fields + 降级旧定稿

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通解耦主链路第一步 — 研究完成后自动写入 research_fields，并让主定稿流程从旧的"1-8卡逐张markdown_full"切换到"字段定稿→卡片设置→排版"

**Architecture:** 在 pipeline.py 末尾增加一行调用 `split_research_to_fields` + `insert_research_fields_batch`；在 editor.html 中隐藏旧的"内容定稿"手风琴（保留入口兼容），默认展开"字段定稿"

**Tech Stack:** Python (pipeline.py, db.py), vanilla JS (editor.js), HTML

---

### Task 1: Pipeline 写入 research_fields

**Files:**
- Modify: `webapp/pipeline.py` (after line ~658, after `save_research_records`)

- [ ] **Step 1: 在 pipeline.py 中添加 research_fields 写入逻辑**

在 `pipeline.py` 中找到 `database.save_research_records(config.DB_PATH_RESEARCH, records)` 这行。在其后添加：

```python
# 写入字段级表 research_fields（解耦架构：字段不再属于任何卡片）
from services.field_service import split_research_to_fields
from repositories.field_repo import insert_research_fields_batch

for record in records:
    version = record.get('version', 'standard')
    field_rows = split_research_to_fields(record, version)
    if field_rows:
        insert_research_fields_batch(config.DB_PATH_RESEARCH, field_rows)
```

- [ ] **Step 2: 验证 Python 语法**

```bash
cd webapp && python3 -m py_compile pipeline.py
```
Expected: 无输出（编译成功）

- [ ] **Step 3: 检查导入链路**

```bash
cd webapp && python3 -c "
from services.field_service import split_research_to_fields
from repositories.field_repo import insert_research_fields_batch
print('Imports OK')
"
```
Expected: "Imports OK"

- [ ] **Step 4: Commit**

```bash
git add webapp/pipeline.py
git commit -m "feat: pipeline writes research_fields after each research job

After save_research_records writes the wide table, each record is now
also split into per-field rows via split_research_to_fields and written
to research_fields. This connects the pipeline to the field-level
decoupled architecture."
```

---

### Task 2: 降级旧的"内容定稿 1-8 卡"

**Files:**
- Modify: `webapp/templates/editor.html` (手风琴顺序和默认展开)
- Modify: `webapp/static/js/editor.js` (init() 的默认 section)

- [ ] **Step 1: editor.html — 调整手风琴顺序，字段定稿置顶并默认展开**

将"字段定稿"手风琴移到第一位，并设置 `open` class：

```html
<!-- 手风琴1：字段定稿（主流程入口，默认展开） -->
<div class="accordion-section" data-od-id="editor-field-finalize">
  <div class="accordion-header open" data-section="field-finalize">
    <span class="arrow">&#9654;</span> 字段定稿
  </div>
  <div class="accordion-body open" data-section="field-finalize" data-od-id="editor-field-finalize-body">
    <div id="field-finalize-content" data-od-id="editor-field-finalize-content">
      <!-- 由 field-finalize-panel.js 动态渲染 -->
    </div>
  </div>
</div>
```

将"内容定稿（兼容）"移到字段定稿之后，去掉默认 `open`：

```html
<!-- 手风琴2：内容定稿（旧版 1-8 卡，兼容入口） -->
<div class="accordion-section">
  <div class="accordion-header" data-section="content">
    <span class="arrow">&#9654;</span> 内容定稿（旧版 1-8 卡）
  </div>
  <div class="accordion-body" data-section="content">
    ...
  </div>
</div>
```

- [ ] **Step 2: editor.js — init() 默认启动字段定稿模式**

修改 `EditorApp.init()` 中 `this.switchSection('content')` 为 `this.switchSection('field-finalize')`：

```javascript
// 旧: this.switchSection('content');
this.switchSection('field-finalize');
```

同时在 `FieldFinalizePanel.init` 在 init() 中需要被触发。当前 init() 只通过手风琴点击事件触发，需要改为 init 时主动调用：

```javascript
// 在 EditorApp.init() 中，switchSection('field-finalize') 之后：
if (this.companyName) {
  FieldFinalizePanel.init(this.companyName);
}
```

- [ ] **Step 3: 验证 HTML 结构**

```bash
cd webapp && python3 app.py &
sleep 2
curl -s http://127.0.0.1:5050/editor | grep -E '字段定稿|内容定稿.*旧版|accordion-header open'
```
Expected: 字段定稿的 accordion-header 有 `open` class，内容定稿没有

- [ ] **Step 4: Commit**

```bash
git add webapp/templates/editor.html webapp/static/js/editor.js
git commit -m "refactor: field-finalize as default, downgrade old 1-8 card flow

- Field-finalize accordion becomes the first/default section
- Old content finalization renamed to '内容定稿（旧版 1-8 卡）' for compatibility
- EditorApp.init now starts in field-finalize mode
- FieldFinalizePanel auto-initializes on page load"
```

---

### Task 3: 端到端验证

- [ ] **Step 1: 启动服务并测试完整流程**

```bash
cd webapp && python3 app.py &
sleep 2

# 1. 研究一家公司（如果已有数据跳过）
curl -X POST http://127.0.0.1:5050/api/research/start \
  -H "Content-Type: application/json" \
  -d '{"company_name":"TestCo","company_url":"https://example.com"}'

# 2. 等研究完成后检查 research_fields
# 在浏览器打开 http://127.0.0.1:5050/editor?company=TestCo
# 验证：左侧默认展开"字段定稿"，右侧显示字段定稿面板
```

- [ ] **Step 2: 验证 research_fields 有数据**

```bash
sqlite3 db/research_db.sqlite "SELECT COUNT(*) FROM research_fields WHERE company_name='TestCo'"
```
Expected: >0（研究完成后应有字段行）

- [ ] **Step 3: pkill server**

```bash
pkill -f "python3 app.py"
```
