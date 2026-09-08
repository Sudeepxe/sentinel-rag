from __future__ import annotations

import hashlib

from sentinel.observability.tracing import span
from sentinel.repair.catalog import repairs_for
from sentinel.schemas.experiments import ExperimentConfig
from sentinel.schemas.failures import FailureRecord
from sentinel.schemas.repair import RepairProposal


class RepairEngine:
    def suggest(
        self, failures: list[FailureRecord], base_config: ExperimentConfig
    ) -> list[RepairProposal]:
        with span("repair", base_config=base_config.name, n_failures=len(failures)):
            proposals: list[RepairProposal] = []
            seen_types = set()
            for failure in failures:
                failure_type = failure.primary
                if failure_type in seen_types:
                    continue
                seen_types.add(failure_type)
                for i, factory in enumerate(repairs_for(failure_type)):
                    digest = hashlib.sha256(f"{failure_type}:{i}:{base_config.name}".encode()).hexdigest()[:8]
                    repair_id = f"repair-{failure_type.value.lower()}-{digest}"
                    proposal = factory(base_config, repair_id)
                    if proposal is not None:
                        proposals.append(proposal)
            return proposals
