# GZHv2 商业研究中台升级 — 实施清单 ✅ 全部完成

> **状态: 全部完成** — 2026-06-17，详见 `IMPLEMENTATION_REPORT.md`。

从 PDF《GZHv2 商业研究中台升级技术文档》提取，映射到当前代码库状态。

## 状态说明
- **done** — 已完成/已有基础
- **partial** — 部分完成/需改进
- **blocked** — 依赖外部条件（API Key、网络等）
- **todo** — 待实现

---

## P0 — 必做（核心数据完整性）

### 1. 修复 L0/LLM 输入，保留 evidence_pool
- **当前**: `_prepare_raw_data_for_llm()` 删除所有 `_` 前缀 key（丢失 `_evidence_pool`、`_source_summary`、`_source_warnings`、`_company_identity`）
- **目标**: 改为结构化输入，显式包含 `company_identity`、`source_audit`、`source_warnings`、`evidence_pool`、`raw_sources`
- **文件**: `webapp/pipeline.py` 行 855-894
- **状态**: todo

### 2. company_key 贯穿 research_fields / final_fields
- **当前**: `company_name` 作为主键；`company_identity.py` 已有 `CompanyIdentity` 但未贯穿字段层
- **目标**: research_fields 和 final_fields 增加 `company_key` 列；查询优先用 `company_key`，缺失回退 `company_name`
- **文件**: `webapp/repositories/field_repo.py`, `webapp/services/field_service.py`, `db/migrations/`
- **状态**: partial (CompanyIdentity 已有，但字段表未迁移)

### 3. confirmed 必须绑定 evidence
- **当前**: `field_status.py` 和 `field_resolver.py` 中 `official_fact` 有值即标 `confirmed`，不检查证据
- **目标**: 无 `evidence_span_ids` → 不得 `confirmed`；private_metric 无直接来源 → `unavailable`
- **文件**: `webapp/research/field_status.py`, `webapp/research/field_resolver.py`
- **状态**: todo

### 4. 统一字段状态枚举
- **当前**: 已有 `confirmed`, `derived`, `proxy`, `unavailable`, `manual_needed`, `not_applicable`, `llm_extracted`
- **缺**: `industry_avg`, `conflict`, `draft`, `hidden`
- **文件**: `webapp/research/field_status.py`, `webapp/research/field_resolver.py`
- **状态**: partial (大部分已有，缺 4 个)

### 5. D/E 私有指标不得盲目补采
- **当前**: `gap_detector.py` 的 `CRITICAL_GAPS` 对所有字段（含 D/E）生成补采 query
- **目标**: `gap_detector` 读取 `field_manifest.yaml`，A/B/C 才补采，D/E 跳过
- **文件**: `webapp/gap_detector.py`, `webapp/pipeline.py`
- **状态**: todo

### 6. gap_detector/gap_auditor 读取 field_manifest
- **当前**: `gap_detector.py` 用硬编码 `CRITICAL_GAPS`；`gap_auditor.py` 已调用 `_load_manifest()` 分类
- **目标**: `gap_detector.py` 按 manifest category 过滤补采字段
- **文件**: `webapp/gap_detector.py`
- **状态**: partial (gap_auditor 已读 manifest，gap_detector 未读)

### 7. LTV/CAC 四级降级规则
- **当前**: `field_manifest.yaml` 已有 D 类标记和 `if_missing: unavailable`
- **目标**: 实现 confirmed → proxy → industry_avg → unavailable 四级降级；行业均值展示注明"不代表公司披露"
- **文件**: `webapp/research/field_resolver.py`, `webapp/research/field_status.py`
- **状态**: partial (有 unavailable 标记，缺 industry_avg 和四级降级)

### 8. 解决 Limitless/limitless/limitless.ai 分裂
- **当前**: `company_identity.py` 已有 `company_key`（基于 host）；`db.py` 的 `get_companies` 已有 `company_key` 回退
- **目标**: 全链路统一用 `company_key`，大小写不同不生成两套字段
- **文件**: `webapp/company_identity.py`, `webapp/db.py`, `webapp/repositories/field_repo.py`
- **状态**: partial (CompanyIdentity 已有，但 field_repo 仍用 company_name 查询)

---

## P1 — 应做（证据层升级）

### 1. 新增 migration: source_documents
- **状态**: todo
- **文件**: `db/migrations/013_source_documents.sql`

### 2. 新增 migration: evidence_spans
- **状态**: todo
- **文件**: `db/migrations/014_evidence_spans.sql`

### 3. 新增 migration: field_candidates
- **状态**: todo
- **文件**: `db/migrations/015_field_candidates.sql`

### 4. 新增 migration: final_card_values
- **状态**: todo
- **文件**: `db/migrations/016_final_card_values.sql`

### 5. 新增 migration: card_schema
- **状态**: todo
- **文件**: `db/migrations/017_card_schema.sql`

### 6. 新增 migration: research_fields/final_fields 加 company_key
- **状态**: todo
- **文件**: `db/migrations/018_company_key_fields.sql`

### 7. 新增 document/evidence 存储层
- **目标**: 采集结果先入 `source_documents`，再抽取 `evidence_spans`
- **文件**: `webapp/research/document_store.py`, `webapp/research/evidence_extractor.py`
- **状态**: partial (evidence_persister 已有，但写的是 evidence_items 旧表)

### 8. OfficialAgent 最小可用实现
- **目标**: 抓取 16 个固定路径（/, /about, /company, /team, /founders, /pricing, /customers, /case-studies, /blog, /news, /press, /docs, /changelog, /security, /careers），失败不阻塞
- **文件**: `webapp/research_agents/agents/official_agent.py`
- **状态**: todo

### 9. FieldResolver v2
- **目标**: 按 official_fact、market_model、private_metric、derived、analysis、b2b_remap 分类处理；market_size/market_cagr/tam 必须带 region/segment/year/source
- **文件**: `webapp/research/resolvers/field_resolver_v2.py`
- **状态**: partial (v1 已有，缺 market_model 口径检查和 industry_avg 降级)

### 10. field_candidates 替代三版本混表
- **目标**: field_candidates 保存 candidate_value、agent_name、evidence_span_ids、confidence、status、conflict_note/reasoning_summary
- **文件**: `webapp/research_agents/storage/candidate_store.py`
- **状态**: todo

---

## P2 — 可做（Agent 化和论坛校验）

### 1. 创建 research_agents 目录结构
- **状态**: todo
- **文件**: `webapp/research_agents/__init__.py`, `webapp/research_agents/{agents,forum,resolvers,storage}/`

### 2. Agent 骨架
- identity_agent, source_planning_agent, official_agent, query_agent, github_agent, media_agent, community_agent, insight_agent, metric_agent, competitor_agent, report_agent
- **目标**: 非核心 agent 可最小接口+fallback，不得破坏主流程
- **状态**: todo

### 3. ForumModerator
- **目标**: 检查 confirmed 无证据、市场字段缺口径、候选值冲突、私有指标误 confirmed
- **输出**: weak_evidence_fields, conflict_fields, manual_needed_fields, refetch_tasks
- **文件**: `webapp/research_agents/forum/moderator.py`
- **状态**: todo

### 4. card_schema 内置 8 页字段配置
- **目标**: 8 页卡片不再写死在代码里
- **文件**: `db/migrations/017_card_schema.sql`, seed data
- **状态**: todo

### 5. final_card_values 支持 company_key+card_no+field_key 去重
- **目标**: 唯一键 `(company_key, card_no, field_key)`
- **文件**: `db/migrations/016_final_card_values.sql`
- **状态**: todo

---

## 验收检查项

- [ ] migration 可执行（`python3 db/migrate.py`）
- [ ] 能模拟或真实生成 company_key
- [ ] 能写 source_documents / evidence_spans / field_candidates / field_resolutions 或 final_card_values
- [ ] confirmed 无证据 → 测试失败
- [ ] D/E 字段进入补采 → 测试失败
- [ ] company_key 大小写不同不生成两套字段
- [ ] 旧字段读取可回退
- [ ] 现有测试全通过
