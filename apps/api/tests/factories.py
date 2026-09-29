"""Build EvaluationContext objects from the JSON scenario fixtures."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.portfolio.modifiers import PortfolioState
from app.pricing.fair_value import FairValue
from app.pricing.history import HistoryStats
from app.scoring.context import EvaluationContext

SCENARIOS = json.loads((Path(__file__).parent / "fixtures" / "sample_listings.json").read_text())


def make_ctx(name: str, **overrides) -> EvaluationContext:
    data = {**SCENARIOS[name], **overrides}
    fv = data.pop("fair_value")
    conf = data.pop("fv_confidence", 0.9)
    hist = HistoryStats(**data.pop("history", {}))
    pf = PortfolioState(**data.pop("portfolio", {}))
    if data.get("release_date"):
        data["release_date"] = date.fromisoformat(data["release_date"])
    return EvaluationContext(
        **data, history=hist, portfolio=pf,
        fair_value=FairValue(fv, fv * 0.92, fv * 1.08, conf, []) if fv else None,
    )
