"""Панель дипломатии: действия с выбранной страной."""
from __future__ import annotations

from core import diplomacy as dip
from core.war import find_war
from . import SidePanel


class DiplomacyPanel(SidePanel):
    """Улучшение отношений, торговля, пакты, союзы, война и мир."""
    NAME = "diplomacy"

    def build(self) -> None:
        ctx, st = self.ctx, self.ctx.state
        me, tgt = ctx.player_iso, ctx.selected
        if st is None or me is None:
            return
        if tgt is None or tgt == me or tgt not in st.countries or not st.countries[tgt].alive:
            self.add_text("<b>Дипломатия</b><br>Выберите на карте другую страну.", 3)
            return
        a, b = st.countries[me], st.countries[tgt]
        tags = []
        if tgt in a.allies: tags.append("союзник")
        if tgt in a.pacts: tags.append("пакт о ненападении")
        if tgt in a.trade: tags.append("торговое соглашение")
        if tgt in a.at_war_with: tags.append("<font color='#ff6666'>ВОЙНА</font>")
        left = dip.truce_left(st, me, tgt)
        if left: tags.append(f"перемирие {left} дн.")
        rel = dip.get_relation(st, tgt, me)
        lines = [f"<b><font color='#ffd34d'>{b.name}</font></b>",
                 f"Отношения: {rel:+d}", f"Статус: {', '.join(tags) or 'нет соглашений'}",
                 f"Армия {b.army} / ваша {a.army}",
                 f"Общая граница: {'да' if tgt in st.neighbors(me) else 'нет'}"]
        w = find_war(st, me, tgt)
        if w:
            lines.append(f"Счёт войны для вас: {w.score_for(me):+.0f}  (день {w.days})")
        self.add_text("<br>".join(lines), len(lines) + 1)
        at_war = tgt in a.at_war_with
        self.add_button("Улучшить отношения (10 казны)", lambda: ctx.say(*dip.improve_relations(st, me, tgt)), enabled=not at_war)
        self.add_button("Торговое соглашение", lambda: ctx.say(*dip.propose_trade(st, me, tgt)), enabled=not at_war)
        self.add_button("Пакт о ненападении", lambda: ctx.say(*dip.propose_pact(st, me, tgt)), enabled=not at_war)
        if tgt in a.allies:
            self.add_button("Расторгнуть союз", lambda: ctx.say(*dip.break_alliance(st, me, tgt)))
        else:
            self.add_button("Предложить союз", lambda: ctx.say(*dip.propose_alliance(st, me, tgt)), enabled=not at_war)
        if at_war:
            self.add_button("Предложить мир", lambda: ctx.say(*a.propose_peace(st, tgt)), key="btn_peace")
        else:
            self.add_button("Объявить войну", lambda: ctx.say(*a.declare_war(st, tgt)), key="btn_war")
