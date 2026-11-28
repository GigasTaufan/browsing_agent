"""Respons keputusan riset deterministik untuk tes kontrak sintesis/API."""

import json


def research_decision(payload: dict, required_sources: int = 1) -> str | None:
    try:
        request = json.loads(payload["messages"][0]["content"])
    except json.JSONDecodeError:
        return None
    task = request.get("task")
    data = request.get("input", {})
    if task == "research_plan":
        result = {"goal": data["question"], "constraints": "", "queries": [data["question"]]}
    elif task == "research_select":
        result = {"candidate_ids": [item["id"] for item in data["candidates"]]}
    elif task == "research_review":
        ids = [item["id"] for item in data["evidence"]]
        result = {
            "relevant_ids": ids,
            "sufficient": len(ids) >= required_sources,
            "missing_information": "",
            "next_queries": [],
        }
    else:
        return None
    return json.dumps(result)
