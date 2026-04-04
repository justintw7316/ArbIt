"""
Phase 3 — Validation & Adjudication.

Public API:
  Phase3Engine       — main orchestrator
  Phase3Decision     — output per candidate pair
  Verdict            — ACCEPT | REJECT | REVIEW
"""

from algorithm.Phase_3.engine import Phase3Engine
from algorithm.Phase_3.models import Phase3Decision, Verdict

__all__ = ["Phase3Engine", "Phase3Decision", "Verdict"]
