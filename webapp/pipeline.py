"""研究流水线：4路并行采集 → 4层LLM分析 → 写库"""
from __future__ import annotations
import json, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from config import config
from deepseek_client import call_deepseek, load_prompt
from firecrawl_local import scrape_url
from field_rules import run_rule_layer
from field_validator import validate_enum_fields
import db as database

_REQUIRED_FIELDS = database.REQUIRED_RESEARCH_FIELDS

_SOURCE_LABELS = {
    "tavily": "Tavily 搜索",
    "github": "GitHub",
    "youtube": "YouTube",
    "website": "官网抓取",
}


def _report(progress_callback, stage: str, detail: str = "", job_id: str = None):
    if progress_callback:
        progress_callback(stage, detail)
    if job_id:
        try:
            import db as _db
            from config import config as _cfg
            _db.update_job(_cfg.DB_PATH_RESEARCH, job_id, stage=stage, detail=_detail_text(detail))
        except Exception:
            pass


def _detail_text(detail) -> str:
    if isinstance(detail, dict):
        return str(detail.get("message") or "")
    return str(detail or "")


# ── Step 1: 4路并行采集 ──────────────────────────

def _search_tavily(company_name: str):
    queries = [
        f"{company_name} AI startup overview funding founders",
        f"{company_name} company news competitors product",
    ]
    return [_search_tavily_query(q) for q in queries]


def _tavily_keys() -> list[str]:
    keys = getattr(config, "TAVILY_API_KEYS", None)
    if keys:
        return keys
    return [config.TAVILY_API_KEY] if config.TAVILY_API_KEY else []


def _is_tavily_quota_response(resp) -> bool:
    text = getattr(resp, "text", "") or ""
    return resp.status_code in (429, 432) or "usage limit" in text.lower() or "quota" in text.lower()


def _tavily_error_text(resp) -> str:
    try:
        data = resp.json()
        detail = data.get("detail") if isinstance(data, dict) else None
        if isinstance(detail, dict):
            return str(detail.get("error") or detail)
        if detail:
            return str(detail)
    except Exception:
        pass
    return f"HTTP {resp.status_code}"


def _tavily_proxy() -> dict | None:
    """读取 .env 中的代理配置，用于 requests 显式传参"""
    import os
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
    if proxy_url:
        return {"http": proxy_url, "https": proxy_url}
    return None


def _search_tavily_query(query: str, include_images: bool = False):
    keys = _tavily_keys()
    if not keys:
        return {"error": "TAVILY_API_KEYS not configured", "results": []}

    last_error = ""
    for index, api_key in enumerate(keys):
        try:
            body = {
                "api_key": api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": True,
                "include_raw_content": True,
                "max_results": 8,
            }
            if include_images:
                body["include_images"] = True
                body["max_results"] = 10
            resp = requests.post(
                "https://api.tavily.com/search",
                json=body,
                timeout=(30, 120),
                proxies=_tavily_proxy(),
            )
            if resp.status_code >= 400:
                last_error = _tavily_error_text(resp)
                if _is_tavily_quota_response(resp) and index < len(keys) - 1:
                    continue
                return {"error": last_error, "results": []}
            return resp.json()
        except Exception as e:
            last_error = str(e)
            # 超时也尝试下一个 key
            if index < len(keys) - 1:
                continue
    return {"error": last_error or "Tavily request failed", "results": []}


def _search_github(company_name: str):
    try:
        resp = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": f"{company_name} in:name", "sort": "stars", "per_page": 5},
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=(15, 45),
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
            timeout=(15, 45),
        )
        return resp.json() if resp.status_code == 200 else {"items": [], "error": resp.status_code}
    except Exception as e:
        return {"items": [], "error": str(e)}


def _scrape_website(company_url: str):
    for attempt in range(3):
        result = scrape_url(company_url, timeout=30)
        if not result.get("error"):
            return result
        if attempt < 2:
            time.sleep(3)
    return result


def _summarize_collection_source(name: str, data) -> dict:
    label = _SOURCE_LABELS.get(name, name)
    summary = {
        "label": label,
        "status": "empty",
        "count": 0,
        "unit": "条",
        "detail": "未获得有效信息",
    }

    if name == "tavily":
        items = data if isinstance(data, list) else []
        count = sum(len(item.get("results", [])) for item in items if isinstance(item, dict))
        errors = [str(item.get("error")) for item in items if isinstance(item, dict) and item.get("error")]
        summary.update({"count": count, "unit": "条结果"})
        if count > 0:
            detail = f"获得 {count} 条搜索结果"
            if errors:
                detail += f"，部分查询失败：{errors[0]}"
            summary.update({"status": "ok", "detail": detail})
        elif errors:
            summary.update({"status": "failed", "detail": errors[0]})
        return summary

    if name == "github":
        count = len(data.get("items", [])) if isinstance(data, dict) else 0
        error = data.get("error") if isinstance(data, dict) else None
        summary.update({"count": count, "unit": "个仓库"})
        if count > 0:
            summary.update({"status": "ok", "detail": f"找到 {count} 个相关仓库"})
        elif error:
            summary.update({"status": "failed", "detail": str(error)})
        return summary

    if name == "youtube":
        count = len(data.get("items", [])) if isinstance(data, dict) else 0
        note = data.get("note") if isinstance(data, dict) else None
        error = data.get("error") if isinstance(data, dict) else None
        summary.update({"count": count, "unit": "个视频"})
        if count > 0:
            summary.update({"status": "ok", "detail": f"找到 {count} 个相关视频"})
        elif note:
            summary.update({"status": "skipped", "detail": str(note)})
        elif error:
            summary.update({"status": "failed", "detail": str(error)})
        return summary

    if name == "website":
        text = ""
        if isinstance(data, dict):
            text = data.get("text") or data.get("markdown") or data.get("content") or ""
        count = len(str(text).strip())
        error = data.get("error") if isinstance(data, dict) else None
        summary.update({"count": count, "unit": "字符"})
        if count > 0:
            summary.update({"status": "ok", "detail": f"抓取 {count} 个正文字符"})
        elif error:
            summary.update({"status": "failed", "detail": str(error)})
        return summary

    return summary


def _collect_all(company_name: str, company_url: str, progress_callback=None, job_id: str = None) -> dict:
    """4路并行采集"""
    source_summary = {}
    _report(
        progress_callback,
        "采集",
        {"message": "4路并行采集中...", "sources": source_summary},
        job_id=job_id,
    )
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
            source_summary[name] = _summarize_collection_source(name, raw[name])
            _report(
                progress_callback,
                "采集",
                {
                    "message": f"{source_summary[name]['label']}完成：{source_summary[name]['detail']}",
                    "sources": dict(source_summary),
                },
                job_id=job_id,
            )
    raw["_source_summary"] = source_summary
    return raw


# ── Step 2: AI 分析 ──────────────────────────────

def _load_prompt_text(name: str) -> str:
    return load_prompt(name)


# ══ 三层枚举提取（规则层 → LLM 三组 → 验证）══════════════════

ENUM_GROUP_PROMPTS = {
    "A": ("layer3-group-a-technical", ["ai_model_dependency", "data_flywheel", "proprietary_data_asset"]),
    "B": ("layer3-group-b-competitive", ["incumbent_direct_competitor", "workflow_integration_level", "inference_cost_exposure"]),
    "C": ("layer3-group-c-business", ["pricing_model", "customer_segment_type", "stack_layer"]),
}

KEY_ENUM_FIELDS = ["ai_model_dependency", "incumbent_direct_competitor", "pricing_model"]


def _run_llm_enum_group(api_key: str, group_name: str, context: str,
                        rule_hits: dict | None = None,
                        temperature: float = 0.1) -> dict:
    """调用单组 LLM 提取枚举字段。返回 {field: value} dict。"""
    prompt_file, field_names = ENUM_GROUP_PROMPTS[group_name]
    prompt = _load_prompt_text(prompt_file)

    # 组 C 需要注入规则层提示
    if group_name == "C" and rule_hits:
        hint_lines = [f"- {k} = \"{v}\"（规则层已确定，跳过）" for k, v in rule_hits.items()]
        prompt = prompt.replace("{rule_fields_hint}", "\n".join(hint_lines))
    elif group_name == "C":
        prompt = prompt.replace("{rule_fields_hint}", "（无）")

    result = call_deepseek(
        api_key, prompt, context,
        temperature=temperature, max_tokens=200, timeout=60,
    )
    parsed = _extract_json(result)
    # 只保留本组字段
    return {k: v for k, v in parsed.items() if k in field_names and v}


def _extract_enum_fields(api_key: str, l0_result: str, l1_result: str, l2_result: str,
                         company_url: str, company_type: str = "",
                         progress_callback=None, job_id: str = None) -> dict:
    """三层枚举提取：规则层 → LLM 组A+B→组C → 验证 → 合并。
    返回 {field: value} dict，覆盖原 L3 的枚举字段。"""
    context = json.dumps(
        {"layer0": l0_result, "layer1": l1_result, "layer2": l2_result},
        ensure_ascii=False, indent=2,
    )

    # 层1：规则层
    _report(progress_callback, "枚举-规则", "规则层提取...", job_id=job_id)
    rule_hits = run_rule_layer(company_url, company_type)
    _report(progress_callback, "枚举-规则",
            f"命中 {len(rule_hits)} 字段: {list(rule_hits.keys())}", job_id=job_id)

    # 层2：LLM 组 A + B 并行
    _report(progress_callback, "枚举-LLM", "组A+B并行提取...", job_id=job_id)
    group_a = {}
    group_b = {}
    with ThreadPoolExecutor(max_workers=2) as ex:
        fa = ex.submit(_run_llm_enum_group, api_key, "A", context)
        fb = ex.submit(_run_llm_enum_group, api_key, "B", context)
        group_a = fa.result() or {}
        group_b = fb.result() or {}

    # 层2：LLM 组 C（传规则层结果，跳过已有字段）
    _report(progress_callback, "枚举-LLM", "组C提取...", job_id=job_id)
    group_c = _run_llm_enum_group(api_key, "C", context, rule_hits) or {}

    # 合并三组
    merged = {}
    merged.update(group_a)
    merged.update(group_b)
    merged.update(group_c)
    # 规则层覆盖（优先级最高）
    merged.update(rule_hits)

    _report(progress_callback, "枚举-LLM",
            f"合并 {len(merged)} 字段: {list(merged.keys())}", job_id=job_id)

    # 关键字段多数投票（2 round，不一致时加第3 round）
    for field in KEY_ENUM_FIELDS:
        if field in merged:
            v1 = merged[field]
            _report(progress_callback, "枚举-投票", f"{field} round 2...", job_id=job_id)
            r2 = _run_llm_enum_group(api_key, _group_for_field(field), context,
                                     rule_hits if _group_for_field(field) == "C" else None,
                                     temperature=0.2)
            v2 = r2.get(field) if r2 else None
            if v2 and v2 != v1:
                _report(progress_callback, "枚举-投票",
                        f"{field} 不一致({v1} vs {v2}), round 3...", job_id=job_id)
                r3 = _run_llm_enum_group(api_key, _group_for_field(field), context,
                                         rule_hits if _group_for_field(field) == "C" else None,
                                         temperature=0.25)
                v3 = r3.get(field) if r3 else None
                # 取众数
                votes = [v1, v2]
                if v3: votes.append(v3)
                merged[field] = max(set(votes), key=votes.count)
                _report(progress_callback, "枚举-投票",
                        f"{field} → {merged[field]} (投票: {votes})", job_id=job_id)
            else:
                _report(progress_callback, "枚举-投票",
                        f"{field} 一致 ({v1})", job_id=job_id)

    # 层3：Pydantic 验证
    _report(progress_callback, "枚举-验证", "Pydantic 验证...", job_id=job_id)
    try:
        validated = validate_enum_fields(merged)
        _report(progress_callback, "枚举-验证",
                f"通过 {len(validated)}/{len(merged)} 字段", job_id=job_id)
        return validated
    except ValueError as e:
        _report(progress_callback, "枚举-验证",
                f"验证失败: {e}，退回未验证结果", job_id=job_id)
        return merged


def _group_for_field(field: str) -> str:
    for g, (_, fields) in ENUM_GROUP_PROMPTS.items():
        if field in fields:
            return g
    return "A"


def llm_analysis(company_name: str, company_url: str, raw_data: dict,
                 progress_callback=None, job_id: str = None) -> list[dict]:
    """4层 Prompt 分析，返回 3 版本记录列表"""
    api_key = config.DEEPSEEK_API_KEY

    # Layer 0
    _report(progress_callback, "L0清洗", "信息清洗中...", job_id=job_id)
    l0_prompt = _load_prompt_text("layer0-cleaner")
    l0_result = call_deepseek(
        api_key, l0_prompt,
        json.dumps(raw_data, ensure_ascii=False, indent=2),
        temperature=0.1, max_tokens=4096, timeout=120,
    )

    # Layer 1
    _report(progress_callback, "L1横纵分析", "横纵分析中...", job_id=job_id)
    l1_prompt = _load_prompt_text("layer1-hv-analysis")
    l1_result = call_deepseek(
        api_key, l1_prompt, l0_result,
        temperature=0.3, max_tokens=4096, timeout=120,
    )

    # Layer 2
    _report(progress_callback, "L2商业结构", "商业结构分析中...", job_id=job_id)
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
        _report(progress_callback, f"L3-{ver_name}", f"提取 {ver_name} 版...", job_id=job_id)
        prompt = l3_prompt_template
        for placeholder, value in [("{{VERSION}}", ver_name),
                                    ("{{VERSION_INSTRUCTIONS}}", ver_inst),
                                    ("{{VERSION_SPECIFIC}}", ver_inst)]:
            prompt = prompt.replace(placeholder, value)

        parsed = None
        for attempt in range(2):
            try:
                l3_result = call_deepseek(
                    api_key, prompt, all_context,
                    temperature=0.15, max_tokens=16384, timeout=120,
                )
                parsed = _extract_json(l3_result)
                break
            except ValueError as e:
                if attempt == 0:
                    _report(progress_callback, f"L3-{ver_name}", f"JSON修复失败，重试...", job_id=job_id)
                    retry_msg = f"上一次输出 JSON 无法解析：{e}\n请确保输出合法 JSON（检查逗号、引号、转义）。"
                    prompt = prompt + "\n\n" + retry_msg
                else:
                    all_records.append({"company_name": company_name, "version": ver_name, "_error": str(e)})
                    break

        if parsed is not None:
            # ── 三层枚举提取覆盖 ──
            try:
                enum_fields = _extract_enum_fields(
                    api_key, l0_result, l1_result, l2_result,
                    company_url, parsed.get("company_type", ""),
                    progress_callback, job_id,
                )
                parsed.update(enum_fields)
            except Exception as e:
                _report(progress_callback, f"L3-{ver_name}",
                        f"枚举提取异常: {e}", job_id=job_id)

            missing_founder_fields = _missing_founder_fields(parsed)
            if missing_founder_fields and _has_founder_detail_signal(l0_result):
                _report(
                    progress_callback,
                    f"L3-{ver_name}",
                    f"创始人字段缺失，重试 {', '.join(missing_founder_fields)}...",
                    job_id=job_id,
                )
                retry_prompt = _founder_retry_prompt(prompt, missing_founder_fields)
                try:
                    retry_result = call_deepseek(
                        api_key, retry_prompt, all_context,
                        temperature=0.1, max_tokens=16384, timeout=120,
                    )
                    retry_parsed = _extract_json(retry_result)
                    parsed = _merge_founder_retry(parsed, retry_parsed, missing_founder_fields)
                except ValueError:
                    pass
            parsed["company_name"] = company_name
            parsed["version"] = ver_name
            all_records.append(parsed)

    return all_records


def _extract_json(text: str) -> dict:
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text, flags=re.IGNORECASE)
    if match:
        text = match.group(1)
    clean = text.strip()

    # 尝试直接解析
    try:
        if clean.startswith('{'):
            return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # LLM 偶尔会在 JSON 前后加解释文字；截取第一个完整对象再解析。
    json_obj = _find_json_object(clean)
    if json_obj:
        try:
            return json.loads(json_obj)
        except json.JSONDecodeError:
            text = json_obj

    # 用 json_repair 自动修复常见语法错误
    try:
        from json_repair import repair_json
        return json.loads(repair_json(text))
    except ImportError:
        pass

    raise ValueError(f"Cannot parse JSON from: {text[:200]}...")


def _is_missing_value(value) -> bool:
    return str(value or "").strip() in ("", "暂缺", "unknown", "Unknown", "N/A", "n/a")


def _missing_founder_fields(record: dict) -> list[str]:
    fields = ["founder_edu", "founder_achievement"]
    return [field for field in fields if _is_missing_value(record.get(field))]


def _has_founder_detail_signal(text: str) -> bool:
    lowered = str(text or "").lower()
    keywords = [
        "founder", "founded", "university", "college", "school", "degree",
        "phd", "mit", "stanford", "harvard", "berkeley", "alumni",
        "创始", "大学", "学院", "学位", "博士", "硕士", "本科",
        "毕业", "获奖", "奖项", "创业", "前公司", "曾任",
    ]
    return any(keyword in lowered for keyword in keywords)


def _founder_retry_prompt(prompt: str, missing_fields: list[str]) -> str:
    fields = ", ".join(missing_fields)
    return prompt + f"""

上一轮输出遗漏了以下创始人字段：{fields}。
请重新输出完整 JSON，保持原有字段结构不变，并优先从 Layer 0 的创始人信息中提取：
- founder_edu：只写学校、专业、学位等教育信息，不要混入工作履历。
- founder_achievement：只写获奖、创业经历、前公司重要成果等，不要与教育信息混淆。
如果 Layer 0 已有相关线索，不允许填“暂缺”。
"""


def _merge_founder_retry(original: dict, retry: dict, missing_fields: list[str]) -> dict:
    merged = dict(original)
    for field in missing_fields:
        value = retry.get(field)
        if not _is_missing_value(value):
            merged[field] = value
    for key, value in retry.items():
        if key not in merged or _is_missing_value(merged.get(key)):
            merged[key] = value
    return merged


def _find_json_object(text: str) -> str | None:
    start = text.find('{')
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


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
                 progress_callback=None, job_id: str = None) -> list[int]:
    """执行完整研究流水线，返回插入的记录 ID 列表"""
    t0 = time.time()

    # Step 1: 采集
    raw = _collect_all(company_name, company_url, progress_callback, job_id=job_id)
    t1 = time.time()
    _report(
        progress_callback,
        "采集完成",
        {
            "message": f"4路采集完成（{t1 - t0:.1f}s）",
            "sources": raw.get("_source_summary", {}),
        },
        job_id=job_id,
    )

    # Step 2: AI 分析
    _report(progress_callback, "分析", "开始 4 层 LLM 分析...", job_id=job_id)
    records = llm_analysis(company_name, company_url, raw, progress_callback, job_id=job_id)
    errors = [r for r in records if r.get("_error")]
    if errors:
        details = ", ".join(f"{r.get('version', '?')}: {r.get('_error')}" for r in errors)
        raise RuntimeError(f"L3 字段提取失败: {details}")
    records = _validate_records(records)

    t2 = time.time()
    _report(progress_callback, "分析完成", f"({t2 - t1:.1f}s)", job_id=job_id)

    # Step 3: 写库
    _report(progress_callback, "写库", "写入数据库...", job_id=job_id)
    ids = database.save_research_records(config.DB_PATH_RESEARCH, records)

    # Step 3.5: 写入字段级表（解耦架构 — 字段不天然属于任何卡片）
    from services.field_service import split_research_to_fields
    from repositories.field_repo import insert_research_fields_batch
    for record in records:
        version = record.get('version', 'standard')
        field_record = {**record, "company_name": company_name}
        field_rows = split_research_to_fields(field_record, version)
        if field_rows:
            insert_research_fields_batch(config.DB_PATH_RESEARCH, field_rows)

    t3 = time.time()

    # Step 4: 图片采集
    standard_record = records[0] if records else {}
    company_data = {
        "company_name": company_name,
        "company_url": company_url,
        "website_url": company_url,
        "location": standard_record.get("location", ""),
        "other_products": standard_record.get("other_products", ""),
        "competitors": standard_record.get("competitors", ""),
        "main_product_name": standard_record.get("main_product_name", ""),
        "main_product_img_src": standard_record.get("main_product_img_src", ""),
        "office_photo_hints": standard_record.get("office_photo_hints", ""),
    }
    try:
        from asset_pipeline import collect_image_variants_pipeline
        image_results = collect_image_variants_pipeline(
            config.DB_PATH_ASSETS, config.IMAGES_DIR, company_name, company_data,
            progress_callback=progress_callback, job_id=job_id,
        )
    except Exception as e:
        _report(progress_callback, "图片采集",
                {"message": f"图片采集异常：{e}", "card": 0, "total": 4},
                job_id=job_id)
        image_results = {}

    total_images = sum(image_results.values())
    _report(progress_callback, "图片采集完成",
            {"message": f"共 {total_images} 张候选图"},
            job_id=job_id)

    t4 = time.time()
    _report(progress_callback, "完成", f"总耗时 {t4 - t0:.1f}s, IDs: {ids}", job_id=job_id)
    return ids
