--- Page 1 ---
GZHv2 商业研究中台升级技术文档
1. 项目目标
将 GZHv2 从“AI 公司信息卡片生成器”升级为“可追溯、可复用、可扩展的商业研究中台”。
核心目标：
输入公司名或官网后，自动完成公司识别、信息采集、证据抽取、字段解析、缺口判断、补采、定稿和
卡片生成。
8 页知识卡片不再依赖固定宽表，而是由字段池和卡片配置动态组合。
每个字段必须能回答三个问题：
值从哪里来；
是否可信；
为什么最终采用这个版本。
对不可公开获得的指标，例如 CAC、L TV、毛利率、Burn Rate，不再强行补搜或硬填，而是按规则标记
为不可得、代理估算或行业均值。
借鉴 BettaFish 的多 Agent 分工和论坛式校验机制，但改造为适合 AI 初创公司商业研究的字段驱动流
程。
2. 当前问题判断
2.1 数据库层问题
当前字段设计把四类内容混在一起：
原始事实字段；
多模型候选结果；
人工定稿结果；
卡片展示文案。
典型表现：
字段 Key / 标签 / Standard / Business / Spread / 定稿值 / 状态
这种结构适合人工对比，不适合系统长期维护。
核心问题是：字段没有证据绑定，多版本结果没有独立候选记录，定稿值和原始事实没有分层。
2.2 研究流程问题
当前链路大致是：1. 
2. 
3. 
4. 
5. 
6. 
7. 
8. 
1. 
2. 
3. 
4. 
1

--- Page 2 ---
公司识别
→ Tavily / GitHub / YouTube / 官网并行采集
→ evidence_pool 去重打分
→ gap_detector 缺口补采
→ L0-L3 LLM 分析
→ research 宽表
→ research_fields 字段拆分
→ final_fields 定稿
→ 卡片渲染
已有基础是好的，但存在 5 个关键缺陷：
证据池没有真正成为字段确认依据。
L0 输入会清理 _evidence_pool 、_source_summary  等内部字段，导致证据层半失效。
confirmed  状态过宽松，只要 LLM 有值就可能被认为已确认。
缺口补采没有严格遵守字段可得性规则，私有指标也会被反复搜索。
company_key  没有贯穿字段层和定稿层，容易出现 Limitless / limitless / limitless.ai  分裂。
3. 总体设计原则
3.1 字段不是卡片
数据库不应该按 8 页卡片直接建宽表。
正确关系是：
事实字段池
→ 分析字段池
→ 定稿字段池
→ 卡片配置
→ HTML / PNG / Markdown 渲染
卡片只是展示方案，不是底层数据结构。
3.2 事实、推理、文案必须分层
类型 示例 存储位置
事实成立时间、融资金额、官网、客
户名称companies / products / funding_rounds / customers /
metrics
指标 ARR、MAU、留存率、L TV/CAC metrics
证据来源网页、引用片段、截图、访
谈字幕source_documents / evidence_spans
推理 生态位、竞争优势、错位机会 company_analysis1. 
2. 
3. 
4. 
5. 
2

--- Page 3 ---
类型 示例 存储位置
候选答
案Standard / Business / Spread field_candidates
定稿文
案卡片最终显示内容 final_card_values
3.3 所有字段必须有状态
统一状态枚举：
confirmed       有直接证据确认
derived         由已确认字段计算得出
proxy           基于同类公司或市场报告估算
industry_avg    使用行业平均值
llm_extracted   LLM 提取但未绑定证据
manual_needed   需要人工判断
unavailable     公开不可得
not_applicable  不适用
conflict        多来源冲突
draft           待定稿
hidden          不展示
禁止继续只用：
暂缺
未知
—
4. 目标系统架构
升级后的研究流程：
输入公司名 / 官网
  ↓
CompanyIdentityAgent
公司身份归一化，生成 company_key
  ↓
SourcePlanningAgent
根据字段需求生成采集计划
  ↓
多 Agent 并行采集
OfficialAgent / QueryAgent / MediaAgent / CommunityAgent / GitHubAgent / InsightAgent
  ↓
3

--- Page 4 ---
source_documents
保存完整来源文档
  ↓
EvidenceExtractor
从文档中切出字段证据片段
  ↓
evidence_spans
证据片段入库
  ↓
FieldResolver
字段确认、估算、不可得、冲突处理
  ↓
ForumModerator
检查字段冲突、幻觉、证据不足
  ↓
GapRefetchPlanner
只对可补采字段执行二次补采
  ↓
AnalysisResolver
生成生态位、GTM、竞争态势、变现能力等分析字段
  ↓
ReportAgent
生成 Standard / Business / Spread 候选版本
  ↓
final_card_values
人工或自动定稿
  ↓
card_schema
自由组合为 8 页知识卡片
  ↓
HTML / PNG / Markdown 输出
5. 数据库设计
5.1 公司主体表： companies
CREATE TABLE companies (
idTEXT PRIMARY KEY ,
company_key TEXT NOT NULL UNIQUE ,
name TEXT NOT NULL ,
canonical_name TEXT ,
aliases TEXT ,
website_url TEXT ,
company_category TEXT ,
company_definition TEXT ,
founded_date TEXT ,
hq_country TEXT ,
hq_city TEXT ,
4

--- Page 5 ---
main_business TEXT ,
core_advantage TEXT ,
industry_positioning TEXT ,
data_confidence TEXT DEFAUL T 'medium' ,
created_at TEXT DEFAUL T CURRENT_TIMESTAMP ,
updated_at TEXT DEFAUL T CURRENT_TIMESTAMP
);
说明：
company_key  是主身份，建议使用官网 host，例如 sardine.ai 。
name 只是展示名，不再作为主键。
所有表优先关联 company_key 。
5.2 产品表： products
CREATE TABLE products (
idTEXT PRIMARY KEY ,
company_key TEXT NOT NULL ,
name TEXT NOT NULL ,
is_primary INTEGER DEFAUL T 0,
product_definition TEXT ,
target_pain_points TEXT ,
core_features TEXT ,
usage_play TEXT ,
tech_stack TEXT ,
regional_markets TEXT ,
pricing_detail TEXT ,
product_url TEXT ,
screenshot_asset_id TEXT ,
confidence TEXT DEFAUL T 'medium' ,
created_at TEXT DEFAUL T CURRENT_TIMESTAMP
);
第三页主产品字段从这里读取：
名称
针对的痛点
核心功能
核心用法玩法
技术栈
地区市场
定价明细
月活、留存率等指标不放在 products ，统一放入 metrics 。• 
• 
• 
5

--- Page 6 ---
5.3 指标表： metrics
CREATE TABLE metrics (
idTEXT PRIMARY KEY ,
company_key TEXT NOT NULL ,
entity_type TEXT NOT NULL ,
entity_id TEXT ,
metric_key TEXT NOT NULL ,
metric_value REAL ,
metric_text TEXT ,
unit TEXT ,
period TEXT ,
region TEXT ,
segment TEXT ,
source_id TEXT ,
status TEXT DEFAUL T 'unavailable' ,
estimate_method TEXT ,
confidence TEXT DEFAUL T 'medium' ,
created_at TEXT DEFAUL T CURRENT_TIMESTAMP
);
适合放入 metrics  的字段：
market_size
market_cagr
tam
sam
som
arr
mrr
mau
active_users
registered_users
paying_users
retention_rate
churn_rate
ltv
cac
ltv_cac_ratio
gross_margin
burn_rate
runway_months
team_size
6

--- Page 7 ---
5.4 赛道表： sectors
CREATE TABLE sectors (
idTEXT PRIMARY KEY ,
company_key TEXT NOT NULL ,
sector_name TEXT ,
market_landscape TEXT ,
market_size_summary TEXT ,
market_cagr_summary TEXT ,
tam_summary TEXT ,
source_note TEXT ,
confidence TEXT DEFAUL T 'medium'
);
说明：
sectors  存文本判断；
具体数字仍进入 metrics ；
市场规模必须包含口径：年份、地区、细分赛道、数据来源。
5.5 创始团队表： founders
CREATE TABLE founders (
idTEXT PRIMARY KEY ,
company_key TEXT NOT NULL ,
name TEXT NOT NULL ,
role TEXT ,
education TEXT ,
career_background TEXT ,
founder_achievement TEXT ,
credibility_note TEXT ,
linkedin_url TEXT ,
confidence TEXT DEFAUL T 'medium'
);
新增 credibility_note ，用于解释：
为什么这个团队适合做这家公司？
这是创始团队页最重要的判断。
5.6 融资表： funding_rounds
CREATE TABLE funding_rounds (
idTEXT PRIMARY KEY ,• 
• 
• 
7

--- Page 8 ---
company_key TEXT NOT NULL ,
round_name TEXT ,
announced_date TEXT ,
amount_usd REAL ,
valuation_usd REAL ,
lead_investor TEXT ,
investors TEXT ,
source_id TEXT ,
confidence TEXT DEFAUL T 'medium'
);
第二页“融资情况”由这张表聚合生成，不再手写长文本。
5.7 客户与用户群体表： customers
CREATE TABLE customers (
idTEXT PRIMARY KEY ,
company_key TEXT NOT NULL ,
customer_type TEXT ,
persona_name TEXT ,
customer_name TEXT ,
industry TEXT ,
customer_pain TEXT ,
choice_reason TEXT ,
evidence_summary TEXT ,
source_id TEXT ,
confidence TEXT DEFAUL T 'medium'
);
customer_type  可选：
persona
named_customer
industry_segment
第五页字段映射：
用户画像 → customer_type = persona
具体客户名称 → customer_type = named_customer
客户选择理由 → choice_reason + evidence_summary
8

--- Page 9 ---
5.8 竞品表： competitors
CREATE TABLE competitors (
idTEXT PRIMARY KEY ,
company_key TEXT NOT NULL ,
competitor_name TEXT NOT NULL ,
competitor_url TEXT ,
product_summary TEXT ,
company_summary TEXT ,
rank INTEGER ,
overlap_area TEXT ,
difference_area TEXT ,
competitor_strength TEXT ,
competitor_weakness TEXT ,
source_id TEXT ,
confidence TEXT DEFAUL T 'medium'
);
第八页字段映射：
Top3 公司简介 → competitors
被研公司在竞争中的位置 → company_analysis.competitive_position
错位竞争机会 → company_analysis.differentiation_opportunity
竞争优势 → company_analysis.competitive_advantage
5.9 公司分析表： company_analysis
CREATE TABLE company_analysis (
idTEXT PRIMARY KEY ,
company_key TEXT NOT NULL ,
ecosystem_niche TEXT ,
monetization_strategy TEXT ,
pricing_strategy TEXT ,
value_capture_score REAL ,
defensibility_score REAL ,
competitive_position TEXT ,
differentiation_opportunity TEXT ,
competitive_advantage TEXT ,
moat TEXT ,
risk_window TEXT ,
gtm_motion TEXT ,
cold_start TEXT ,
growth_strategy TEXT ,
growth_flywheel TEXT ,
analysis_version INTEGER DEFAUL T 1,
confidence TEXT DEFAUL T 'medium' ,
9

--- Page 10 ---
created_at TEXT DEFAUL T CURRENT_TIMESTAMP
);
说明：
这里存推理结果；
不存原始事实；
所有分析必须尽量引用 evidence_spans  或 confirmed 字段。
5.10 来源文档表： source_documents
CREATE TABLE source_documents (
idINTEGER PRIMARY KEY AUTOINCREMENT ,
run_id TEXT ,
company_key TEXT ,
source_type TEXT ,
source_url TEXT ,
title TEXT ,
publisher TEXT ,
published_at TEXT ,
fetched_at TEXT DEFAUL T CURRENT_TIMESTAMP ,
raw_text TEXT ,
content_hash TEXT ,
trust_tier TEXT ,
intent TEXT
);
source_type  可选：
official_site
official_blog
pricing_page
case_study
press_release
media_article
github
youtube
youtube_transcript
product_hunt
hacker_news
reddit
market_report
database
manual• 
• 
• 
10

--- Page 11 ---
5.11 证据片段表： evidence_spans
CREATE TABLE evidence_spans (
idINTEGER PRIMARY KEY AUTOINCREMENT ,
document_id INTEGER NOT NULL ,
company_key TEXT NOT NULL ,
field_key TEXT ,
quote_text TEXT ,
normalized_fact TEXT ,
start_offset INTEGER ,
end_offset INTEGER ,
confidence REAL ,
created_by_agent TEXT ,
created_at TEXT DEFAUL T CURRENT_TIMESTAMP
);
这张表解决字段可追溯问题。
5.12 研究运行表： research_runs
CREATE TABLE research_runs (
idTEXT PRIMARY KEY ,
company_key TEXT NOT NULL ,
display_name TEXT ,
input_query TEXT ,
research_depth TEXT ,
status TEXT ,
started_at TEXT DEFAUL T CURRENT_TIMESTAMP ,
finished_at TEXT ,
config_json TEXT
);
5.13 候选字段表： field_candidates
CREATE TABLE field_candidates (
idINTEGER PRIMARY KEY AUTOINCREMENT ,
run_id TEXT NOT NULL ,
company_key TEXT NOT NULL ,
field_key TEXT NOT NULL ,
agent_name TEXT ,
candidate_value TEXT ,
evidence_span_ids TEXT ,
confidence REAL ,
status TEXT ,
conflict_group_id TEXT ,
reasoning_summary TEXT ,
11

--- Page 12 ---
selected INTEGER DEFAUL T 0,
created_at TEXT DEFAUL T CURRENT_TIMESTAMP
);
用于替代当前混在一起的：
Standard / Business / Spread
5.14 字段定稿表： final_card_values
CREATE TABLE final_card_values (
idINTEGER PRIMARY KEY AUTOINCREMENT ,
run_id TEXT NOT NULL ,
company_key TEXT NOT NULL ,
card_no INTEGER NOT NULL ,
field_key TEXT NOT NULL ,
final_value TEXT ,
source_evidence_ids TEXT ,
status TEXT DEFAUL T 'draft' ,
confidence TEXT DEFAUL T 'medium' ,
editor_note TEXT ,
updated_at TEXT DEFAUL T CURRENT_TIMESTAMP ,
UNIQUE (company_key ,card_no ,field_key )
);
5.15 卡片配置表： card_schema
CREATE TABLE card_schema (
idINTEGER PRIMARY KEY AUTOINCREMENT ,
card_no INTEGER NOT NULL ,
card_title TEXT NOT NULL ,
field_key TEXT NOT NULL ,
display_label TEXT ,
render_order INTEGER ,
required INTEGER DEFAUL T 0,
max_length INTEGER ,
render_type TEXT DEFAUL T 'text'
);
8 页卡片不再写死在代码里，而是由 card_schema  控制。
12

--- Page 13 ---
6. 8 页卡片字段映射
第 1 页：首页
company_name       → companies.name
company_category   → companies.company_category
第 2 页：公司简介
赛道市场格局       → sectors.market_landscape
赛道市场规模       → metrics.metric_key = market_size
赛道年复合增长率   → metrics.metric_key = market_cagr
赛道总潜在市场     → metrics.metric_key = tam
公司地理位置       → companies.hq_city + companies.hq_country
公司成立时间       → companies.founded_date
公司主营业务       → companies.main_business
公司核心竞争优势   → companies.core_advantage
公司融资情况       → funding_rounds 聚合
公司取得成就       → company_analysis 或 evidence 聚合
公司行业定位       → companies.industry_positioning
第 3 页：主产品
名称               → products.name where is_primary = 1
针对的痛点         → products.target_pain_points
核心功能           → products.core_features
核心用法玩法       → products.usage_play
技术栈             → products.tech_stack
地区市场           → products.regional_markets
月活跃用户         → metrics.metric_key = mau
留存率             → metrics.metric_key = retention_rate
定价明细           → products.pricing_detail
第 4 页：创始团队
创始人姓名         → founders.name
职位               → founders.role
学历背景           → founders.education
职业背景           → founders.career_background
关键成就           → founders.founder_achievement
13

--- Page 14 ---
团队亮点           → founders.credibility_note 或 company_analysis
团队规模           → metrics.metric_key = team_size
第 5 页：用户群体
用户画像           → customers.customer_type = persona
具体客户名称       → customers.customer_type = named_customer
客户选择理由       → customers.choice_reason
数据与事实支撑     → customers.evidence_summary + evidence_spans
第 6 页：公司能力分析
生态位分析         → company_analysis.ecosystem_niche
盈利策略           → company_analysis.monetization_strategy
定价策略           → company_analysis.pricing_strategy
LTV                → metrics.metric_key = ltv
CAC                → metrics.metric_key = cac
LTV/CAC            → metrics.metric_key = ltv_cac_ratio
L TV/CAC 显示规则：
公司披露 → confirmed
同类公司推断 → proxy
行业均值 → industry_avg
没有依据 → unavailable
卡片文案必须显式标注：
“行业平均，不代表公司披露”
第 7 页：增长与 GTM
冷启动策略         → company_analysis.cold_start
GTM 打法           → company_analysis.gtm_motion
增长策略           → company_analysis.growth_strategy
增长飞轮           → company_analysis.growth_flywheel
渠道结构           → company_analysis 或 metrics
GTM 是 Go-To-Market，指产品如何触达客户、转化客户并形成销售闭环。
B2B 公司重点看直销、渠道、合作伙伴、创始人网络、标杆客户和 PoC。
14

--- Page 15 ---
第 8 页：竞争态势
Top3 公司简介       → competitors
被研公司竞争位置    → company_analysis.competitive_position
错位竞争机会        → company_analysis.differentiation_opportunity
竞争优势            → company_analysis.competitive_advantage
7. 信息采集方法设计
7.1 字段驱动采集
当前做法偏向：
公司名 → 搜索 query → LLM 总结
目标做法：
字段需求 → 来源策略 → 采集任务 → 文档入库 → 证据片段 → 字段解析
示例：
funding_info :
preferred_sources :
-official_press
-techcrunch
-crunchbase
-pitchbook
query_templates :
-'"{company}" funding round valuation investors'
-'"{company}" raised Series AORSeries BORSeries C'
confirm_rule :
min_evidence :1
allowed_tiers :
-official
-trusted_media
-financial_database
ltv_cac_ratio :
preferred_sources :
-company_financials
-founder_interview
-latka
-sacra
fallback :
15

--- Page 16 ---
-industry_benchmark
confirm_rule :
never_confirm_without_direct_number :true
7.2 OfficialAgent：官网深爬
当前官网只抓首页，不足。
新增 official_agent.py ，按站内路径抓取：
/
/about
/company
/team
/founders
/pricing
/customers
/case-studies
/blog
/news
/press
/docs
/changelog
/security
/careers
字段映射：
页面 可支撑字段
About 公司定义、地点、成立时间、主营业务
Team 创始人、团队亮点
Pricing 定价明细、定价策略
Customers 客户名称、用户群体
Case Studies 客户痛点、选择理由、ROI
Blog / News 产品发布、时间线、公司成就
Docs 技术栈、集成方式、API
Careers 团队规模、技术栈、地区扩张
7.3 QueryAgent：公开网页搜索
负责：
16

--- Page 17 ---
融资
市场规模
竞品
公司成就
行业定位
公开指标
新闻事件
搜索不应再追求盲目增多，而应按字段分配 query budget。
优先级：
A 类字段：必须补采
C 类字段：允许补采一次
D/E 类字段：默认不补采
7.4 GitHubAgent：开源与技术信号采集
当前 GitHub 只搜 repo metadata，建议扩展为：
README
docs
releases
issues
discussions
stars
forks
contributors
last_commit_at
license
topics
支撑字段：
技术栈
开发者采用度
开源替代
产品成熟度
社区信号
技术壁垒
17

--- Page 18 ---
7.5 MediaAgent：视频与访谈采集
当前 YouTube 只取标题和描述，不足。
新增字幕提取：
搜索 founder interview / product demo / podcast
→ 获取 video_id
→ 抓 transcript
→ 分段
→ 提取创始人背景、GTM、产品理念、冷启动、关键指标
→ 写入 source_documents
支撑字段：
founder_bg
founder_achievement
cold_start
gtm_strategy
market_opportunity
product_pain_points
7.6 CommunityAgent：社区信号采集
采集对象：
Product Hunt
Hacker News
Reddit
G2
Capterra
Chrome Web Store
App Store
X/Twitter 搜索结果
支撑字段：
用户痛点
10分钟惊喜点
用户吐槽
替代竞品
传播钩子
真实使用场景
限制：
18

--- Page 19 ---
社区来源不能用于确认融资、收入、学历、团队规模等硬事实。
7.7 InsightAgent：内部样本库与行业均值
负责：
历史公司对比
行业均值
同类产品 benchmark
过往研究样本复用
用于解决：
LTV/CAC 搜不到
CAC 搜不到
留存率搜不到
行业平均缺失
但输出必须标记为：
proxy
industry_avg
不能标记为：
confirmed
8. 研究方法设计
8.1 从 L0-L3 串行改为字段解析
当前：
L0 清洗
→ L1 横纵分析
→ L2 商业结构
→ L3 字段提取
目标：
19

--- Page 20 ---
Evidence Pool
→ Field Resolver
→ Forum Review
→ Gap Refetch
→ Analysis Resolver
→ Card Writer
原因：
串行 LLM 容易把早期遗漏传递到后面；
字段级解析更容易绑定证据；
分析字段应基于 confirmed / proxy 字段生成，而不是直接从原始搜索结果生成。
8.2 FieldResolver 规则
字段按类型处理：
字段类型 处理方式
官方事实 必须绑定证据
枚举字段 规则层 + LLM 投票 + 验证
公式字段 依赖 confirmed 字段计算
市场字段 必须有 region / segment / year
私有经营指标 默认 unavailable 或 proxy
B2B 不适配字段 转换为客户数、Logo、账户数
推理字段 基于事实字段生成，标记 analysis
8.3 ForumModerator 校验机制
借鉴 BettaFish 的论坛协作，但 GZHv2 只做字段校验，不做复杂辩论。
输入：
{
"field_key" :"funding_info" ,
"claim" :"Series C $70M, valuation $660M" ,
"evidence_ids" :[12,18],
"source_tier" :"trusted_media" ,
"confidence" :0.82 ,
"risk" :"date conflict"
}1. 
2. 
3. 
20

--- Page 21 ---
ForumModerator 只做三件事：
1. 找冲突
2. 找缺口
3. 找证据不足但被标 confirmed 的字段
输出：
conflict_fields
weak_evidence_fields
refetch_tasks
manual_needed_fields
8.4 缺口补采规则
禁止所有缺失字段都补采。
按字段可得性分类：
A 类：强事实字段，必须补采
B 类：官网/产品字段，优先官网补采
C 类：市场/竞品字段，允许补采一次
D 类：私有经营指标，不补采，转 unavailable / proxy
E 类：不适用字段，不补采，转 not_applicable
示例：
def should_refetch (field_key ,manifest ):
category =manifest [field_key ]["category" ]
return category in["A","B","C"]
9. 代码改造方案
9.1 P0：修复 L0 输入
当前 _prepare_raw_data_for_llm()  会删除 _evidence_pool 、_source_summary 、_source_warnings 。
目标：保留结构化证据输入。
建议改为：
def _prepare_raw_data_for_llm (raw_data ):
return {
21

--- Page 22 ---
"company_identity" :{
"company_key" :raw_data .get("company_key" ),
"display_name" :raw_data .get("display_name" ),
"website_host" :raw_data .get("website_host" ),
"aliases" :raw_data .get("aliases" ,[]),
},
"source_audit" :raw_data .get("_source_summary" ,{}),
"source_warnings" :raw_data .get("_source_warnings" ,[]),
"evidence_pool" :[
{
"source" :e.source ,
"intent" :e.intent ,
"title" :e.title ,
"url" :e.url,
"content" :e.content [:1200 ],
"metric_snippet" :e.metric_snippet ,
"source_score" :e.source_score ,
"entity_score" :e.entity_score ,
"final_score" :e.final_score ,
}
for einraw_data .get("_evidence_pool" ,[])[:80]
],
"raw_sources" :{
"tavily" :raw_data .get("tavily" ),
"github" :raw_data .get("github" ),
"youtube" :raw_data .get("youtube" ),
"website" :raw_data .get("website" ),
}
}
验收标准：
L0 prompt 输入中可以看到 evidence_pool、source_audit、company_identity。
9.2 P0：company_key 贯穿字段层
需要修改：
webapp/services/field_service.py
webapp/repositories/field_repo.py
db/migrations
final_fields
research_fields
当前：
22

--- Page 23 ---
company_name 作为查询主键
目标：
company_key 作为查询主键
company_name 作为展示字段
迁移策略：
research_fields  增加 company_key ；
final_fields  增加 company_key ；
旧数据用 company_identity  或官网 host 回填；
查询优先使用 company_key ，缺失时回退 company_name 。
9.3 P0：字段状态必须绑定证据
当前 field_resolver.py  中 official_fact 、private_metric  有值即 confirmed ，风险较大。
改造规则：
没有 evidence_span_ids → 不得 confirmed
private_metric 没有直接来源 → unavailable
market_model 没有 region / segment / year → manual_needed
derived 输入字段不是 confirmed / proxy → blocked
新增状态：
llm_extracted
industry_avg
conflict
9.4 P0：缺口补采读取 field_manifest
当前 gap_detector.py  用 CRITICAL_GAPS  判断缺口。
应改为读取 references/field_manifest.yaml 。
伪代码：
def build_gap_queries (display_name ,website_host ,root_domain ,gaps ,manifest ):
queries =[]
for intent ,fields ingaps .items ():
refetchable_fields =[]1. 
2. 
3. 
4. 
23

--- Page 24 ---
for field infields :
entry =manifest .get(field ,{})
ifentry .get("category" )in["A","B","C"]:
refetchable_fields .append (field )
ifnot refetchable_fields :
continue
for tmpl inGAP_QUERY_TEMPLATES .get(intent ,[])[:2]:
queries .append ({
"query" :tmpl .format (
display_name =display_name ,
website_host =website_host ,
root_domain =root_domain
),
"intent" :intent ,
"fields" :refetchable_fields
})
return queries
验收标准：
CAC / LTV / Burn Rate / Gross Margin 不再被默认补采。
9.5 P1：新增 source_documents 和 evidence_spans
当前 evidence_items  还偏轻，只保存摘要级证据。
下一步应保存完整文档与证据片段。
新增模块：
webapp/research/document_store.py
webapp/research/evidence_extractor.py
流程：
采集结果
→ source_documents
→ evidence_extractor
→ evidence_spans
→ field_candidates
24

--- Page 25 ---
9.6 P1：官网深爬
新增：
webapp/research_agents/agents/official_agent.py
职责：
发现站内关键路径
抓取页面
清洗正文
写 source_documents
提取 evidence_spans
最小实现：
先只爬 10 个固定路径
每页最多 5000 字
总字符上限 50000
失败不阻塞主流程
9.7 P1：Field Candidate 替代三版本混表
当前 Standard / Business / Spread  是展示版本，不是真正研究视角。
改造后：
OfficialAgent 候选
QueryAgent 候选
MediaAgent 候选
InsightAgent 候选
MetricAgent 候选
ReportAgent Standard 文案
ReportAgent Business 文案
ReportAgent Spread 文案
全部进入 field_candidates 。
9.8 P2：Forum Review
新增目录：
25

--- Page 26 ---
webapp/research_agents/forum/
  moderator.py
  claim_card.py
  conflict_detector.py
  refetch_planner.py
最小功能：
检查同一字段多候选值是否冲突；
检查 confirmed 字段是否有 evidence；
检查市场字段是否有口径；
生成补采任务；
输出人工确认清单。
10. 推荐目录结构
webapp/research_agents/
  __init__.py
  orchestrator.py
  state.py
  contracts.py
  agents/
    identity_agent.py
    source_planning_agent.py
    official_agent.py
    query_agent.py
    github_agent.py
    media_agent.py
    community_agent.py
    insight_agent.py
    metric_agent.py
    competitor_agent.py
    report_agent.py
  forum/
    moderator.py
    claim_card.py
    conflict_detector.py
    refetch_planner.py
  resolvers/
    field_resolver_v2.py
    metric_resolver.py
    market_size_resolver.py
    competitor_resolver.py
    gtm_resolver.py1. 
2. 
3. 
4. 
5. 
26

--- Page 27 ---
  storage/
    document_store.py
    evidence_store.py
    candidate_store.py
不建议现在重写前端。
先保持前端继续读取 research_fields / final_fields ，后端新增兼容层。
11. 字段配置文件设计
扩展 references/field_manifest.yaml 。
示例：
funding_info :
category :A
resolution_type :official_fact
required_evidence :true
allowed_sources :
-official_press
-trusted_media
-financial_database
refetchable :true
card_no :2
market_cagr :
category :C
resolution_type :market_model
required_context :
-region
-segment
-year
allow_proxy :true
refetchable :true
card_no :2
ltv_cac_ratio :
category :D
resolution_type :private_metric
required_evidence :true
fallback :
-industry_avg
refetchable :false
card_no :6
active_users :
category :E
resolution_type :b2b_remap
27

--- Page 28 ---
b2b_replace :
-paying_customers
-customer_logos
refetchable :false
card_no :3
12. 实施计划
阶段 1：稳定现有链路
目标：修复最关键的数据污染问题。
任务：
修复 _prepare_raw_data_for_llm() ，保留 evidence_pool。
field_resolver.py  增加 llm_extracted / industry_avg / conflict 。
gap_detector.py  读取 field_manifest.yaml 。
research_fields / final_fields  增加 company_key 。
final 字段定稿时保留 source_evidence_ids 。
验收：
任意公司研究结果中：
- 每个 confirmed 字段都有 evidence；
- 私有指标不会被反复补采；
- Limitless / limitless 不再分裂；
- L0 输入中能看到 evidence_pool。
阶段 2：证据层升级
目标：字段可追溯。
任务：
新增 source_documents ；
新增 evidence_spans ；
采集结果先入 source_documents；
EvidenceExtractor 从文档中抽取字段证据；
FieldResolver 基于 evidence_spans 判断字段状态。
验收：
点击任一字段，可以看到：
- 来源 URL；
- 来源标题；
- 引用片段；1. 
2. 
3. 
4. 
5. 
1. 
2. 
3. 
4. 
5. 
28

--- Page 29 ---
- 提取 Agent；
- 可信度；
- 是否存在冲突。
阶段 3：Agent 化采集
目标：从“搜索结果总结”升级为“字段驱动采集”。
任务：
新增 OfficialAgent；
新增 GitHubAgent；
新增 MediaAgent 字幕提取；
新增 CommunityAgent；
新增 InsightAgent 行业均值；
SourcePlanningAgent 根据字段 manifest 生成任务。
验收：
同一个字段可以看到多个 Agent 的候选值。
阶段 4：Forum Review
目标：降低幻觉和冲突。
任务：
新增 Claim Card；
新增 ConflictDetector；
新增 RefetchPlanner；
新增人工确认清单；
将冲突字段状态设为 conflict 或 manual_needed。
验收：
字段冲突不会直接进入 confirmed。
阶段 5：卡片配置化
目标：8 页卡片自由组合。
任务：
新增 card_schema ；1. 
2. 
3. 
4. 
5. 
6. 
1. 
2. 
3. 
4. 
5. 
1. 
29

--- Page 30 ---
新增 final_card_values ；
前端定稿台读取 card_schema；
卡片渲染不再绑定固定字段顺序；
支持新增、隐藏、调序、换字段。
验收：
用户可以调整：
- 卡片数量；
- 每页字段；
- 字段顺序；
- 字段展示方式。
13. 优先级清单
P0 必做
1. 保留 evidence_pool 给 L0
2. confirmed 必须绑定 evidence
3. D/E 类字段禁止盲目补采
4. company_key 贯穿 research_fields / final_fields
5. LTV/CAC 使用三层降级规则
P1 应做
1. source_documents
2. evidence_spans
3. 官网深爬
4. field_candidates
5. market_size_resolver
P2 可做
1. ForumModerator
2. YouTube transcript
3. CommunityAgent
4. GitHub README / docs / issues 深采
5. 卡片 schema 配置化2. 
3. 
4. 
5. 
30

--- Page 31 ---
14. 验收指标
14.1 采集质量指标
每家公司唯一 URL 数 >= 15
官网关键页抓取数 >= 5
confirmed 字段证据绑定率 >= 90%
市场字段口径完整率 >= 80%
私有指标误 confirmed 数 = 0
14.2 研究质量指标
字段缺失率下降
冲突字段被拦截
不可得字段有明确原因
LTV/CAC 不再伪装为公司事实
Top3 竞品有来源与差异说明
客户选择理由有证据支撑
14.3 产品质量指标
8 页卡片字段完整率 >= 85%
人工定稿时间下降 50%
同一公司重复研究可复用历史证据
字段修改不影响渲染层
新增字段不需要改核心 pipeline
15. 风险与约束
15.1 不要过早重写前端
当前最重要的是研究后端和数据库分层。
前端可以继续兼容旧表。
15.2 不要把所有字段都追求 confirmed
公开互联网无法稳定获得：
CAC
LTV
毛利率
31

--- Page 32 ---
Burn Rate
Runway
真实留存率
这些字段应接受：
unavailable
proxy
industry_avg
manual_needed
15.3 不要让卡片结构决定数据库
卡片页会变，数据库事实不应跟着变。
正确方式是：
数据库存事实
card_schema 决定如何展示
15.4 不要把 BettaFish 照搬过来
BettaFish 是舆情分析框架。
GZHv2 应借鉴：
多 Agent 分工
论坛式校验
公私域数据融合
模块化架构
不应照搬：
微博/小红书/抖音舆情爬虫
舆情情绪分析流程
大众评论处理逻辑
16. 最终形态
GZHv2 的最终架构应是：
32

--- Page 33 ---
研究台：
负责采集、证据、字段、分析、冲突处理
定稿台：
负责字段选择、文案压缩、状态确认、卡片组合
资产台：
负责 logo、截图、地图、竞品 logo、时间线、增长飞轮
渲染台：
负责 HTML / PNG / Markdown 输出
一句话目标：
把 GZHv2 从“能生成卡片的 LLM 工具”，升级成“字段可追溯、结果可复用、卡片可配置的 AI 初创公
司商业研究中台”。
33