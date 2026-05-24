"""研究流水线：4路并行采集 → 4层LLM分析 → 写库"""
from __future__ import annotations
import json, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from config import config
from deepseek_client import call_deepseek, load_prompt
from firecrawl_local import scrape_url
import db as database

_REQUIRED_FIELDS = database.REQUIRED_RESEARCH_FIELDS


def _report(progress_callback, stage: str, detail: str = ""):
    if progress_callback:
        progress_callback(stage, detail)


# ── Step 1: 4路并行采集 ──────────────────────────

def _search_tavily(company_name: str):
    queries = [
        f"{company_name} AI startup overview funding founders",
        f"{company_name} company news competitors product",
    ]
    results = []
    for q in queries:
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": config.TAVILY_API_KEY,
                    "query": q,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_raw_content": True,
                    "max_results": 8,
                },
                timeout=(10, 60),
            )
            resp.raise_for_status()
            results.append(resp.json())
        except Exception as e:
            results.append({"error": str(e), "results": []})
    return results


def _search_github(company_name: str):
    try:
        resp = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": f"{company_name} in:name", "sort": "stars", "per_page": 5},
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=(5, 25),
        )
        if resp.status_code == 200:
            return resp.json()
        return {"error": resp.status_code, "items": []}
    except Exception as e:
        return {"error": str(e), "items": []}


def _search_youtube(company_name: str):
    if not config.YOUTUBE_API_KEY:
        return {"items": [], "note": "no API key"}
    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": f"{company_name} founder interview",
                "type": "video",
                "maxResults": 3,
                "key": config.YOUTUBE_API_KEY,
            },
            timeout=(5, 25),
        )
        return resp.json() if resp.status_code == 200 else {"items": [], "error": resp.status_code}
    except Exception as e:
        return {"items": [], "error": str(e)}


def _scrape_website(company_url: str):
    result = scrape_url(company_url, timeout=30)
    return result


def _collect_all(company_name: str, company_url: str, progress_callback=None) -> dict:
    """4路并行采集"""
    _report(progress_callback, "采集", "4路并行采集中...")
    tasks = {
        "tavily": lambda: _search_tavily(company_name),
        "github": lambda: _search_github(company_name),
        "youtube": lambda: _search_youtube(company_name),
        "website": lambda: _scrape_website(company_url),
    }

    raw = {"company_name": company_name, "company_url": company_url}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                raw[name] = future.result()
            except Exception as e:
                raw[name] = {"error": str(e)}
            _report(progress_callback, "采集", f"  {name} 完成")
    return raw


# ── Step 2: AI 分析 ──────────────────────────────

def _load_prompt_text(name: str) -> str:
    return load_prompt(name)


def llm_analysis(company_name: str, company_url: str, raw_data: dict,
                 progress_callback=None) -> list[dict]:
    """4层 Prompt 分析，返回 3 版本记录列表"""
    api_key = config.DEEPSEEK_API_KEY

    # Layer 0
    _report(progress_callback, "L0清洗", "信息清洗中...")
    l0_prompt = _load_prompt_text("layer0-cleaner")
    l0_result = call_deepseek(
        api_key, l0_prompt,
        json.dumps(raw_data, ensure_ascii=False, indent=2),
        temperature=0.1, max_tokens=4096, timeout=120,
    )

    # Layer 1
    _report(progress_callback, "L1横纵分析", "横纵分析中...")
    l1_prompt = _load_prompt_text("layer1-hv-analysis")
    l1_result = call_deepseek(
        api_key, l1_prompt, l0_result,
        temperature=0.3, max_tokens=4096, timeout=120,
    )

    # Layer 2
    _report(progress_callback, "L2商业结构", "商业结构分析中...")
    l2_prompt = _load_prompt_text("layer2-business")
    l2_context = json.dumps({"layer0": l0_result, "layer1": l1_result}, ensure_ascii=False, indent=2)
    l2_result = call_deepseek(
        api_key, l2_prompt, l2_context,
        temperature=0.2, max_tokens=4096, timeout=120,
    )

    # Layer 3 — 3 版本
    l3_prompt_template = _load_prompt_text("layer3-field-extraction")
    all_context = json.dumps(
        {"layer0": l0_result, "layer1": l1_result, "layer2": l2_result},
        ensure_ascii=False, indent=2,
    )

    versions = [
        ("standard", "标准版：客观完整，数据优先，适合事实核查。用词严谨，多引用具体数据。要求：语气客观中立，强调数据可靠性和来源可验证性。"),
        ("business", "商业版：强调价值判断，投资人/同行视角。突出商业潜力和竞争分析。要求：语气专业但有判断力，关注估值空间、市场空间、竞争壁垒。"),
        ("spread", "传播版：高钩子密度，语言有张力，自媒体友好。要求：开头要有强钩子，用数据制造冲击感。金句化表达关键洞察。适合大众传播。"),
    ]

    all_records = []
    for ver_name, ver_inst in versions:
        _report(progress_callback, f"L3-{ver_name}", f"提取 {ver_name} 版...")
        prompt = l3_prompt_template
        for placeholder, value in [("{{VERSION}}", ver_name),
                                    ("{{VERSION_INSTRUCTIONS}}", ver_inst),
                                    ("{{VERSION_SPECIFIC}}", ver_inst)]:
            prompt = prompt.replace(placeholder, value)

        try:
            l3_result = call_deepseek(
                api_key, prompt, all_context,
                temperature=0.15, max_tokens=8192, timeout=120,
            )
            parsed = _extract_json(l3_result)
            parsed["company_name"] = company_name
            parsed["version"] = ver_name
            all_records.append(parsed)
        except Exception as e:
            all_records.append({"company_name": company_name, "version": ver_name, "_error": str(e)})

    return all_records


def _extract_json(text: str) -> dict:
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return json.loads(match.group(1))
    clean = text.strip()
    if clean.startswith('{'):
        return json.loads(clean)
    raise ValueError(f"Cannot parse JSON from: {text[:200]}...")


def _validate_records(records: list[dict]) -> list[dict]:
    """填充暂缺字段"""
    for rec in records:
        for f in _REQUIRED_FIELDS:
            val = rec.get(f)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                rec[f] = "暂缺"
    return records


# ── 主入口 ─────────────────────────────────────

def run_pipeline(company_name: str, company_url: str,
                 progress_callback=None) -> list[int]:
    """执行完整研究流水线，返回插入的记录 ID 列表"""
    t0 = time.time()

    # Step 1: 采集
    raw = _collect_all(company_name, company_url, progress_callback)
    t1 = time.time()
    _report(progress_callback, "采集完成", f"({t1 - t0:.1f}s)")

    # Step 2: AI 分析
    _report(progress_callback, "分析", "开始 4 层 LLM 分析...")
    records = llm_analysis(company_name, company_url, raw, progress_callback)
    errors = [r for r in records if r.get("_error")]
    if errors:
        details = ", ".join(f"{r.get('version', '?')}: {r.get('_error')}" for r in errors)
        raise RuntimeError(f"L3 字段提取失败: {details}")
    records = _validate_records(records)
    t2 = time.time()
    _report(progress_callback, "分析完成", f"({t2 - t1:.1f}s)")

    # Step 3: 写库
    _report(progress_callback, "写库", "写入数据库...")
    ids = database.save_research_records(config.DB_PATH_RESEARCH, records)
    t3 = time.time()
    _report(progress_callback, "完成", f"总耗时 {t3 - t0:.1f}s, IDs: {ids}")
    return ids
