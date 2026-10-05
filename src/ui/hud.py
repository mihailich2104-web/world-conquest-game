"""HUD: дата, ресурсы, стабильность и кнопки панелей/хода."""
from __future__ import annotations

import logging
from typing import Optional

import pygame
import pygame_gui
from pygame_gui.elements import UIButton, UILabel, UIPanel

from config import HUD_HEIGHT, RESOURCE_NAMES, SETTINGS, SIDE_PANEL_W
from core import economy
from . import UIContext, get_font

log = logging.getLogger(__name__)
MONTHS = ("янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")


class HUD:
    """Верхняя панель. handle_event возвращает имя действия или None."""

    def __init__(self, ctx: UIContext) -> None:
        self.ctx = ctx
        self._cache: dict = {}
        w = ctx.size[0]
        m = ctx.manager
        self.panel = UIPanel(pygame.Rect(0, 0, w, HUD_HEIGHT), starting_height=3, manager=m)
        self.lbl_date = UILabel(pygame.Rect(4, 4, 150, 30), "", m, self.panel)
        self.lbl_money = UILabel(pygame.Rect(158, 4, 230, 30), "", m, self.panel)
        self.lbl_res = UILabel(pygame.Rect(392, 4, 520, 30), "", m, self.panel)
        self.lbl_stab = UILabel(pygame.Rect(916, 4, 340, 30), "", m, self.panel)
        self.buttons: dict[UIButton, str] = {}
        x = 4
        spec = [("Страна", "panel:country", "btn_country", 96), ("Дипломатия", "panel:diplomacy", "btn_diplomacy", 118),
                ("Исследования", "panel:research", "btn_research", 130), ("Армия", "panel:military", "btn_military", 90),
                ("Карта", "map_mode", "btn_map", 80), ("Авто: выкл", "auto", "btn_auto", 100),
                ("Сохранить", "save", "btn_save", 104), ("Меню", "menu", "btn_menu", 80),
                ("След. ход (Пробел)", "next_turn", "btn_next_turn", 190)]
        for text, action, key, bw in spec:
            b = UIButton(pygame.Rect(x, 38, bw, 32), text, m, self.panel)
            self.buttons[b] = action
            ctx.reg[key] = b
            x += bw + 6
        self.btn_auto = ctx.reg["btn_auto"]

    def _set(self, el, text: str) -> None:
        """Меняет текст элемента только при изменении (дорогая перерисовка)."""
        if self._cache.get(el) != text:
            self._cache[el] = text
            el.set_text(text)

    @property
    def rect(self) -> pygame.Rect:
        """Область HUD (для блокировки кликов по карте)."""
        return pygame.Rect(0, 0, self.ctx.size[0], HUD_HEIGHT)

    def update(self, auto: bool) -> None:
        """Обновляет подписи по состоянию игры."""
        st = self.ctx.state
        c = st.player if st else None
        if st is None or c is None:
            self._set(self.lbl_date, "")
            self._set(self.lbl_money, "")
            self._set(self.lbl_res, "Выберите страну на карте")
            self._set(self.lbl_stab, "")
            return
        d = st.date
        self._set(self.lbl_date, f"{d.day} {MONTHS[d.month - 1]} {d.year}")
        self._set(self.lbl_money, f"Казна: {c.treasury:,.0f} ({economy.net_income(c):+.1f}/д)".replace(",", " "))
        self._set(self.lbl_res, "   ".join(f"{RESOURCE_NAMES[k]} {c.resources[k]:.0f}" for k in RESOURCE_NAMES))
        self._set(self.lbl_stab, f"Стабильность {c.stability:.0f}%   Мораль {c.morale * 100:.0f}%   Войн: {len(c.at_war_with)}")
        self._set(self.btn_auto, "Авто: вкл" if auto else "Авто: выкл")

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Возвращает действие нажатой кнопки HUD."""
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            return self.buttons.get(event.ui_element)
        return None

    def kill(self) -> None:
        """Удаляет HUD."""
        for k in [k for k in self.ctx.reg if k.startswith("btn_") and k in
                  ("btn_country", "btn_diplomacy", "btn_research", "btn_military", "btn_map", "btn_auto",
                   "btn_save", "btn_menu", "btn_next_turn")]:
            self.ctx.reg.pop(k, None)
        self.panel.kill()

    def draw_log(self, screen: pygame.Surface, bottom: int, side_open: bool) -> None:
        """Последние события в левом нижнем углу карты."""
        st = self.ctx.state
        if not st or not st.log:
            return
        font = get_font(14)
        recent = st.log[-5:]
        width = screen.get_width() - (SIDE_PANEL_W if side_open else 0) - 20
        y = bottom - 8 - len(recent) * 20
        bg = pygame.Surface((min(620, width), len(recent) * 20 + 6), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        screen.blit(bg, (8, y - 3))
        for e in recent:
            col = (255, 220, 120) if e.get("imp") else (230, 230, 230)
            screen.blit(font.render(f"{e['date'][5:]}  {e['text']}", True, col), (14, y))
            y += 20
