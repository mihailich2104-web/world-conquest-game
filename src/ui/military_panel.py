"""Панель армии: состав, найм, войны и мир."""
from __future__ import annotations

from config import COSTS
from core import military
from core.war import find_war
from . import SidePanel


class MilitaryPanel(SidePanel):
    """Состав сил, очередь обучения и текущие войны."""
    NAME = "military"

    def build(self) -> None:
        st = self.ctx.state
        c = st.player if st else None
        if c is None:
            return
        lines = [f"<b>Вооружённые силы</b>",
                 f"Дивизии: {c.army} (+{c.pending('army')})  Флот: {c.navy} (+{c.pending('navy')})  "
                 f"Авиация: {c.airforce} (+{c.pending('air')})",
                 f"Мораль: {c.morale * 100:.0f}%  Снабжение: {military.supply_factor(c) * 100:.0f}%",
                 f"Боевая мощь: {military.combat_power(c):.1f}  Людские рез.: {c.manpower:.0f} тыс."]
        for w in st.wars:
            if w.side_of(c.iso):
                en = st.countries[w.enemy_main(c.iso)]
                lines.append(f"<font color='#ff8888'>Война с {en.name}: счёт {w.score_for(c.iso):+.0f}, день {w.days}</font>")
        self.add_text("<br>".join(lines), len(lines) + 2)
        a, n, f = COSTS["army"], COSTS["navy"], COSTS["air"]
        self.add_button(f"Нанять дивизию ({a['treasury']:.0f} казны, {a['steel']:.0f} стали)",
                        lambda: ctx_say(self, c.recruit("army")), key="btn_recruit_army")
        self.add_button(f"Построить корабль ({n['treasury']:.0f} казны)", lambda: ctx_say(self, c.recruit("navy")))
        self.add_button(f"Нанять эскадрилью ({f['treasury']:.0f} казны)", lambda: ctx_say(self, c.recruit("air")))
        for w in [w for w in st.wars if w.side_of(c.iso)][:3]:
            en = w.enemy_main(c.iso)
            self.add_button(f"Предложить мир: {st.countries[en].name}",
                            (lambda e=en: ctx_say(self, c.propose_peace(st, e))))


def ctx_say(panel: SidePanel, result: tuple[bool, str]) -> None:
    """Передаёт результат действия в журнал."""
    panel.ctx.say(*result)
