"""CLI evaluasi offline; import validate tidak membutuhkan provider."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import math
import os
import platform
import statistics
import sys
import tempfile
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import perf_counter
from typing import Any

from evals.schema import (
    EvaluationSettings,
    canonical_json,
    case_fingerprint,
    dataset_fingerprint,
    load_cases,
)


@dataclass
class Clients:
    baseline_factory: Any
    task_lm: Any
    judge_lm: Any
    reflection_lm: Any
    metadata: dict
    secrets: tuple[str, ...] = ()
    baseline_model: Any = None

    def close(self):
        for lm in (self.task_lm, self.judge_lm, self.reflection_lm):
            lm.close()
        if self.baseline_model is not None:
            import asyncio

            self.baseline_model.root_client.close()
            asyncio.run(self.baseline_model.root_async_client.close())


def build_clients(settings, budget) -> Clients:
    """Gunakan provider/model produksi yang sama, tanpa retry/fallback."""
    import config
    from evals.dspy_synthesis import BudgetedLM
    from main import build_system_prompt, define_agent, load_llm

    metadata: dict[str, Any]
    connection: dict[str, Any]
    if config.MODELHUB_API_KEY:
        if not config.MODELHUB_MODEL_NAME or not config.MODELHUB_BASE_URL:
            raise ValueError("Konfigurasi ModelHub tidak lengkap")
        model = "openai/" + config.MODELHUB_MODEL_NAME
        connection = dict(
            api_key=config.MODELHUB_API_KEY,
            api_base=config.MODELHUB_BASE_URL,
            extra_headers={"User-Agent": "curl/8.0"},
        )
        metadata = dict(provider="modelhub", model=config.MODELHUB_MODEL_NAME)
    else:
        if not config.AZURE_OPENAI_DEPLOYMENT_NAME:
            raise ValueError("Deployment Azure wajib untuk evaluasi")
        model = "azure/" + config.AZURE_OPENAI_DEPLOYMENT_NAME
        connection = dict(
            api_key=config.AZURE_OPENAI_API_KEY,
            api_base=config.AZURE_OPENAI_ENDPOINT,
            api_version=config.AZURE_OPENAI_PREVIEW_API_VERSION,
        )
        metadata = dict(provider="azure", model=config.AZURE_OPENAI_DEPLOYMENT_NAME)
    lms = []
    try:
        for role in ("synthesis", "judge", "reflection"):
            lms.append(
                BudgetedLM(
                    model,
                    budget=budget,
                    role=role,
                    model_type="chat",
                    engine="litellm",
                    cache=False,
                    num_retries=0,
                    max_tokens=config.LLM_MAX_TOKENS,
                    timeout=config.LLM_TIMEOUT,
                    temperature=config.LLM_TEMPERATURE
                    if role == "reflection"
                    else settings.temperature,
                    **connection,
                )
            )
        baseline_model = load_llm(temperature=settings.temperature, max_retries=0)
    except BaseException:
        for lm in lms:
            lm.close()
        raise
    agents = {}

    def baseline_factory(as_of):
        if as_of not in agents:
            agents[as_of] = define_agent(baseline_model, build_system_prompt(as_of=as_of))
        return agents[as_of]

    metadata["generation_limits"] = dict(
        max_tokens=config.LLM_MAX_TOKENS,
        timeout=config.LLM_TIMEOUT,
        reflection_temperature=config.LLM_TEMPERATURE,
        retries=0,
    )
    secrets = tuple(key for key in (config.MODELHUB_API_KEY, config.AZURE_OPENAI_API_KEY) if key)
    return Clients(
        baseline_factory,
        lms[0],
        lms[1],
        lms[2],
        metadata,
        secrets=secrets,
        baseline_model=baseline_model,
    )


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now():
    return datetime.now(UTC).isoformat()


def _versions():
    return {name: version(name) for name in ("dspy", "gepa", "langchain")}


def _atomic(output: Path, name: str, content: str):
    fd, temporary = tempfile.mkstemp(dir=output, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, output / name)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _json(output, name, value):
    _atomic(output, name, canonical_json(value) + "\n")


def _check_output(output: Path, dataset: Path):
    protected = Path(__file__).parent / "data"
    resolved = output.resolve()
    if (
        output.exists()
        or output.is_symlink()
        or resolved == dataset.resolve()
        or resolved == protected.resolve()
        or protected.resolve() in resolved.parents
        or resolved in dataset.resolve().parents
    ):
        raise ValueError("Output harus direktori baru di luar dataset/data")


def _error_code(error):
    from evals.dspy_synthesis import BudgetExceeded, FatalLMError

    if isinstance(error, BudgetExceeded):
        return "budget_exhausted"
    if isinstance(error, ArtifactMismatch):
        return "artifact_mismatch"
    if isinstance(error, ScoringError):
        return "scoring_error"
    error_type = error.error_type if isinstance(error, FatalLMError) else type(error)
    name = error_type.__name__.lower()
    if "auth" in name or "permission" in name:
        return "auth_error"
    if "parse" in name or "adapter" in name:
        return "parse_error"
    if issubclass(error_type, (ValueError, PackageNotFoundError)) or "configuration" in name:
        return "configuration_error"
    return "provider_error"


class ArtifactMismatch(ValueError):
    """State tidak cocok dengan manifest run ini."""


class ScoringError(ValueError):
    """Penilaian gagal; bukan jawaban kandidat yang kurang baik."""


def reload_program(output, manifest, task_lm):
    """Load JSON aman hanya setelah hash, versi dan identitas cocok."""
    from evals.dspy_synthesis import SynthesisProgram

    try:
        stored = json.loads((output / "manifest.json").read_text())
        data = (output / "program.json").read_bytes()
        if (
            stored["program_sha256"] != _hash(data)
            or stored["versions"] != _versions()
            or any(stored[key] != manifest[key] for key in ("dataset_sha256", "split_fingerprints"))
        ):
            raise ArtifactMismatch("artifact_mismatch")
        program = SynthesisProgram()
        program.load(output / "program.json", allow_pickle=False, allow_unsafe_lm_state=False)
        program.set_lm(task_lm)
        return program
    except OSError, KeyError, ValueError, TypeError:
        raise ArtifactMismatch("artifact_mismatch") from None


def _aggregate(rows, cases):
    expected = len(cases)
    known = [r for r in rows if r["status"] != "error"]
    applicable = sum(bool(c.evidence) for c in cases)
    valid = sum(r["citation_status"] == "valid" for r in known)
    judged = [r for r in known if r["unsupported_claims"] is not None]
    times = sorted(r["elapsed_synthesis_seconds"] for r in known)
    return dict(
        cases=expected,
        completed=len(known),
        error_or_missing=expected - len(known),
        mean_score=sum(r["score"] for r in rows) / expected if expected else None,
        mean_coverage=sum(r["coverage"] for r in rows) / expected if expected else None,
        citation_valid_rate=valid / applicable if applicable else None,
        citation_applicable=applicable,
        unsupported_rate=sum(bool(r["unsupported_claims"]) for r in judged) / len(judged)
        if judged
        else None,
        forbidden_rate=sum(any(r["forbidden_present"]) for r in judged) / len(judged)
        if judged
        else None,
        unknown_judge=sum(bool(c.evidence) for c in cases) - len(judged),
        latency_median=statistics.median(times) if times else None,
        latency_p95=times[math.ceil(0.95 * len(times)) - 1] if times else None,
    )


def _summary(status, rows, cases, budget, smoke, seed):
    test = [c for c in cases if c.split == "test"]
    backends = {}
    for backend in ("baseline", "dspy", "dspy_optimized"):
        selected = [r for r in rows if r["phase"] == "test_after" and r["backend"] == backend]
        backends[backend] = _aggregate(selected, test)
        backends[backend]["categories"] = {
            cat: _aggregate(
                [r for r in selected if r["category"] == cat],
                [c for c in test if c.category == cat],
            )
            for cat in sorted({c.category for c in test})
        }
    base, opt = backends["baseline"], backends["dspy_optimized"]
    verdict = "inconclusive"
    if (
        status == "complete"
        and not smoke
        and not any(b["error_or_missing"] or b["unknown_judge"] for b in backends.values())
    ):
        safety = all(
            opt[key] >= base[key] if key == "citation_valid_rate" else opt[key] <= base[key]
            for key in ("citation_valid_rate", "unsupported_rate", "forbidden_rate")
            if opt[key] is not None and base[key] is not None
        )
        if opt["mean_score"] < base["mean_score"] or not safety:
            verdict = "regressed"
        elif opt["mean_score"] > base["mean_score"]:
            verdict = "improved_on_seed_holdout" if seed else "improved_on_holdout"
        else:
            verdict = "no_improvement"
    tokens = {
        key: dict(
            reported_total=sum(e[key] for e in budget.events if e[key] is not None),
            unknown=sum(e[key] is None for e in budget.events),
        )
        for key in ("input_tokens", "output_tokens")
    }
    return dict(
        status=status,
        verdict=verdict,
        calls=dict(total=budget.total, limit=budget.limit, roles=dict(budget.counts)),
        backends=backends,
        tokens=tokens,
        usd_cost=None,
    )


def _execute(cases, settings, output, manifest, rows, budget):
    import dspy
    from dspy.teleprompt.gepa import InstructionProposer

    from agent.synthesis import (
        SynthesisDraft,
        finalize_answer,
        inspect_citations,
        invoke_synthesis,
        render_evidence,
    )
    from evals.audit import CandidateAudit
    from evals.dspy_synthesis import BudgetExceeded, SynthesisProgram, chat_adapter
    from evals.schema import to_research_evidence
    from evals.scoring import AnswerJudgeSignature, JudgeResponseError, Scorer
    from main import build_system_prompt

    clients = build_clients(settings, budget)
    try:
        manifest.update(clients.metadata)

        def write_audit(data):
            encoded = canonical_json(data)
            for secret in clients.secrets:
                encoded = encoded.replace(json.dumps(secret, ensure_ascii=False)[1:-1], "[DIHAPUS]")
            _atomic(output, "gepa_audit.json", encoded + "\n")

        judge = dspy.Predict(AnswerJudgeSignature, n=1)
        judge.set_lm(clients.judge_lm)
        scorer = Scorer(
            judge, on_failure=lambda failure: _json(output, "scoring_failure.json", failure)
        )
        initial = SynthesisProgram()
        initial.set_lm(clients.task_lm)

        def evaluate(case, backend, program, phase):
            sources = to_research_evidence(case)
            before = Counter(budget.counts)
            event_start = len(budget.events)
            hits = scorer.cache_hits
            start = perf_counter()
            draft = SynthesisDraft("")
            error_code = None
            scoring_reason = None
            score = None
            elapsed = 0.0
            try:
                if sources:
                    if backend == "baseline":
                        agent = clients.baseline_factory(case.as_of)
                        budget.reserve("baseline")
                        try:
                            draft = invoke_synthesis(agent, case.question, sources)
                        finally:
                            budget.record(
                                "baseline",
                                perf_counter() - start,
                                draft.input_tokens,
                                draft.output_tokens,
                            )
                    else:
                        prediction = program(
                            policy=build_system_prompt(as_of=case.as_of),
                            question=case.question,
                            evidence=render_evidence(sources),
                        )
                        if not isinstance(prediction.answer, str):
                            raise ValueError("answer tidak string")
                        draft = SynthesisDraft(prediction.answer)
                elapsed = perf_counter() - start
                released = finalize_answer(draft.raw_answer, sources)
                try:
                    score = scorer.score(case, draft, released)
                except BudgetExceeded:
                    raise
                except JudgeResponseError as error:
                    scoring_reason = error.reason
                    raise ScoringError("scoring_error") from None
                except Exception:
                    raise ScoringError("scoring_error") from None
            except Exception as error:
                elapsed = elapsed or perf_counter() - start
                error_code = _error_code(error)
                released = finalize_answer(draft.raw_answer, sources)
                if error_code in (
                    "budget_exhausted",
                    "auth_error",
                    "configuration_error",
                    "scoring_error",
                ):
                    raise
            finally:
                verdict = score.verdict if score else None
                events = budget.events[event_start:]
                generation = [e for e in events if e["role"] != "judge"]
                row = dict(
                    phase=phase,
                    backend=backend,
                    case_id=case.case_id,
                    category=case.category,
                    input_fingerprint=case_fingerprint(case),
                    raw_answer=draft.raw_answer,
                    answer=finalize_answer(draft.raw_answer, sources).answer,
                    citations=[
                        c.model_dump() for c in finalize_answer(draft.raw_answer, sources).citations
                    ],
                    citation_status=inspect_citations(draft.raw_answer, len(sources)).status
                    if sources
                    else "no_evidence",
                    score=score.score if score else 0,
                    coverage=score.coverage if score else 0,
                    groundedness=score.groundedness if score else None,
                    behavior_matches=score.behavior_matches if score else None,
                    feedback=score.feedback
                    if score
                    else (
                        f"Penilaian judge gagal: {scoring_reason}"
                        if scoring_reason
                        else "Evaluasi gagal; lihat error_code."
                    ),
                    elapsed_synthesis_seconds=elapsed,
                    generation_calls=sum(
                        budget.counts[r] - before[r] for r in ("baseline", "synthesis")
                    ),
                    judge_calls=budget.counts["judge"] - before["judge"],
                    cache_hit=scorer.cache_hits > hits,
                    status="error" if error_code else "ok" if sources else "skipped_no_evidence",
                    error_code=error_code,
                )
                for key in (
                    "covered_claims",
                    "supported_claims",
                    "unsupported_claims",
                    "forbidden_present",
                ):
                    row[key] = getattr(verdict, key) if verdict else None
                for key in ("input_tokens", "output_tokens"):
                    row[key] = (
                        sum(e[key] for e in generation)
                        if generation and all(e[key] is not None for e in generation)
                        else None
                    )
                encoded = canonical_json(row)
                for secret in clients.secrets:
                    encoded = encoded.replace(
                        json.dumps(secret, ensure_ascii=False)[1:-1], "[DIHAPUS]"
                    )
                rows.append(json.loads(encoded))
                _atomic(output, "results.jsonl", "".join(canonical_json(r) + "\n" for r in rows))

        with dspy.context(adapter=chat_adapter(), disable_history=True):
            for case in (c for c in cases if c.split == "validation"):
                evaluate(case, "baseline", None, "validation_before")
                evaluate(case, "dspy", initial, "validation_before")

            def examples(split):
                return [
                    dspy.Example(
                        policy=build_system_prompt(as_of=c.as_of),
                        question=c.question,
                        evidence=render_evidence(to_research_evidence(c)),
                        case=c.model_dump(mode="json"),
                    ).with_inputs("policy", "question", "evidence")
                    for c in cases
                    if c.split == split and c.evidence
                ]

            valset = examples("validation")
            audit = CandidateAudit(write_audit, [example.case["case_id"] for example in valset])

            optimizer = dspy.GEPA(
                metric=scorer.metric,
                auto=None,
                max_metric_calls=settings.gepa_metric_calls,
                reflection_lm=clients.reflection_lm,
                reflection_minibatch_size=1,
                skip_perfect_score=False,
                gepa_kwargs={
                    "acceptance_criterion": "improvement_or_equal",
                    "selection_strategy": audit.selection_strategy(),
                    "callbacks": [audit],
                },
                num_threads=1,
                use_merge=False,
                track_stats=True,
                add_format_failure_as_feedback=True,
                log_dir=None,
                use_wandb=False,
                use_mlflow=False,
                seed=settings.seed,
                instruction_proposer=InstructionProposer(adapter=chat_adapter()),
            )
            student = SynthesisProgram()
            student.set_lm(clients.task_lm)
            compiled = optimizer.compile(student, trainset=examples("train"), valset=valset)
            audit.finish(compiled.detailed_results)
            budget.raise_if_failed()
            if budget.exhausted:
                raise BudgetExceeded("budget_exhausted")
            if scorer.failure is not None:
                raise ScoringError(scorer.failure["reason"])
            compiled.set_lm(None)
            fd, temporary = tempfile.mkstemp(dir=output, suffix=".json")
            os.close(fd)
            try:
                compiled.save(temporary, save_program=False)
                os.chmod(temporary, 0o600)
                os.replace(temporary, output / "program.json")
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            manifest["program_sha256"] = _hash((output / "program.json").read_bytes())
            _json(output, "manifest.json", manifest)
            optimized = reload_program(output, manifest, clients.task_lm)
            for backend, program in (
                ("baseline", None),
                ("dspy", initial),
                ("dspy_optimized", optimized),
            ):
                for case in (c for c in cases if c.split == "test"):
                    evaluate(case, backend, program, "test_after")
    finally:
        clients.close()


def _run(cases, settings, dataset, output, smoke):
    from evals.dspy_synthesis import CallBudget, FatalLMError
    from evals.scoring import AnswerJudgeSignature
    from main import build_system_prompt

    budget = CallBudget(settings.max_lm_calls)
    rows: list[dict] = []
    seed_path = Path(__file__).parent / "data/synthesis_seed.jsonl"
    seed = dataset.resolve() == seed_path.resolve() and dataset_fingerprint(
        load_cases(seed_path)
    ) == dataset_fingerprint(cases)
    full = cases
    if smoke:
        cases = [
            next(c for c in full if c.split == split and c.category == "single_source")
            for split in ("train", "validation", "test")
        ]
    manifest = dict(
        schema_version=1,
        dataset_sha256=dataset_fingerprint(full),
        split_fingerprints={
            s: [case_fingerprint(c) for c in cases if c.split == s]
            for s in ("train", "validation", "test")
        },
        selected_ids=[c.case_id for c in cases],
        synthetic_seed=seed,
        python=platform.python_version(),
        versions=_versions(),
        generation=settings.model_dump(),
        adapter="ChatAdapter(native=False,fallback=False)",
        judge_adapter="JSONAdapter(native=False,strict_json_schema,case_array_bounds,no_runtime_fallback)",
        policy_hashes={
            c.as_of.isoformat(): _hash(build_system_prompt(as_of=c.as_of).encode()) for c in cases
        },
        judge_signature_sha256=_hash(str(AnswerJudgeSignature).encode()),
        optimizer=dict(
            max_metric_calls=settings.gepa_metric_calls,
            seed=settings.seed,
            reflection_minibatch_size=1,
            skip_perfect_score=False,
            acceptance_criterion="improvement_or_equal",
            num_threads=1,
            use_merge=False,
        ),
        started_at=_now(),
        finished_at=None,
        program_sha256=None,
    )
    output.mkdir(mode=0o700, parents=False)
    _json(output, "manifest.json", manifest)
    _atomic(output, "results.jsonl", "")
    status = "complete"
    error_code = None
    previous_logging = logging.root.manager.disable
    try:
        # Framework/provider diagnostics dapat memuat prompt atau exception berisi secret.
        logging.disable(logging.CRITICAL)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            _execute(cases, settings, output, manifest, rows, budget)
        if any(row["status"] == "error" for row in rows):
            status = "failed"
    except KeyboardInterrupt:
        status = "interrupted"
    except Exception as error:
        error_code = _error_code(
            FatalLMError(budget.fatal_error_type) if budget.fatal_error_type is not None else error
        )
        status = (
            "budget_exhausted" if budget.exhausted or error_code == "budget_exhausted" else "failed"
        )
    finally:
        logging.disable(previous_logging)
        manifest["finished_at"] = _now()
        _json(output, "manifest.json", manifest)
        summary = _summary(status, rows, cases, budget, smoke, seed)
        summary["error_code"] = error_code
        _json(output, "summary.json", summary)
    print(f"Evaluasi {status}: {len(cases)} kasus, {budget.total}/{budget.limit} panggilan.")
    print("Backend | Skor test | Kasus selesai")
    for backend, data in summary["backends"].items():
        print(f"{backend} | {data['mean_score']:.3f} | {data['completed']}/{data['cases']}")
    print(f"Laporan: {output}")
    return 0 if status == "complete" else 1


def main(argv: list[str] | None = None) -> int:
    """Dua subcommands eksplisit; tidak ada backend produksi."""
    parser = argparse.ArgumentParser(description="Evaluasi sintesis dengan bukti beku.")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validasi snapshot tanpa provider")
    validate.add_argument("--dataset", required=True, type=Path)
    run = commands.add_parser("run", help="Bandingkan baseline dan DSPy; inference berbayar")
    run.add_argument("--dataset", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    try:
        try:
            cases = load_cases(args.dataset)
        except ValueError as error:
            print(f"Dataset invalid: {error}", file=sys.stderr)
            return 2
        if args.command == "validate":
            counts = Counter(c.split for c in cases)
            print(
                f"Dataset valid: {len(cases)} kasus (train={counts['train']}, validation={counts['validation']}, test={counts['test']})."
            )
            return 0
        _check_output(args.output, args.dataset)
        _versions()
        settings = EvaluationSettings.from_env()
        if args.smoke and any(
            not any(c.split == s and c.category == "single_source" for c in cases)
            for s in ("train", "validation", "test")
        ):
            raise ValueError("Smoke memerlukan single_source pada setiap split")
        if any(
            not any(c.split == s and c.evidence for c in cases) for s in ("train", "validation")
        ):
            raise ValueError("Optimasi memerlukan bukti pada train dan validation")
        if not args.output.parent.is_dir():
            args.output.parent.mkdir(parents=True, exist_ok=True)
        return _run(cases, settings, args.dataset, args.output, args.smoke)
    except ValueError, OSError, ImportError, PackageNotFoundError:
        print(
            "Evaluasi tidak dapat dimulai: periksa dataset, konfigurasi, dependency, dan path output.",
            file=sys.stderr,
        )
        return 2
