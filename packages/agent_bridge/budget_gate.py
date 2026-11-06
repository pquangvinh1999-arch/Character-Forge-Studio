"""Explicit budget and user-approval gate for external paid AI providers.

Architectural Rule: Do not call paid AI APIs without an explicitly configured budget
and user approval.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class BudgetApprovalError(PermissionError):
    """Raised when an operation attempts to call a paid AI API without budget or user approval."""


@dataclass
class BudgetPolicy:
    paid_apis_enabled: bool = False
    user_approved: bool = False
    max_usd_per_job: float = 0.0
    max_usd_session: float = 0.0
    spent_usd_session: float = 0.0
    approved_providers: tuple[str, ...] = ()


class BudgetGate:
    """Enforce zero unapproved paid API spending."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path
        self.policy = BudgetPolicy()
        if config_path and config_path.is_file():
            self._load(config_path)

    def _load(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.policy = BudgetPolicy(
            paid_apis_enabled=bool(data.get("paid_apis_enabled", False)),
            user_approved=bool(data.get("user_approved", False)),
            max_usd_per_job=float(data.get("max_usd_per_job", 0.0)),
            max_usd_session=float(data.get("max_usd_session", 0.0)),
            spent_usd_session=float(data.get("spent_usd_session", 0.0)),
            approved_providers=tuple(data.get("approved_providers", [])),
        )

    def status(self) -> dict[str, Any]:
        return asdict(self.policy)

    def require_approval(self, provider: str, estimated_cost_usd: float) -> None:
        """Raise BudgetApprovalError unless paid APIs, user approval, and budget ceiling allow the call."""
        if not self.policy.paid_apis_enabled:
            raise BudgetApprovalError(
                f"Blocked paid API call to {provider!r}: paid_apis_enabled is False by default."
            )
        if not self.policy.user_approved:
            raise BudgetApprovalError(
                f"Blocked paid API call to {provider!r}: explicit user approval is required."
            )
        if provider not in self.policy.approved_providers:
            raise BudgetApprovalError(
                f"Blocked paid API call to {provider!r}: provider not in approved_providers {self.policy.approved_providers}."
            )
        if estimated_cost_usd > self.policy.max_usd_per_job or self.policy.max_usd_per_job <= 0:
            raise BudgetApprovalError(
                f"Blocked paid API call to {provider!r}: estimated cost ${estimated_cost_usd:.4f} exceeds max_usd_per_job ${self.policy.max_usd_per_job:.4f}."
            )
        if (self.policy.spent_usd_session + estimated_cost_usd) > self.policy.max_usd_session:
            raise BudgetApprovalError(
                f"Blocked paid API call to {provider!r}: session budget ${self.policy.max_usd_session:.4f} would be exceeded."
            )


_DEFAULT_BUDGET_GATE: BudgetGate | None = None


def get_budget_gate() -> BudgetGate:
    global _DEFAULT_BUDGET_GATE
    if _DEFAULT_BUDGET_GATE is None:
        _DEFAULT_BUDGET_GATE = BudgetGate()
    return _DEFAULT_BUDGET_GATE
