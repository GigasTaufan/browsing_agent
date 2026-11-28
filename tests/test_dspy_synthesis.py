"""Integrasi canonical DSPy dan gate kualitas tanpa jaringan."""

import copy
from pathlib import Path

import pytest

pytest.importorskip("dspy")
import dspy
from dspy.lm15 import Message, Request, Response, Usage

from agent.synthesis import SynthesisDraft, finalize_answer
from evals.dspy_synthesis import BudgetedLM, BudgetExceeded, CallBudget, SynthesisProgram
from evals.schema import load_cases, to_research_evidence
from evals.scoring import score_case


class Engine:
    def __init__(self):
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return Response(
            id=None,
            model=request.model,
            message=Message.assistant(
                "[[ ## answer ## ]]\nHarga Rp120.000; kapasitas 10 kanal [1].\n[[ ## completed ## ]]"
            ),
            finish_reason="stop",
            usage=Usage(input_tokens=0, output_tokens=3),
        )


def test_guard_and_copy_share_budget():
    engine = Engine()
    budget = CallBudget(2)
    lm = BudgetedLM(
        "openai/test", budget=budget, role="synthesis", engine=engine, cache=False, num_retries=0
    )
    request = Request(model="openai/test", messages=(Message.user("Halo"),))
    lm(request)
    lm.copy()(request)
    with pytest.raises(BudgetExceeded):
        copy.deepcopy(lm)(request)
    assert len(engine.requests) == budget.total == 2
    assert budget.exhausted
    assert budget.events[0]["input_tokens"] == 0


def test_actual_predict_and_final_scoring():
    case = load_cases(Path("evals/data/synthesis_seed.jsonl"))[0]
    program = SynthesisProgram()
    program.set_lm(
        BudgetedLM(
            "openai/test",
            budget=CallBudget(10),
            role="synthesis",
            engine=Engine(),
            cache=False,
            num_retries=0,
        )
    )
    with dspy.context(
        adapter=dspy.ChatAdapter(use_native_function_calling=False, use_json_adapter_fallback=False)
    ):
        prediction = program(
            policy="Kutip sumber", question=case.question, evidence=case.evidence[0].text
        )
    sources = to_research_evidence(case)
    draft = SynthesisDraft(prediction.answer)
    verdict = dict(
        covered_claims=[True, True],
        supported_claims=[True, True],
        unsupported_claims=[],
        forbidden_present=[False, False],
        behavior_matches=True,
        feedback="Benar",
    )
    seen = {}

    def judge(**kwargs):
        seen.update(kwargs)
        return dspy.Prediction(**verdict)

    assert score_case(case, draft, finalize_answer(draft.raw_answer, sources), judge).score == 1
    assert seen["answer"] == draft.raw_answer
    verdict["unsupported_claims"] = ["Harga salah"]
    assert score_case(case, draft, finalize_answer(draft.raw_answer, sources), judge).score == 0
    invalid = SynthesisDraft("Saya tidak tahu")
    assert score_case(case, invalid, finalize_answer(invalid.raw_answer, sources), None).score == 0
    verdict["covered_claims"] = []
    with pytest.raises(ValueError):
        score_case(case, draft, finalize_answer(draft.raw_answer, sources), judge)


@pytest.mark.parametrize("kwargs", [{"cache": True}, {"num_retries": 1}, {"n": 2}])
def test_guard_rejects_hidden_attempts(kwargs):
    with pytest.raises(ValueError):
        BudgetedLM("openai/test", budget=CallBudget(2), role="synthesis", **kwargs)


def test_failed_attempt_and_copy_settings():
    from dspy.utils.exceptions import LMUnexpectedError

    from evals.dspy_synthesis import FatalLMError

    class FailedEngine:
        def complete(self, request):
            raise RuntimeError("provider gagal")

    budget = CallBudget(2)
    lm = BudgetedLM("openai/test", budget=budget, role="reflection", engine=FailedEngine())
    request = Request(model="openai/test", messages=(Message.user("Halo"),))
    with pytest.raises(LMUnexpectedError):
        lm(request)
    assert budget.total == 1
    assert budget.events[0]["input_tokens"] is None
    assert budget.fatal_error_type is LMUnexpectedError
    with pytest.raises(FatalLMError) as failure:
        copy.deepcopy(lm).budget.raise_if_failed()
    assert failure.value.error_type is LMUnexpectedError
    with pytest.raises(ValueError):
        lm.copy(cache=True)


def test_remapped_judge_and_no_evidence():
    case = next(
        c for c in load_cases(Path("evals/data/synthesis_seed.jsonl")) if c.category == "dated"
    )
    draft = SynthesisDraft("Fakta [2]")
    seen = {}

    def judge(**kwargs):
        seen.update(kwargs)
        return dspy.Prediction(
            covered_claims=[True] * 3,
            supported_claims=[True] * 3,
            unsupported_claims=[],
            forbidden_present=[False] * 2,
            behavior_matches=True,
            feedback="Didukung",
        )

    score_case(case, draft, finalize_answer(draft.raw_answer, to_research_evidence(case)), judge)
    import json

    assert seen["answer"] == "Fakta [1]"
    assert json.loads(seen["cited_sources"])[0]["original_id"] == 2
    empty = case.model_copy(
        update={"evidence": [], "required_claims": [], "expected_behavior": "insufficient"}
    )
    assert score_case(empty, SynthesisDraft(""), finalize_answer("", []), None).score == 1


@pytest.mark.parametrize(
    "supported,unsupported,expected",
    [
        ([True, True, True], [], 1),
        ([False, False, False], ["Harga lama disebut berlaku pada tanggal baru."], 0),
    ],
)
def test_actual_judge_parses_dated_claims(supported, unsupported, expected):
    import json

    from evals.dspy_synthesis import chat_adapter
    from evals.scoring import AnswerJudgeSignature

    case = next(
        c
        for c in load_cases(Path("evals/data/synthesis_seed.jsonl"))
        if c.case_id == "validation-dated"
    )
    fields = dict(
        covered_claims=[True, True, True],
        supported_claims=supported,
        unsupported_claims=unsupported,
        forbidden_present=[False, False],
        behavior_matches=True,
        feedback="Periksa tanggal dan sumber [2].",
    )

    class JudgeEngine:
        def complete(self, request):
            output = json.dumps(fields)
            return Response(
                id=None,
                model=request.model,
                message=Message.assistant(output),
                finish_reason="stop",
                usage=Usage(),
            )

    judge = dspy.Predict(AnswerJudgeSignature, n=1)
    judge.set_lm(
        BudgetedLM("openai/test", budget=CallBudget(1), role="judge", engine=JudgeEngine())
    )
    answer = "Harga Rp140.000 dan kapasitas 12 kanal per 2026-02-10 [2]."
    if expected == 0:
        answer = "Harga Rp70.000 dan kapasitas 6 kanal berlaku per 2026-02-10 [1]."
    sources = to_research_evidence(case)
    with dspy.context(adapter=chat_adapter(), disable_history=True):
        score = score_case(case, SynthesisDraft(answer), finalize_answer(answer, sources), judge)
    assert score.score == expected
    assert score.verdict is not None
    assert score.verdict.unsupported_claims == unsupported


@pytest.mark.parametrize(
    "failure,reason",
    [
        ("missing", "judge_parse_error"),
        ("dimensions", "judge_dimension_mismatch"),
        ("type", "judge_parse_error"),
    ],
)
def test_json_judge_rejects_invalid_comparison_without_retry(failure, reason):
    import json

    from evals.scoring import AnswerJudgeSignature, JudgeResponseError

    case = next(
        c
        for c in load_cases(Path("evals/data/synthesis_seed.jsonl"))
        if c.case_id == "validation-comparison"
    )
    fields = dict(
        covered_claims=[True] * 4,
        supported_claims=[True] * 4,
        unsupported_claims=[],
        forbidden_present=[False] * 2,
        behavior_matches=True,
        feedback="Periksa sumber.",
    )
    if failure == "missing":
        del fields["unsupported_claims"]
    elif failure == "dimensions":
        fields["covered_claims"] = [True] * 3
    else:
        fields["covered_claims"] = ["bukan boolean"] * 4

    class JudgeEngine:
        def complete(self, request):
            return Response(
                id=None,
                model=request.model,
                message=Message.assistant(json.dumps(fields)),
                finish_reason="stop",
                usage=Usage(),
            )

    budget = CallBudget(2)
    judge = dspy.Predict(AnswerJudgeSignature, n=1)
    judge.set_lm(BudgetedLM("openai/test", budget=budget, role="judge", engine=JudgeEngine()))
    answer = "Cakra Rp140.000/12 kanal [1]; Damar Rp210.000/24 kanal [2]."
    with pytest.raises(JudgeResponseError) as error:
        score_case(
            case, SynthesisDraft(answer), finalize_answer(answer, to_research_evidence(case)), judge
        )
    assert error.value.reason.startswith(reason)
    assert budget.total == 1


def test_scorer_preserves_first_failure_after_framework_catches_it():
    from evals.scoring import JudgeResponseError, Scorer

    cases = load_cases(Path("evals/data/synthesis_seed.jsonl"))
    notifications = []

    def bad_judge(**kwargs):
        raise JudgeResponseError("judge_parse_error", {"response_characters": 12})

    scorer = Scorer(bad_judge, on_failure=notifications.append)
    for case in cases[:2]:
        draft = SynthesisDraft("Fakta [1]")
        with pytest.raises(JudgeResponseError):
            scorer.score(case, draft, finalize_answer(draft.raw_answer, to_research_evidence(case)))
    assert scorer.failure["case_id"] == cases[0].case_id
    assert scorer.failure["reason"] == "judge_parse_error"
    assert len(notifications) == 1
