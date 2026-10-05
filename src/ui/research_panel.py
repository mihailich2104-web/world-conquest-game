"""Панель исследований: 5 веток × 6 уровней."""
from __future__ import annotations

from config import RESEARCH_SLOTS
from core import research as rs
from . import SidePanel


class ResearchPanel(SidePanel):
    """Текущие исследования и кнопки запуска следующей технологии каждой ветки."""
    NAME = "research"

    def build(self) -> None:
        c = self.ctx.state.player if self.ctx.state else None
        if c is None:
            return
        tree = rs.get_tree()
        cur = [f"{tree.techs[t].name}: {p:.0f}/{tree.techs[t].cost}" for t, p in c.researching]
        pts = rs.research_points(c)
        lines = [f"<b>Исследования</b> (слоты {len(c.researching)}/{RESEARCH_SLOTS}, {pts:.1f} очк./день)"]
        lines += cur or ["Нет активных исследований"]
        self.add_text("<br>".join(lines), len(lines) + 1)
        for br, ru in rs.BRANCH_NAMES.items():
            t = tree.next_in_branch(c, br)
            n = rs.tech_levels(c, br)
            if t is None:
                self.add_button(f"{ru} {n}/6 — ветка изучена", lambda: None, enabled=False, h=38)
            else:
                busy = any(r[0] == t.id for r in c.researching)
                self.add_button(f"{ru} {n}/6: {t.name} ({t.cost} оч.)" + (" …" if busy else ""),
                                (lambda tid=t.id: self.ctx.say(*c.research(tid))), enabled=not busy, h=38)
