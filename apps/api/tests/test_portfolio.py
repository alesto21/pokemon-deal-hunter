from __future__ import annotations

from app.core.config import BinderModifiers
from app.db.models import Card, PortfolioItem
from app.portfolio.modifiers import PortfolioState, portfolio_modifier
from app.portfolio.service import portfolio_state_for_card, portfolio_summary, value_holdings

M = BinderModifiers()


def test_duplicate_in_premium_penalty():
    pm = portfolio_modifier(PortfolioState(owned_quantity=1, owned_in_premium=True), 0.2, "premium", M)
    assert pm.points == -8


def test_duplicate_exceptional_discount_no_penalty():
    pm = portfolio_modifier(PortfolioState(owned_quantity=1, owned_in_premium=True), 0.36, "premium", M)
    assert pm.points == 0


def test_missing_high_priority_bonus():
    pm = portfolio_modifier(PortfolioState(is_high_priority=True, owns_pokemon_in_binder=True), 0.2, "premium", M)
    assert pm.items == {"missing_high_priority": 8}


def test_iconic_missing_theme_and_diversification():
    st = PortfolioState(is_high_priority=True, is_iconic=True, owns_pokemon_in_binder=False,
                        theme_name="eeveelutions", theme_owned=3, theme_size=9, distinct_pokemon_owned=4)
    pm = portfolio_modifier(st, 0.2, "premium", M)
    assert pm.items == {"missing_high_priority": 8, "iconic_missing": 5, "completes_theme": 5,
                        "diversification": 3}
    assert pm.points == M.max_total_bonus  # capped at 15


def test_portfolio_state_from_db(session, cfg):
    eevee = Card(name="Eevee", pokemon_name="Eevee", set_code="TWM", card_number="188/167", source_ids={})
    umbreon = Card(name="Umbreon ex", pokemon_name="Umbreon", set_code="PRE", card_number="161/131", source_ids={})
    sylveon = Card(name="Sylveon ex", pokemon_name="Sylveon", set_code="PRE", card_number="156/131", source_ids={})
    session.add_all([eevee, umbreon, sylveon])
    session.flush()
    session.add_all([PortfolioItem(card_id=umbreon.id, binder_type="premium", acquisition_price_nok=3000),
                     PortfolioItem(card_id=sylveon.id, binder_type="premium", acquisition_price_nok=1500)])
    session.flush()
    st = portfolio_state_for_card(session, eevee, cfg)
    assert st.owned_quantity == 0 and st.is_high_priority and st.is_iconic
    assert st.theme_name == "eeveelutions" and st.theme_owned == 2
    own = portfolio_state_for_card(session, umbreon, cfg)
    assert own.owned_quantity == 1 and own.owned_in_premium


def test_portfolio_valuation(session):
    c = Card(name="Gastly", pokemon_name="Gastly", set_code="TEF", card_number="177/162", source_ids={})
    session.add(c)
    session.flush()
    session.add(PortfolioItem(card_id=c.id, quantity=2, acquisition_price_nok=600, binder_type="premium"))
    session.flush()
    hs = value_holdings(session, lambda t, i: 900.0)
    s = portfolio_summary(session, hs)
    assert s["total_cost_nok"] == 1200 and s["raw_value_nok"] == 1800
    assert s["unrealized_gain_nok"] == 600 and s["by_binder"] == {"premium": 1800}
