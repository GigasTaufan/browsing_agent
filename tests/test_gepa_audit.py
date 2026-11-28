"""Kontrak audit kandidat GEPA; bergantung pada group eval opsional."""

import json
from types import SimpleNamespace

import pytest

pytest.importorskip("dspy")

from dspy.lm15 import Message, Response, Usage
from gepa.proposer.base import CandidateProposal

from evals.audit import CandidateAudit
from evals.dspy_synthesis import BudgetedLM
from evals.runner import main
from evals.schema import load_cases

SEED = "evals/data/synthesis_seed.jsonl"


def test_candidate_audit_links_acceptance_and_rejection_reason():
    reports = []
    audit = CandidateAudit(reports.append, ["validation-real"])
    proposals = [
        CandidateProposal(
            candidate={"qa": "prompt-equal"},
            parent_program_ids=[0],
            subsample_indices=[0],
            subsample_scores_before=[1.0],
            subsample_scores_after=[1.0],
        ),
        CandidateProposal(
            candidate={"qa": "prompt-worse"},
            parent_program_ids=[0],
            subsample_indices=[0],
            subsample_scores_before=[1.0],
            subsample_scores_after=[0.5],
        ),
    ]

    class ImprovementOrEqual:
        def should_accept(self, proposal, state):
            return sum(proposal.subsample_scores_after) >= sum(proposal.subsample_scores_before)

    selected = audit.selection_strategy().select(
        proposals, SimpleNamespace(i=0), ImprovementOrEqual()
    )
    assert selected == [proposals[0]]
    audit.on_candidate_accepted(
        dict(iteration=1, new_candidate_idx=1, new_score=1.0, parent_ids=[0])
    )
    audit.on_candidate_rejected(
        dict(
            iteration=1,
            old_score=1.0,
            new_score=0.5,
            reason="New subsample score 0.5 not better than old score 1.0",
        )
    )

    class Candidate:
        def __init__(self, instruction):
            self.signature = SimpleNamespace(instructions=instruction)

    class Program:
        def __init__(self, instruction):
            self.instruction = instruction

        def named_predictors(self):
            return [("qa", Candidate(self.instruction))]

    stats = SimpleNamespace(
        candidates=[Program("seed"), Program("prompt-equal")],
        parents=[[None], [0]],
        val_subscores=[{0: 0.5}, {0: 0.5}],
        val_aggregate_scores=[0.5, 0.5],
        discovery_eval_counts=[0, 1],
        best_idx=0,
        total_metric_calls=3,
        num_full_val_evals=2,
    )
    audit.finish(stats)
    decisions = reports[-1]["decisions"]
    assert [(d["instructions"]["qa"], d["outcome"], d["reason"]) for d in decisions] == [
        ("prompt-equal", "accepted", None),
        ("prompt-worse", "rejected", "New subsample score 0.5 not better than old score 1.0"),
    ]


def test_empty_validation_case_does_not_shift_audit_score_ids(tmp_path, monkeypatch):
    import evals.runner as runner

    cases = [
        case
        for case in load_cases(__import__("pathlib").Path(SEED))
        if case.category == "single_source"
    ]
    empty = cases[1].model_copy(
        update={
            "case_id": "validation-empty-first",
            "question": "Pertanyaan tanpa sumber validation.",
            "category": "insufficient",
            "evidence": [],
            "required_claims": [],
            "forbidden_claims": [],
            "expected_behavior": "insufficient",
        }
    )
    dataset = tmp_path / "mixed.jsonl"
    dataset.write_text(
        "\n".join(case.model_dump_json() for case in [cases[0], empty, cases[1], cases[2]])
    )
    for key, value in {
        "EVAL_TEMPERATURE": "0",
        "EVAL_LLM_MAX_RETRIES": "0",
        "EVAL_MAX_LM_CALLS": "80",
        "EVAL_GEPA_METRIC_CALLS": "3",
        "EVAL_SEED": "17",
    }.items():
        monkeypatch.setenv(key, value)

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
                text = "[[ ## answer ## ]]\nFakta [1].\n[[ ## completed ## ]]"
            return Response(
                id=None,
                model=request.model,
                message=Message.assistant(text),
                finish_reason="stop",
                usage=Usage(),
            )

    class Baseline:
        def invoke(self, payload):
            return {"messages": [SimpleNamespace(type="ai", content="Fakta [1].")]}

    def clients(_settings, budget):
        lms = [
            BudgetedLM("openai/test", budget=budget, role=role, engine=Engine(role))
            for role in ("synthesis", "judge", "reflection")
        ]
        return runner.Clients(lambda _: Baseline(), *lms, {"provider": "test", "model": "test"})

    monkeypatch.setattr(runner, "build_clients", clients)
    output = tmp_path / "run"
    assert main(["run", "--dataset", str(dataset), "--output", str(output)]) == 0
    audit = json.loads((output / "gepa_audit.json").read_text())
    for candidate in audit["candidates"]:
        assert candidate["validation_scores"] == {cases[1].case_id: 1.0}
