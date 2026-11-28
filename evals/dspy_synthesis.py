"""DSPy offline: satu predictor tanpa tools dan budget sebelum inference."""

import threading
from collections import Counter
from time import perf_counter

import dspy
from dspy.lm15 import Request, Response


class SynthesisSignature(dspy.Signature):
    """Susun jawaban dari pertanyaan, kebijakan, dan bukti yang diberikan."""

    policy: str = dspy.InputField()
    question: str = dspy.InputField()
    evidence: str = dspy.InputField()
    answer: str = dspy.OutputField()


class SynthesisProgram(dspy.Module):
    def __init__(self):
        super().__init__()
        self.qa = dspy.Predict(SynthesisSignature, n=1)

    def forward(self, policy: str, question: str, evidence: str) -> dspy.Prediction:
        return self.qa(policy=policy, question=question, evidence=evidence)


class BudgetExceeded(RuntimeError):
    """Tidak ada slot inference tersisa."""


class FatalLMError(RuntimeError):
    """Kegagalan inference tersimpan sebagai tipe, tanpa pesan atau credential."""

    def __init__(self, error_type: type[Exception]):
        self.error_type = error_type
        super().__init__("Inference LM gagal selama evaluasi")


class CallBudget:
    def __init__(self, limit: int):
        if type(limit) is not int or limit <= 0:
            raise ValueError("budget harus integer positif")
        self.limit = limit
        self.total = 0
        self.counts: Counter = Counter()
        self.exhausted = False
        self.fatal_error_type: type[Exception] | None = None
        self.events: list[dict] = []
        self.lock = threading.Lock()

    def reserve(self, role: str) -> None:
        if role not in ("baseline", "synthesis", "judge", "reflection"):
            raise ValueError("role inference invalid")
        with self.lock:
            if self.total >= self.limit:
                self.exhausted = True
                raise BudgetExceeded("budget inference habis")
            self.total += 1
            self.counts[role] += 1

    def record(self, role, elapsed, input_tokens=None, output_tokens=None):
        with self.lock:
            self.events.append(
                dict(
                    role=role,
                    elapsed=elapsed,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            )

    def record_failure(self, error: Exception) -> None:
        with self.lock:
            if self.fatal_error_type is None:
                self.fatal_error_type = type(error)

    def raise_if_failed(self) -> None:
        with self.lock:
            error_type = self.fatal_error_type
        if error_type is not None:
            raise FatalLMError(error_type) from None

    def __deepcopy__(self, memo):
        return self


def _guard_settings(kwargs):
    if (
        kwargs.get("cache", False) is not False
        or kwargs.get("num_retries", 0) != 0
        or kwargs.get("n", 1) != 1
    ):
        raise ValueError("cache/retry/multiple candidates dilarang untuk evaluasi")


class BudgetedLM(dspy.LM):
    def __init__(self, model: str, *, budget: CallBudget, role: str, **kwargs):
        _guard_settings(kwargs)
        kwargs.setdefault("cache", False)
        kwargs.setdefault("num_retries", 0)
        self.budget = budget
        self.role = role
        super().__init__(model, **kwargs)

    def copy(self, **kwargs):
        _guard_settings(kwargs)
        return super().copy(**kwargs)

    def __call__(self, *args, **kwargs):
        _guard_settings(kwargs)
        if len(args) != 1 or not isinstance(args[0], Request):
            raise ValueError("evaluator hanya menerima canonical Request")
        self.budget.reserve(self.role)
        start = perf_counter()
        response = None
        try:
            response = super().__call__(*args, **kwargs)
            return response
        except Exception as error:
            self.budget.record_failure(error)
            raise
        finally:
            usage = response.usage if isinstance(response, Response) else None
            self.budget.record(
                self.role,
                perf_counter() - start,
                usage.input_tokens if usage else None,
                usage.output_tokens if usage else None,
            )


def chat_adapter():
    """Matikan native tool calling dan fallback yang menambah inference."""
    return dspy.ChatAdapter(use_native_function_calling=False, use_json_adapter_fallback=False)
