"""Dataset harus terisolasi dan gagal aman sebelum memanggil provider."""

import json
from pathlib import Path

import pytest

from evals.schema import case_fingerprint, dataset_fingerprint, load_cases

SEED = Path("evals/data/synthesis_seed.jsonl")


def test_seed_and_fingerprints():
    cases = load_cases(SEED)
    assert {s: sum(c.split == s for c in cases) for s in ("train", "validation", "test")} == {
        "train": 6,
        "validation": 6,
        "test": 6,
    }
    changed = cases[0].model_copy(deep=True)
    changed.evidence[0].text += " tambahan"
    assert case_fingerprint(changed) != case_fingerprint(cases[0])
    assert dataset_fingerprint([changed, *cases[1:]]) != dataset_fingerprint(cases)


@pytest.mark.parametrize(
    "mutation", ["extra", "duplicate", "leak", "blank", "gold", "url", "timestamp"]
)
def test_invalid_dataset(tmp_path, mutation):
    rows = [c.model_dump(mode="json") for c in load_cases(SEED)]
    if mutation == "extra":
        rows[0]["unknown"] = True
    elif mutation == "duplicate":
        rows[1]["case_id"] = rows[0]["case_id"]
    elif mutation == "leak":
        rows[6] = {**rows[0], "case_id": "different", "split": "validation"}
    elif mutation == "blank":
        rows[0]["evidence"][0]["text"] = " "
    elif mutation == "gold":
        rows[0]["required_claims"][0]["source_ids"] = [99]
    elif mutation == "url":
        rows[0]["evidence"][0]["url"] = "https://user:secret@example.com/"
    else:
        rows[0]["evidence"][0]["fetched_at"] = "2026-03-10"
    path = tmp_path / "bad.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows))
    with pytest.raises(ValueError) as error:
        load_cases(path)
    assert str(path) in str(error.value)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("text", ["", "not json", "{}"])
def test_empty_or_malformed(tmp_path, text):
    path = tmp_path / "bad.jsonl"
    path.write_text(text)
    with pytest.raises(ValueError):
        load_cases(path)


def test_settings_require_explicit_eval_environment(monkeypatch):
    from evals.schema import EvaluationSettings

    values = {
        "EVAL_TEMPERATURE": "0",
        "EVAL_LLM_MAX_RETRIES": "0",
        "EVAL_MAX_LM_CALLS": "24",
        "EVAL_GEPA_METRIC_CALLS": "3",
        "EVAL_SEED": "17",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    assert EvaluationSettings.from_env().max_lm_calls == 24
    monkeypatch.setenv("EVAL_LLM_MAX_RETRIES", "1")
    with pytest.raises(ValueError):
        EvaluationSettings.from_env()
    monkeypatch.delenv("EVAL_MAX_LM_CALLS")
    with pytest.raises(ValueError):
        EvaluationSettings.from_env()
