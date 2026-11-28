"""Audit GEPA tanpa menyimpan LM, credential, atau respons provider mentah."""

import math


class _AuditedAllImprovements:
    """Seleksi AllImprovements yang merekam setiap proposal dan acceptance."""

    def __init__(self, audit):
        self.audit = audit

    def select(self, proposals, state, acceptance_criterion):
        selected = []
        for proposal in proposals:
            passed = acceptance_criterion.should_accept(proposal, state)
            record = dict(
                iteration=state.i + 1,
                parent_ids=list(proposal.parent_program_ids),
                instructions=dict(proposal.candidate),
                subsample_indices=list(proposal.subsample_indices or []),
                scores_before=list(proposal.subsample_scores_before or []),
                scores_after=list(proposal.subsample_scores_after or []),
                score_before=sum(proposal.subsample_scores_before or []),
                score_after=sum(proposal.subsample_scores_after or []),
                criterion_passed=passed,
                selected_by_strategy=passed,
            )
            self.audit.proposals.append(record)
            if passed:
                selected.append(proposal)
            else:
                record["reason"] = "skor subsampel tidak memenuhi acceptance criterion"
        self.audit._write_running()
        return selected


class CandidateAudit:
    def __init__(self, write, validation_ids):
        self.write = write
        self.validation_ids = validation_ids
        self.events = []
        self.proposals = []

    def selection_strategy(self):
        return _AuditedAllImprovements(self)

    def _write_running(self):
        self.write(dict(status="running", events=self.events, proposals=self.proposals))

    def _record(self, kind, event, fields):
        self.events.append(dict(kind=kind, **{key: event[key] for key in fields if key in event}))
        self._write_running()

    def on_proposal_end(self, event):
        self._record("proposal", event, ("iteration", "new_instructions"))

    def on_candidate_accepted(self, event):
        self._record(
            "accepted", event, ("iteration", "new_candidate_idx", "new_score", "parent_ids")
        )

    def on_candidate_rejected(self, event):
        self._record("rejected", event, ("iteration", "old_score", "new_score", "reason"))

    def on_evaluation_skipped(self, event):
        self._record("skipped", event, ("iteration", "candidate_idx", "reason", "scores"))

    @staticmethod
    def _instructions(program):
        return {
            name: predictor.signature.instructions for name, predictor in program.named_predictors()
        }

    def _match_rejection(self, proposal, rejected, used):
        matches = [
            (index, event)
            for index, event in enumerate(rejected)
            if index not in used
            and event["iteration"] == proposal["iteration"]
            and math.isclose(event["old_score"], proposal["score_before"])
            and math.isclose(event["new_score"], proposal["score_after"])
        ]
        if not matches:
            return None
        index, event = matches[0]
        used.add(index)
        return event["reason"]

    def finish(self, stats):
        candidates = []
        for index, candidate in enumerate(stats.candidates):
            scores = {
                self.validation_ids[key]
                if isinstance(key, int) and 0 <= key < len(self.validation_ids)
                else str(key): value
                for key, value in stats.val_subscores[index].items()
            }
            candidates.append(
                dict(
                    index=index,
                    parents=stats.parents[index],
                    instructions=self._instructions(candidate),
                    validation_score=stats.val_aggregate_scores[index],
                    validation_scores=scores,
                    discovered_at_metric_call=stats.discovery_eval_counts[index],
                )
            )
        accepted = [event for event in self.events if event["kind"] == "accepted"]
        rejected = [event for event in self.events if event["kind"] == "rejected"]
        accepted_indices, used_rejections, decisions = set(), set(), []
        for proposal in self.proposals:
            decision = dict(proposal)
            if not proposal["criterion_passed"]:
                decision["outcome"] = "rejected"
                decision["reason"] = (
                    self._match_rejection(proposal, rejected, used_rejections) or decision["reason"]
                )
            else:
                candidate_index = next(
                    (
                        event["new_candidate_idx"]
                        for event in accepted
                        if event["iteration"] == proposal["iteration"]
                        and event["new_candidate_idx"] not in accepted_indices
                        and list(event["parent_ids"]) == proposal["parent_ids"]
                        and self._instructions(stats.candidates[event["new_candidate_idx"]])
                        == proposal["instructions"]
                    ),
                    None,
                )
                if candidate_index is not None:
                    accepted_indices.add(candidate_index)
                    decision.update(
                        outcome="accepted",
                        reason=None,
                        candidate_index=candidate_index,
                        validation_score=stats.val_aggregate_scores[candidate_index],
                    )
                else:
                    decision["outcome"] = "rejected"
                    decision["reason"] = (
                        self._match_rejection(proposal, rejected, used_rejections)
                        or "tidak terpetakan ke event keputusan GEPA"
                    )
            decisions.append(decision)
        self.write(
            dict(
                status="compiled",
                events=self.events,
                proposals=self.proposals,
                decisions=decisions,
                candidates=candidates,
                best_idx=stats.best_idx,
                total_metric_calls=stats.total_metric_calls,
                num_full_val_evals=stats.num_full_val_evals,
                selection_rule="highest validation score; earliest candidate wins ties",
            )
        )
