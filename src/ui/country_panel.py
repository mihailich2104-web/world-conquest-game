"""Панель страны: сводка и действия (строительство, налоги, выбор страны)."""
from __future__ import annotations

from config import COSTS, IDEOLOGY_NAMES
from core import economy
from core.diplomacy import get_relation
from . import SidePanel


class CountryPanel(SidePanel):
    """Информация о выбранной стране; для своей — кнопки управления."""
    NAME = "country"

    def build(self) -> None:
        ctx, st = self.ctx, self.ctx.state
        iso = ctx.selected or ctx.player_iso
        if st is None or iso is None or iso not in st.countries:
            self.add_text("<b>Страна не выбрана</b><br>Кликните по стране на карте.", 3)
            return
        c, own = st.countries[iso], iso == ctx.player_iso
        owner = st.owner.get(iso, iso)
        head = f"<b><font color='#ffd34d'>{c.name}</font></b> — {IDEOLOGY_NAMES.get(c.ideology, c.ideology)}"
        if not c.alive:
            self.add_text(head + f"<br>Оккупирована: {st.countries[owner].name}", 3)
            return
        lines = [head, f"Столица: {c.capital or '—'}",
                 f"Население: {c.population:,.1f} млн   ВВП: {c.gdp:,.0f} млрд $",
                 f"Стабильность: {c.stability:.0f}%   Налог: {c.tax_rate * 100:.0f}%",
                 f"Армия: {c.army}  Флот: {c.navy}  Авиация: {c.airforce}",
                 f"Фабрики: {c.factories}  Укрепления: {c.fort}"]
        if own:
            lines += [f"Казна: {c.treasury:,.0f}  Людские рез.: {c.manpower:,.0f} тыс.",
                      f"Сталь {c.resources['steel']:.0f}  Нефть {c.resources['oil']:.0f}  "
                      f"Еда {c.resources['food']:.0f}  Электр. {c.resources['electronics']:.0f}",
                      f"Чистый доход: {economy.net_income(c):+.1f}/день",
                      f"В строительстве: {len(c.construction)}  В обучении: {len(c.training)}"]
        elif ctx.player_iso and st.player:
            lines.append(f"Отношения с вами: {get_relation(st, iso, ctx.player_iso):+d}")
            if iso in st.player.allies:
                lines.append("<font color='#66dd66'>Союзник</font>")
            if iso in st.player.at_war_with:
                lines.append("<font color='#ff6666'>В состоянии войны</font>")
        self.add_text("<br>".join(lines), len(lines) + 1)

        if ctx.player_iso is None:                       # режим выбора страны
            self.add_button(f"Играть за {c.name}", ctx.start_play, key="btn_play")
        elif own:
            f = COSTS["factory"]
            self.add_button(f"Построить фабрику ({f['treasury']:.0f} казны, {f['steel']:.0f} стали)",
                            lambda: ctx.say(*c.build("factory")), key="btn_factory")
            fo = COSTS["fort"]
            self.add_button(f"Построить укрепление ({fo['treasury']:.0f} казны)",
                            lambda: ctx.say(*c.build("fort")))
            self.add_button("Налог +5%", lambda: self._tax(c, +0.05))
            self.add_button("Налог -5%", lambda: self._tax(c, -0.05))
        else:
            self.add_button("Открыть дипломатию", lambda: ctx.open_panel("diplomacy"))

    def _tax(self, c, delta: float) -> None:
        """Меняет налоговую ставку в пределах 5–60%."""
        c.tax_rate = round(max(0.05, min(0.6, c.tax_rate + delta)), 2)
