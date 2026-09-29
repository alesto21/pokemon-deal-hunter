"""Human-readable Telegram messages (HTML parse mode — every dynamic value is escaped)."""

from __future__ import annotations

from html import escape

from app.scoring.context import EvaluationContext
from app.scoring.engine import ScoreResult

EMOJI = {"GOOD": "👀", "STRONG_BUY": "🔥", "STEAL": "🚨"}
LABEL = {"GOOD": "GOOD", "STRONG_BUY": "STRONG BUY", "STEAL": "STEAL"}


def nok(v: float | None) -> str:
    return "—" if v is None else f"{v:,.0f} NOK".replace(",", " ")


def _level(score: float) -> str:
    return "High" if score >= 0.7 else "Medium" if score >= 0.4 else "Low"


def format_deal_alert(ctx: EvaluationContext, result: ScoreResult, severity: str, source_label: str) -> str:
    e = escape
    fv = ctx.fair_value
    h = ctx.history
    lines = [f"{EMOJI.get(severity, '')} <b>{LABEL.get(severity, severity)} — {result.total_score:.0f}/100</b>", ""]
    title = ctx.entity_name or ctx.title
    if ctx.card_number:
        title = f"{title} {ctx.card_number}"
    lines.append(f"<b>{e(title)}</b>")
    if ctx.set_name:
        lines.append(e(ctx.set_name))
    lines += ["", f"Source: {e(source_label)}",
              f"Price: {nok(ctx.listing_price_nok if ctx.listing_price_nok is not None else ctx.total_price_nok)}",
              f"Shipping: {nok(ctx.shipping_nok)}",
              f"Total: {nok(ctx.total_price_nok)}"]
    lines += ["", f"Fair value: {nok(fv.fair_value_nok if fv else None)}"
              f" ({nok(fv.fair_value_low if fv else None)}–{nok(fv.fair_value_high if fv else None)})",
              f"Discount: {result.discount_pct:.1%}" if result.discount_pct is not None else "Discount: —"]
    if h.median_30d:
        lines.append(f"30d median: {nok(h.median_30d)}")
    if h.trend_30d is not None:
        lines.append(f"30d trend: {h.trend_30d:+.1%}")
    owned = ctx.portfolio.owned_quantity
    lines += ["", f"Liquidity: {_level(result.components.get('liquidity', 0))}",
              f"Binder fit: {result.binder_fit.capitalize()}",
              f"Already owned: {f'Yes ({owned})' if owned else 'No'}"]
    if result.grading and result.grading.psa10_nok:
        g = result.grading
        lines += ["", f"PSA9 ref: {nok(g.psa9_nok)}", f"PSA10 ref: {nok(g.psa10_nok)}",
                  f"Grading upside: {e(g.label)}"]
    if result.sealed:
        s = result.sealed
        lines += [""]
        if s.price_per_pack_nok:
            lines.append(f"Per pack: {nok(s.price_per_pack_nok)} ({s.pack_count} packs)")
        lines.append(f"Rip score: {s.rip_score:.2f} · Sealed hold score: {s.sealed_investment_score:.2f}")
    if result.reasons:
        lines += ["", "<b>Why:</b>"] + [f"• {e(r)}" for r in result.reasons[:6]]
    if result.warnings:
        lines += ["", "<b>Caveats:</b>"] + [f"• {e(w)}" for w in result.warnings[:4]]
    return "\n".join(lines)
