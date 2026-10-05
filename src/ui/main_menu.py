"""Главное меню: Новая игра / Обучение / Загрузить / Настройки / Выход."""
from __future__ import annotations

import logging
from typing import Any, Optional

import pygame
import pygame_gui
from pygame_gui.elements import UIButton

from config import SETTINGS, TITLE
from . import get_font

log = logging.getLogger(__name__)
AGGR = ((0.0, "Мирный"), (0.5, "Низкая"), (1.0, "Обычная"), (2.0, "Высокая"))


class MainMenu:
    """Меню с подменю загрузки и настроек. handle_event → (действие, данные) или None."""

    def __init__(self, manager: pygame_gui.UIManager, size: tuple[int, int]) -> None:
        self.m, self.size = manager, size
        self.buttons: dict[UIButton, tuple[str, Any]] = {}
        self.show_main()

    def _clear(self) -> None:
        for b in self.buttons:
            b.kill()
        self.buttons.clear()

    def _add(self, items: list[tuple[str, str, Any]]) -> None:
        w, h, gap = 360, 46, 12
        x = (self.size[0] - w) // 2
        y = 210
        for text, action, data in items:
            b = UIButton(pygame.Rect(x, y, w, h), text, self.m)
            self.buttons[b] = (action, data)
            y += h + gap

    def kill(self) -> None:
        """Удаляет все элементы меню."""
        self._clear()

    def show_main(self) -> None:
        """Корневое меню."""
        self._clear()
        self._add([("Новая игра", "new", None), ("Обучение", "tutorial", None),
                   ("Загрузить", "load_menu", None), ("Настройки", "settings", None), ("Выход", "quit", None)])

    def show_load(self, saves: list[dict[str, Any]]) -> None:
        """Список последних сохранений."""
        self._clear()
        items = [(f"{s['name']} | {s['player']} | {s['game_date']}", "load", s["id"]) for s in saves]
        self._add(items + [("Назад", "main", None)] if saves else [("Сохранений нет", "main", None)])

    def show_settings(self) -> None:
        """Настройки."""
        self._clear()
        aggr = next((n for v, n in AGGR if v == SETTINGS.ai_aggression), "Обычная")
        self._add([
            (f"Полный экран: {'вкл' if SETTINGS.fullscreen else 'выкл'}", "toggle_fullscreen", None),
            (f"Агрессия ИИ: {aggr}", "toggle_aggr", None),
            (f"Режим карты: {'идеологии' if SETTINGS.map_mode == 'ideology' else 'политический'}", "toggle_map", None),
            (f"Автосохранение: {'вкл' if SETTINGS.autosave else 'выкл'}", "toggle_autosave", None),
            ("Назад", "main", None)])

    def handle_event(self, event: pygame.event.Event) -> Optional[tuple[str, Any]]:
        """Обрабатывает кнопки; внутренние переключатели применяет сам."""
        if event.type != pygame_gui.UI_BUTTON_PRESSED or event.ui_element not in self.buttons:
            return None
        action, data = self.buttons[event.ui_element]
        if action == "main":
            self.show_main()
        elif action == "settings":
            self.show_settings()
        elif action == "toggle_aggr":
            vals = [v for v, _ in AGGR]
            i = vals.index(SETTINGS.ai_aggression) if SETTINGS.ai_aggression in vals else 2
            SETTINGS.ai_aggression = vals[(i + 1) % len(vals)]
            SETTINGS.save()
            self.show_settings()
        elif action == "toggle_map":
            SETTINGS.map_mode = "political" if SETTINGS.map_mode == "ideology" else "ideology"
            SETTINGS.save()
            self.show_settings()
        elif action == "toggle_autosave":
            SETTINGS.autosave = not SETTINGS.autosave
            SETTINGS.save()
            self.show_settings()
        elif action == "toggle_fullscreen":
            SETTINGS.fullscreen = not SETTINGS.fullscreen
            SETTINGS.save()
            return "apply_display", None
        else:
            return action, data
        return None

    def draw(self, screen: pygame.Surface) -> None:
        """Фон и заголовок."""
        screen.fill((14, 24, 44))
        t = get_font(56).render(TITLE, True, (255, 215, 0))
        screen.blit(t, ((self.size[0] - t.get_width()) // 2, 90))
        s = get_font(18).render("Глобальная пошаговая стратегия", True, (190, 200, 220))
        screen.blit(s, ((self.size[0] - s.get_width()) // 2, 160))
