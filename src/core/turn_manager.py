"""Пошаговый ход (1 ход = 1 день): экономика → производство → рекрутинг → исследования → бои → ИИ."""
from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from config import AUTOSAVE_EVERY_DAYS, SETTINGS
from datetime import timedelta
from . import diplomacy, military, research
from .game_state import GameState, save_game
from .war import resolve_day

if TYPE_CHECKING:
    from .country import Country

log = logging.getLogger(__name__)
BRANCH_PRIORITY = ("industry", "infantry", "tanks", "air", "navy")


class AIController:
    """Простой ИИ: развитие экономики, дипломатия, редкие войны с более слабыми соседями."""

    def __init__(self, state: GameState) -> None:
        self.s = state

    def act(self, c: "Country") -> None:
        """Решения одной страны на один день."""
        rng = self.s.rng
        if rng.random() < 0.2:
            self._economy(c)
        if rng.random() < 0.05:
            self._diplomacy(c)
        self._war(c)

    def _economy(self, c: "Country") -> None:
        """Исследования, найм и строительство."""
        tree = research.get_tree()
        for br in BRANCH_PRIORITY:
            if len(c.researching) >= 2:
                break
            t = tree.next_in_branch(c, br)
            if t and not any(r[0] == t.id for r in c.researching):
                c.research(t.id)
        desired = int(math.sqrt(c.population) * 1.5) + c.factories // 2
        if c.at_war_with:
            desired = int(desired * 1.5)
        if c.army + c.pending("army") < desired:
            c.recruit("army")
        elif c.factories + c.pending("factory") < max(1, int(c.gdp ** 0.45)) and c.treasury > 150:
            c.build("factory")
        elif c.fort + c.pending("fort") < 2 and c.treasury > 200:
            c.build("fort")
        elif c.treasury > 400:
            c.recruit(self.s.rng.choice(("air", "navy")))

    def _diplomacy(self, c: "Country") -> None:
        """Улучшение отношений, торговля, пакты и союзы с соседями."""
        nbs = [n for n in self.s.neighbors(c.iso) if n != self.s.player_iso and n not in c.at_war_with]
        if not nbs:
            return
        t = self.s.rng.choice(sorted(nbs))
        diplomacy.improve_relations(self.s, c.iso, t)
        diplomacy.propose_trade(self.s, c.iso, t)
        diplomacy.propose_pact(self.s, c.iso, t)
        if self.s.rng.random() < 0.3:
            diplomacy.propose_alliance(self.s, c.iso, t)

    def _war(self, c: "Country") -> None:
        """Мир при проигрыше и агрессия против более слабых соседей."""
        from . import war as warmod
        rng, s = self.s.rng, self.s
        if c.at_war_with:
            if rng.random() < 0.1:
                for w in list(s.wars):
                    if w.side_of(c.iso) and w.score_for(c.iso) <= -30:
                        enemy = w.enemy_main(c.iso)
                        if enemy != s.player_iso:
                            diplomacy.propose_peace(s, c.iso, enemy)
            return
        aggr = SETTINGS.ai_aggression
        if aggr <= 0 or c.army < 3 or rng.random() > 0.004 * aggr:
            return
        mine = military.combat_power(c)
        cands = []
        for n in s.neighbors(c.iso):
            t = s.countries[n]
            if (s.tutorial and n == s.player_iso) or n in c.allies or t.at_war_with:
                continue
            if mine >= 1.8 * military.combat_power(t, True) and not diplomacy.truce_left(s, c.iso, n):
                cands.append(n)
        if cands:
            diplomacy.declare_war(s, c.iso, rng.choice(sorted(cands)))


class TurnManager:
    """Продвигает игру на один и более дней."""

    def __init__(self, state: GameState) -> None:
        self.state = state
        self.ai = AIController(state)

    def next_turn(self) -> None:
        """Один день: экономика → производство → рекрутинг → исследования → бои → ИИ."""
        s = self.state
        if s.game_over:
            return
        s.date += timedelta(days=1)
        alive = s.alive_countries()
        for c in alive:                                   # экономика + производство
            for m in c.production_tick():
                if c.iso == s.player_iso:
                    s.log_event(m, c.iso)
        for c in alive:                                   # рекрутинг
            for m in military.training_tick(c):
                if c.iso == s.player_iso:
                    s.log_event(m, c.iso)
        for c in alive:                                   # исследования
            for m in research.research_tick(c):
                if c.iso == s.player_iso:
                    s.log_event(m, c.iso, True)
        for w in list(s.wars):                            # бои
            if w in s.wars:
                resolve_day(s, w)
        for c in s.alive_countries():                     # ИИ
            if c.iso != s.player_iso:
                self.ai.act(c)
        s.check_victory()
        if SETTINGS.autosave and s.player_iso and s.date.toordinal() % AUTOSAVE_EVERY_DAYS == 0:
            save_game(s, "Автосохранение")

    def advance(self, days: int = 1) -> None:
        """Продвигает игру на несколько дней."""
        for _ in range(days):
            self.next_turn()
