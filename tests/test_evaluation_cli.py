"""Kontrak CLI evaluator offline tanpa kredensial maupun jaringan pada pytest."""

import builtins
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.runner import main

SEED = Path("evals/data/synthesis_seed.jsonl")


def test_validate_without_application_imports(monkeypatch, capsys):
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name in ("main", "config", "dspy") or name.startswith("agent."):
            raise AssertionError(name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    assert main(["validate", "--dataset", str(SEED)]) == 0
    assert capsys.readouterr().out.strip() == (
        "Dataset valid: 18 kasus (train=6, validation=6, test=6)."
    )


def _settings(monkeypatch, limit=80):
    for key, value in {
        "EVAL_TEMPERATURE": "0",
        "EVAL_LLM_MAX_RETRIES": "0",
        "EVAL_MAX_LM_CALLS": str(limit),
        "EVAL_GEPA_METRIC_CALLS": str(min(3, limit)),
        "EVAL_SEED": "17",
    }.items():
        monkeypatch.setenv(key, value)


def test_existing_output_rejected_before_clients(tmp_path, monkeypatch):
    _settings(monkeypatch)
    import evals.runner as runner

    monkeypatch.setattr(runner, "build_clients", lambda *_: pytest.fail("provider dibangun"))
    assert main(["run", "--dataset", str(SEED), "--output", str(tmp_path)]) == 2


@pytest.mark.parametrize(
    "limit,expected,compile_failure",
    [
        (80, "complete", None),
        (2, "budget_exhausted", None),
        (80, "failed", "provider"),
        (80, "failed", "auth"),
        (80, "complete", "parse"),
        (80, "failed", "judge"),
    ],
)
def test_actual_optimizer_reports_and_budget(
    tmp_path, monkeypatch, capsys, limit, expected, compile_failure
):
    dspy = pytest.importorskip("dspy")
    from dspy.lm15 import Message, Response, Usage
    from dspy.utils.exceptions import LMAuthError, LMProviderError

    import evals.runner as runner
    from evals.dspy_synthesis import BudgetedLM

    _settings(monkeypatch, limit)
    calls = []
    stages = []
    phase = {"compiling": False, "injected": False}
    original_compile = dspy.GEPA.compile

    def compile_program(self, *args, **kwargs):
        phase["compiling"] = True
        try:
            return original_compile(self, *args, **kwargs)
        finally:
            phase["compiling"] = False

    monkeypatch.setattr(dspy.GEPA, "compile", compile_program)

    class Engine:
        def __init__(self, role):
            self.role = role

        def complete(self, request):
            text = (
                str(request.system or "")
                + "\n"
                + "\n".join(message.text or "" for message in request.messages)
            )
            calls.append((self.role, text))
            failing_role = "judge" if compile_failure == "judge" else "synthesis"
            fail_now = (
                self.role == failing_role
                and phase["compiling"]
                and not phase["injected"]
                and compile_failure is not None
            )
            if fail_now:
                phase["injected"] = True
                if compile_failure in ("provider", "auth"):
                    error_type = LMAuthError if compile_failure == "auth" else LMProviderError
                    raise error_type("Authorization: COMPILE_SECRET")
            if fail_now and compile_failure == "parse":
                output = "Jawaban tidak mengikuti format adapter."
            elif fail_now and compile_failure == "judge":
                output = json.dumps(
                    dict(
                        covered_claims=[True],
                        supported_claims=[True, True],
                        unsupported_claims=[],
                        forbidden_present=[False, False],
                        behavior_matches=True,
                        feedback="PRIVATE_COMPILE_JUDGE_PAYLOAD",
                    )
                )
            elif self.role == "reflection":
                output = (
                    "[[ ## new_instruction ## ]]\n"
                    "KAPASITAS_BENAR: Susun fakta dengan referensi.\n"
                    "[[ ## completed ## ]]"
                )
            elif self.role == "judge":
                output = json.dumps(
                    dict(
                        covered_claims=[True, True],
                        supported_claims=[True, True],
                        unsupported_claims=[]
                        if "kapasitas benar" in text.lower()
                        else ["Kapasitas salah"],
                        forbidden_present=[False, False],
                        behavior_matches=True,
                        feedback="Perbaiki kapasitas sesuai sumber.",
                    )
                )
            else:
                correct = "KAPASITAS_BENAR" in text
                output = (
                    "[[ ## answer ## ]]\n"
                    + ("Kapasitas benar" if correct else "Kapasitas salah")
                    + " [1].\n[[ ## completed ## ]]"
                )
            return Response(
                id=None,
                model=request.model,
                message=Message.assistant(output),
                finish_reason="stop",
                usage=Usage(),
            )

    class Baseline:
        def invoke(self, payload):
            return {"messages": [SimpleNamespace(type="ai", content="Kapasitas benar [1].")]}

    def clients(_settings, budget):
        lms = {
            role: BudgetedLM(
                "openai/test",
                role=role,
                budget=budget,
                engine=Engine(role),
                cache=False,
                num_retries=0,
            )
            for role in ("synthesis", "judge", "reflection")
        }
        return runner.Clients(
            lambda _: Baseline(),
            lms["synthesis"],
            lms["judge"],
            lms["reflection"],
            {"provider": "test", "model": "test"},
        )

    monkeypatch.setattr(runner, "build_clients", clients)
    original_reload = runner.reload_program

    def reload(*args):
        assert not any("Elang" in text or "Fajar" in text for _, text in calls)
        stages.append("reload")
        return original_reload(*args)

    monkeypatch.setattr(runner, "reload_program", reload)
    output = tmp_path / "run"
    code = main(["run", "--dataset", str(SEED), "--output", str(output), "--smoke"])
    summary = json.loads((output / "summary.json").read_text())
    assert summary["status"] == expected
    assert summary["calls"]["total"] <= limit
    assert code == (0 if expected == "complete" else 1)
    if compile_failure is not None:
        assert phase["injected"]
    if compile_failure in ("provider", "auth"):
        assert summary["error_code"] == (
            "auth_error" if compile_failure == "auth" else "provider_error"
        )
        assert not (output / "program.json").exists()
        assert stages == []
        assert "COMPILE_SECRET" not in "".join(path.read_text() for path in output.iterdir())
    if compile_failure == "judge":
        assert summary["error_code"] == "scoring_error"
        assert not (output / "program.json").exists()
        failure = json.loads((output / "scoring_failure.json").read_text())
        assert failure["case_id"] == "train-single_source"
        assert "PRIVATE_COMPILE_JUDGE_PAYLOAD" not in "".join(
            path.read_text() for path in output.iterdir()
        )
    if code == 0:
        assert stages == ["reload"]
        rows = [json.loads(line) for line in (output / "results.jsonl").read_text().splitlines()]
        test_rows = [row for row in rows if row["phase"] == "test_after"]
        assert len(test_rows) == 3
        assert next(row for row in test_rows if row["backend"] == "dspy_optimized")["score"] == 1
        assert "KAPASITAS_BENAR" in (output / "program.json").read_text()
        assert summary["verdict"] == "inconclusive"
    assert "Kapasitas salah" not in capsys.readouterr().out


def test_provider_error_sanitized(tmp_path, monkeypatch, capsys):
    pytest.importorskip("dspy")
    import evals.runner as runner

    _settings(monkeypatch)

    def failed(*_):
        raise RuntimeError("Authorization: SUPERSECRET")

    monkeypatch.setattr(runner, "build_clients", failed)
    output = tmp_path / "failed"
    assert main(["run", "--dataset", str(SEED), "--output", str(output)]) == 1
    assert "SUPERSECRET" not in (output / "summary.json").read_text() + capsys.readouterr().out


def test_symlink_and_protected_output_rejected(tmp_path, monkeypatch):
    _settings(monkeypatch)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "absent")
    assert main(["run", "--dataset", str(SEED), "--output", str(link)]) == 2
    assert main(["run", "--dataset", str(SEED), "--output", "evals/data/report"]) == 2


def test_missing_rows_and_unknown_tokens_counted():
    pytest.importorskip("dspy")
    from evals.dspy_synthesis import CallBudget
    from evals.runner import _summary
    from evals.schema import load_cases

    budget = CallBudget(2)
    budget.reserve("baseline")
    budget.record("baseline", 0.1)
    summary = _summary("failed", [], load_cases(SEED), budget, False, True)
    assert summary["backends"]["baseline"]["mean_score"] == 0
    assert summary["backends"]["baseline"]["error_or_missing"] == 6
    assert summary["tokens"]["input_tokens"]["unknown"] == 1
    assert summary["verdict"] == "inconclusive"


def test_artifact_tampering_fails_safe(tmp_path):
    pytest.importorskip("dspy")
    from evals.runner import ArtifactMismatch, _versions, reload_program

    manifest = dict(
        program_sha256="wrong",
        versions=_versions(),
        dataset_sha256="dataset",
        split_fingerprints={},
    )
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "program.json").write_text("{}")
    with pytest.raises(ArtifactMismatch):
        reload_program(tmp_path, manifest, None)


def test_validation_error_identifies_record_without_payload(tmp_path, capsys):
    from evals.schema import load_cases

    row = load_cases(SEED)[0].model_dump(mode="json")
    row["evidence"][0]["url"] = "https://user:PRIVATE_SECRET@example.com/"
    path = tmp_path / "invalid.jsonl"
    path.write_text(json.dumps(row))
    assert main(["validate", "--dataset", str(path)]) == 2
    message = capsys.readouterr().err
    assert str(path) in message and "baris 1" in message and row["case_id"] in message
    assert "evidence.0.url" in message and "PRIVATE_SECRET" not in message


def test_judge_schema_failure_reports_safe_reason(tmp_path, monkeypatch):
    pytest.importorskip("dspy")
    from dspy.lm15 import Message, Response, Usage

    import evals.runner as runner
    from evals.dspy_synthesis import BudgetedLM

    _settings(monkeypatch)

    class Engine:
        def complete(self, request):
            output = json.dumps(
                dict(
                    covered_claims=[True, True],
                    supported_claims=[True, True],
                    forbidden_present=[False, False],
                    behavior_matches=True,
                    feedback="PRIVATE_PROVIDER_PAYLOAD",
                )
            )
            return Response(
                id=None,
                model=request.model,
                message=Message.assistant(output),
                finish_reason="stop",
                usage=Usage(),
            )

    class Baseline:
        def invoke(self, payload):
            return {"messages": [SimpleNamespace(type="ai", content="Fakta [1].")]}

    def clients(_settings, budget):
        lms = [
            BudgetedLM("openai/test", budget=budget, role=role, engine=Engine())
            for role in ("synthesis", "judge", "reflection")
        ]
        return runner.Clients(lambda _: Baseline(), *lms, {"provider": "test", "model": "test"})

    monkeypatch.setattr(runner, "build_clients", clients)
    output = tmp_path / "run"
    assert main(["run", "--dataset", str(SEED), "--output", str(output), "--smoke"]) == 1
    rows = [json.loads(line) for line in (output / "results.jsonl").read_text().splitlines()]
    assert rows[0]["error_code"] == "scoring_error"
    assert rows[0]["feedback"] == "Penilaian judge gagal: judge_parse_error"
    assert "PRIVATE_PROVIDER_PAYLOAD" not in "".join(path.read_text() for path in output.iterdir())


def test_run_skips_model_for_no_evidence_cases(tmp_path, monkeypatch):
    pytest.importorskip("dspy")
    from dspy.lm15 import Message, Response, Usage

    import evals.runner as runner
    from evals.dspy_synthesis import BudgetedLM
    from evals.schema import load_cases

    cases = [case for case in load_cases(SEED) if case.category == "single_source"]
    empty_validation = cases[1].model_copy(
        update={
            "case_id": "empty-validation",
            "question": "Kasus tanpa evidence validation.",
            "category": "insufficient",
            "evidence": [],
            "required_claims": [],
            "forbidden_claims": [],
            "expected_behavior": "insufficient",
        }
    )
    empty_test = cases[2].model_copy(
        update={
            "case_id": "empty-test",
            "question": "Kasus tanpa evidence test.",
            "category": "insufficient",
            "evidence": [],
            "required_claims": [],
            "forbidden_claims": [],
            "expected_behavior": "insufficient",
        }
    )
    dataset = tmp_path / "mixed.jsonl"
    dataset.write_text(
        "\n".join(
            case.model_dump_json()
            for case in [cases[0], cases[1], empty_validation, cases[2], empty_test]
        )
    )
    _settings(monkeypatch)

    class Engine:
        def __init__(self, role):
            self.role = role

        def complete(self, request):
            if self.role == "judge":
                text = json.dumps(
                    dict(
                        covered_claims=[True, True],
                        supported_claims=[True, True],
                        unsupported_claims=[],
                        forbidden_present=[False, False],
                        behavior_matches=True,
                        feedback="Didukung.",
                    )
                )
            elif self.role == "reflection":
                text = "[[ ## new_instruction ## ]]\nJawab dari sumber.\n[[ ## completed ## ]]"
            else:
                text = "[[ ## answer ## ]]\nFakta didukung [1].\n[[ ## completed ## ]]"
            return Response(
                id=None,
                model=request.model,
                message=Message.assistant(text),
                finish_reason="stop",
                usage=Usage(),
            )

    class Baseline:
        def invoke(self, payload):
            return {"messages": [SimpleNamespace(type="ai", content="Fakta didukung [1].")]}

    def clients(_settings, budget):
        lms = [
            BudgetedLM("openai/test", budget=budget, role=role, engine=Engine(role))
            for role in ("synthesis", "judge", "reflection")
        ]
        return runner.Clients(lambda _: Baseline(), *lms, {"provider": "test", "model": "test"})

    monkeypatch.setattr(runner, "build_clients", clients)
    output = tmp_path / "run"
    assert main(["run", "--dataset", str(dataset), "--output", str(output)]) == 0
    rows = [json.loads(line) for line in (output / "results.jsonl").read_text().splitlines()]
    empty_rows = [row for row in rows if row["case_id"] in {"empty-validation", "empty-test"}]
    assert len(empty_rows) == 5
    assert all(row["status"] == "skipped_no_evidence" for row in empty_rows)
    assert all(row["generation_calls"] == row["judge_calls"] == 0 for row in empty_rows)
