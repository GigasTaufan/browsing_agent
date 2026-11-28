"""Schema snapshot offline; validasi tidak mengimpor konfigurasi aplikasi."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

if TYPE_CHECKING:
    from agent.research import ResearchEvidence


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrozenSource(Schema):
    url: str
    title: str | None
    fetched_at: str
    text: str

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("URL harus HTTP(S), hostname valid, tanpa userinfo")
        return value

    @field_validator("fetched_at")
    @classmethod
    def valid_time(cls, value):
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("timestamp harus ISO dengan timezone")
        return value

    @field_validator("text")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("teks bukti kosong")
        return value


class ExpectedClaim(Schema):
    text: str
    source_ids: list[int] = Field(strict=True)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("teks gold kosong")
        return value

    @field_validator("source_ids", mode="before")
    @classmethod
    def strict_ids(cls, value):
        if not isinstance(value, list) or any(type(i) is not int for i in value):
            raise ValueError("source_ids harus integer")
        return value


class EvalCase(Schema):
    schema_version: Literal[1]
    case_id: str
    split: Literal["train", "validation", "test"]
    category: Literal[
        "single_source", "comparison", "dated", "conflict", "insufficient", "injection"
    ]
    question: str
    as_of: date
    evidence: list[FrozenSource]
    expected_behavior: Literal["answer", "insufficient"]
    required_claims: list[ExpectedClaim]
    forbidden_claims: list[str]

    @field_validator("case_id", "question")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("field kosong")
        return value

    @model_validator(mode="after")
    def validate_claims(self):
        if any(not text.strip() for text in self.forbidden_claims):
            raise ValueError("forbidden_claims kosong")
        if not self.evidence and (self.expected_behavior != "insufficient" or self.required_claims):
            raise ValueError("evidence kosong hanya untuk insufficient tanpa gold")
        for claim in self.required_claims:
            ids = claim.source_ids
            if (
                not ids
                or len(set(ids)) != len(ids)
                or any(i < 1 or i > len(self.evidence) for i in ids)
            ):
                raise ValueError("required_claims.source_ids tidak valid")
        return self


class EvaluationSettings(Schema):
    temperature: float = Field(ge=0, le=2, allow_inf_nan=False)
    llm_max_retries: Literal[0]
    max_lm_calls: int = Field(gt=0)
    gepa_metric_calls: int = Field(gt=0)
    seed: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_budget(self):
        if self.gepa_metric_calls > self.max_lm_calls:
            raise ValueError("budget GEPA melebihi budget global")
        return self

    @classmethod
    def from_env(cls) -> EvaluationSettings:
        from config import _env_float, _env_int

        return cls(
            temperature=_env_float("EVAL_TEMPERATURE"),
            llm_max_retries=_env_int("EVAL_LLM_MAX_RETRIES"),
            max_lm_calls=_env_int("EVAL_MAX_LM_CALLS"),
            gepa_metric_calls=_env_int("EVAL_GEPA_METRIC_CALLS"),
            seed=_env_int("EVAL_SEED"),
        )


def canonical_json(value) -> str:
    """Serialisasi deterministik seluruh field, tanpa truncation."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def case_fingerprint(case: EvalCase, identity: bool = False) -> str:
    data = case.model_dump(mode="json")
    return _fingerprint(
        {key: data[key] for key in ("question", "as_of", "evidence")} if identity else data
    )


def dataset_fingerprint(cases: list[EvalCase]) -> str:
    return _fingerprint([c.model_dump(mode="json") for c in cases])


def load_cases(path: Path) -> list[EvalCase]:
    """Tolak data invalid dan kebocoran split tanpa membaca URL."""
    cases = []
    ids = set()
    identities: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError, UnicodeError:
        raise ValueError(f"{path}: file tidak dapat dibaca") from None
    for line_no, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            case = EvalCase.model_validate_json(line)
        except ValidationError as error:
            fields = ", ".join(
                ".".join(map(str, e["loc"])) or "record" for e in error.errors(include_input=False)
            )
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                record = None
            case_id = record.get("case_id") if isinstance(record, dict) else None
            label = (
                f", case {json.dumps(case_id, ensure_ascii=False)}"
                if isinstance(case_id, str)
                else ""
            )
            raise ValueError(
                f"{path}: baris {line_no}{label}, field {fields}: data invalid"
            ) from None
        fingerprint = case_fingerprint(case, identity=True)
        if case.case_id in ids or (
            fingerprint in identities and identities[fingerprint] != case.split
        ):
            raise ValueError(
                f"{path}: baris {line_no}, case {case.case_id}: ID duplikat/kebocoran split"
            )
        ids.add(case.case_id)
        identities[fingerprint] = case.split
        cases.append(case)
    if not cases or {c.split for c in cases} != {"train", "validation", "test"}:
        raise ValueError(f"{path}: dataset kosong atau split tidak lengkap")
    return cases


def to_research_evidence(case: EvalCase) -> list[ResearchEvidence]:
    """Konversi runtime tanpa mengganti teks penuh dengan snippet."""
    from agent.research import ResearchEvidence
    from storage.evidence import EvidenceItem

    return [
        ResearchEvidence(
            EvidenceItem(
                url=s.url,
                title=s.title,
                canonical_url=s.url,
                fetched_at=s.fetched_at,
                snippet=s.text[:300],
            ),
            s.text,
        )
        for s in case.evidence
    ]
