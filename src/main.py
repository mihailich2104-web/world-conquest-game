"""Точка входа World Conquest: инициализация, главный цикл events → update → render."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))   # импорты вида `from core import ...`

import pygame
import pygame_gui

from config import (AUTO_TURN_SECONDS, COUNTRIES_PATH, FPS, HUD_HEIGHT, SETTINGS, SIDE_PANEL_W,
                    TITLE, TUTORIAL_H, USER_DIR, WINDOW_SIZE)
from core.game_state import GameState, list_saves, load_game, save_game
from core.turn_manager import TurnManager
from map.camera import Camera
from map.map_loader import load_world
from map.map_renderer import MapRenderer
from tutorial.tutor_engine import TutorContext, TutorEngine
from ui import UIContext, get_font
from ui.country_panel import CountryPanel
from ui.diplomacy_panel import DiplomacyPanel
from ui.hud import HUD
from ui.main_menu import MainMenu
from ui.military_panel import MilitaryPanel
from ui.research_panel import ResearchPanel
from ui.tutorial import TutorialOverlay

log = logging.getLogger("world_conquest")


def setup_logging() -> None:
    """Логирование в консоль и в файл ~/.world_conquest/game.log."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        USER_DIR.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(USER_DIR / "game.log", encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=handlers)


class App:
    """Приложение: меню, выбор страны, игровой экран."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = self._set_mode()
        self.size = WINDOW_SIZE
        self.manager = pygame_gui.UIManager(self.size)
        self.ctx = UIContext(self.manager, self.size)
        self.clock = pygame.time.Clock()
        try:
            self.countries: list[dict[str, Any]] = json.loads(COUNTRIES_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.exception("countries.json не найден — запустите tools/gen_countries.py")
            self.countries = []
        self.provs, self.adj, self.fallback_map = load_world(self.countries)
        self.camera = Camera(*self.size)
        self.renderer = MapRenderer(self.provs, self.camera, get_font(13))
        self.mode = "menu"
        self.running = True
        self.menu: Optional[MainMenu] = MainMenu(self.manager, self.size)
        # игровое
        self.state: Optional[GameState] = None
        self.tm: Optional[TurnManager] = None
        self.hud: Optional[HUD] = None
        self.panels: dict[str, Any] = {}
        self.active: Optional[str] = None
        self.hover: Optional[str] = None
        self.auto = False
        self.auto_t = 0.0
        self.drag_start: Optional[tuple[int, int]] = None
        self.dragging = False
        self.press_on_ui = False
        self.engine: Optional[TutorEngine] = None
        self.overlay: Optional[TutorialOverlay] = None
        self.tctx: Optional[TutorContext] = None
        self.btn_over: Optional[Any] = None
        self.ctx.open_panel = self.open_panel
        self.ctx.refresh = self.refresh_ui
        self.ctx.start_play = self.start_play

    # ---------- окно ----------
    def _set_mode(self) -> pygame.Surface:
        flags = pygame.SCALED | (pygame.FULLSCREEN if SETTINGS.fullscreen else 0)
        return pygame.display.set_mode(WINDOW_SIZE, flags)

    # ---------- переходы ----------
    def new_game(self, tutorial: bool) -> None:
        """Создаёт партию и переходит к выбору страны."""
        if not self.countries and not self.provs:
            return
        provs = [(p.iso, p.name, p.continent) for p in self.provs]
        state = GameState.new(self.countries, provs, self.adj, tutorial=tutorial)
        self.enter_game(state)

    def enter_game(self, state: GameState) -> None:
        """Строит игровой UI вокруг состояния."""
        self.leave_game()
        if self.menu:
            self.menu.kill()
            self.menu = None
        self.state, self.mode = state, "play"
        self.ctx.state, self.ctx.selected = state, state.player_iso
        self.tm = TurnManager(state)
        self.hud = HUD(self.ctx)
        self.panels = {p.NAME: p for p in (CountryPanel(self.ctx), DiplomacyPanel(self.ctx),
                                           ResearchPanel(self.ctx), MilitaryPanel(self.ctx))}
        self.active, self.auto, state.map_dirty = None, False, True
        self.renderer.pulse = 0.0
        if state.player_iso:
            self.focus_player(2.0)
            self.open_panel("country")
        else:
            self.camera.focus(1800, 700, 0.6)
            self.open_panel("country")
            if state.tutorial:
                self.tctx = TutorContext(self.ctx.reg, self.renderer, self.camera)
                self.tctx.state, self.tctx.open_panel, self.tctx.select = state, self.open_panel, self.select
                self.engine = TutorEngine(self.tctx)
                self.overlay = TutorialOverlay(self.ctx, self.engine)

    def leave_game(self) -> None:
        """Убирает игровой UI."""
        if self.hud:
            for p in self.panels.values():
                p.close()
            self.hud.kill()
        if self.overlay:
            self.overlay.kill()
        if self.btn_over is not None:
            self.btn_over.kill()
            self.btn_over = None
        self.hud, self.panels, self.overlay, self.engine, self.tctx = None, {}, None, None, None
        self.active = None
        self.ctx.reg.clear()
        self.state = self.tm = None
        self.ctx.state = None

    def to_menu(self) -> None:
        """Возврат в главное меню (с автосохранением)."""
        if self.state and self.state.player_iso and not self.state.game_over and SETTINGS.autosave:
            save_game(self.state, "Автосохранение")
        self.leave_game()
        self.mode = "menu"
        self.menu = MainMenu(self.manager, self.size)

    def start_play(self) -> None:
        """Подтверждение выбора страны игроком."""
        st = self.state
        if st and self.ctx.selected and st.player_iso is None:
            st.player_iso = self.ctx.selected
            self.focus_player(2.0)
            self.open_panel("country")
            st.log_event(f"Вы играете за: {st.countries[st.player_iso].name}", st.player_iso, True)

    def focus_player(self, zoom: float) -> None:
        """Камера на страну игрока."""
        iso = self.state.player_iso if self.state else None
        if iso and iso in self.renderer.by_iso:
            self.camera.focus(*self.renderer.by_iso[iso].world_centroid, zoom)

    # ---------- панели ----------
    def open_panel(self, name: str) -> None:
        """Открывает панель (остальные закрываются)."""
        for n, p in self.panels.items():
            if n != name:
                p.close()
        if name in self.panels:
            self.panels[name].open()
            self.active = name

    def toggle_panel(self, name: str) -> None:
        """Открыть/закрыть панель кнопкой HUD."""
        if self.active == name and self.panels[name].is_open:
            self.panels[name].close()
            self.active = None
        else:
            self.open_panel(name)

    def refresh_ui(self) -> None:
        """Перестраивает активную панель."""
        if self.active and self.active in self.panels:
            self.panels[self.active].refresh()

    def select(self, iso: Optional[str]) -> None:
        """Выбор страны на карте."""
        if iso is None:
            return
        self.ctx.selected = iso
        if self.active is None:
            self.open_panel("country")
        else:
            self.refresh_ui()

    def over_ui(self, pos: tuple[int, int]) -> bool:
        """Находится ли точка над элементами интерфейса."""
        if self.mode != "play" or not self.hud:
            return False
        if self.hud.rect.collidepoint(pos):
            return True
        if self.active and self.panels[self.active].is_open and self.panels[self.active].rect.collidepoint(pos):
            return True
        if self.overlay and not (self.engine and self.engine.finished) and self.overlay.box.collidepoint(pos):
            return True
        return bool(self.state and self.state.game_over)

    # ---------- события ----------
    def handle(self, e: pygame.event.Event) -> None:
        """Диспетчер событий."""
        if e.type == pygame.QUIT:
            self.running = False
            return
        self.manager.process_events(e)
        if self.mode == "menu" and self.menu:
            res = self.menu.handle_event(e)
            if res:
                self.menu_action(*res)
            return
        if self.mode != "play" or not self.state or not self.hud:
            return
        if self.overlay and self.overlay.handle_event(e):
            return
        if e.type == pygame_gui.UI_BUTTON_PRESSED and self.btn_over is not None and e.ui_element is self.btn_over:
            self.to_menu()
            return
        act = self.hud.handle_event(e)
        if act:
            self.hud_action(act)
            return
        if self.active and self.panels[self.active].handle_event(e):
            return
        if e.type == pygame.KEYDOWN:
            self.on_key(e.key)
        elif e.type == pygame.MOUSEWHEEL:
            pos = pygame.mouse.get_pos()
            if not self.over_ui(pos):
                self.camera.zoom_at(e.y, *pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.drag_start, self.dragging, self.press_on_ui = e.pos, False, self.over_ui(e.pos)
        elif e.type == pygame.MOUSEMOTION:
            if self.drag_start and e.buttons[0] and not self.press_on_ui:
                if self.dragging or abs(e.pos[0] - self.drag_start[0]) + abs(e.pos[1] - self.drag_start[1]) > 5:
                    self.dragging = True
                    self.camera.pan(*e.rel)
            elif not self.over_ui(e.pos):
                self.hover = self.renderer.province_at(e.pos)
            else:
                self.hover = None
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if self.drag_start and not self.dragging and not self.press_on_ui:
                self.select(self.renderer.province_at(e.pos))
            self.drag_start = None

    def on_key(self, key: int) -> None:
        """Горячие клавиши."""
        if key == pygame.K_SPACE:
            self.end_turn()
        elif key == pygame.K_ESCAPE:
            self.to_menu()
        elif key == pygame.K_a:
            self.auto = not self.auto
        elif key == pygame.K_m:
            self.hud_action("map_mode")
        elif key == pygame.K_F5:
            self.hud_action("save")
        elif key == pygame.K_F9 and self.menu is None:
            self.menu_action("load", None)
        elif key == pygame.K_c:
            self.focus_player(2.0)

    def end_turn(self) -> None:
        """Один игровой день."""
        if self.tm and self.state and self.state.player_iso and not self.state.game_over:
            self.tm.next_turn()
            self.refresh_ui()

    def hud_action(self, act: str) -> None:
        """Действия кнопок HUD."""
        st = self.state
        if act.startswith("panel:"):
            self.toggle_panel(act.split(":", 1)[1])
        elif act == "next_turn":
            self.end_turn()
        elif act == "auto":
            self.auto = not self.auto
        elif act == "map_mode":
            SETTINGS.map_mode = "political" if SETTINGS.map_mode == "ideology" else "ideology"
            SETTINGS.save()
            if st:
                st.map_dirty = True
        elif act == "save" and st and st.player_iso:
            sid = save_game(st, "Ручное сохранение")
            st.log_event("Игра сохранена" if sid else "✖ Не удалось сохранить", st.player_iso)
        elif act == "menu":
            self.to_menu()

    def menu_action(self, action: str, data: Any) -> None:
        """Действия главного меню."""
        if action == "new":
            self.new_game(False)
        elif action == "tutorial":
            self.new_game(True)
        elif action == "load_menu" and self.menu:
            self.menu.show_load(list_saves())
        elif action == "load":
            self.load(data)
        elif action == "apply_display":
            self.screen = self._set_mode()
            if self.menu:
                self.menu.show_settings()
        elif action == "quit":
            self.running = False

    def load(self, save_id: Optional[int]) -> None:
        """Загружает сохранение (None — последнее)."""
        if save_id is None:
            saves = list_saves(1)
            if not saves:
                return
            save_id = saves[0]["id"]
        st = load_game(save_id, self.adj)
        if st is None or set(st.owner) != {p.iso for p in self.provs}:
            log.error("Сохранение несовместимо с текущей картой или повреждено")
            return
        self.enter_game(st)

    # ---------- кадр ----------
    def update(self, dt: float) -> None:
        """Обновление логики."""
        self.manager.update(dt)
        if self.mode != "play" or not self.state or not self.hud:
            return
        if self.engine:
            self.engine.update()
            if self.overlay:
                self.overlay.update()
            if self.engine.finished and self.state.tutorial:
                self.state.tutorial = False
        if self.auto and self.state.player_iso and not self.state.game_over:
            self.auto_t += dt
            if self.auto_t >= AUTO_TURN_SECONDS:
                self.auto_t = 0.0
                self.end_turn()
        if self.state.game_over and self.btn_over is None:
            self.btn_over = pygame_gui.elements.UIButton(
                pygame.Rect(self.size[0] // 2 - 120, self.size[1] // 2 + 20, 240, 44), "В главное меню", self.manager)
        self.hud.update(self.auto)

    def render(self, dt: float) -> None:
        """Отрисовка кадра."""
        if self.mode == "menu" and self.menu:
            self.menu.draw(self.screen)
            self.manager.draw_ui(self.screen)
            return
        st = self.state
        if not st or not self.hud:
            return
        extra = self.engine.extra_countries() if self.engine and not self.engine.finished else ()
        self.renderer.draw(self.screen, st, self.hover, self.ctx.selected, extra)
        if st.player_iso and self.engine and not self.engine.finished and self.engine.step and \
                self.engine.step.id in ("capital",):
            self.renderer.draw_marker(self.screen, st.player_iso, dt)
        side = bool(self.active and self.panels[self.active].is_open)
        tut = bool(self.overlay and self.engine and not self.engine.finished)
        bottom = self.size[1] - (TUTORIAL_H + 16 if tut else 0)
        self.hud.draw_log(self.screen, bottom, side)
        if self.hover and self.hover in st.countries:
            name = st.countries[st.owner.get(self.hover, self.hover)].name
            t = get_font(15).render(name, True, (255, 255, 255))
            mx, my = pygame.mouse.get_pos()
            pygame.draw.rect(self.screen, (0, 0, 0), (mx + 12, my + 10, t.get_width() + 8, t.get_height() + 4))
            self.screen.blit(t, (mx + 16, my + 12))
        if tut and self.overlay:
            self.overlay.draw_box(self.screen)
        self.manager.draw_ui(self.screen)
        if tut and self.overlay:
            self.overlay.draw_highlight(self.screen, pygame.Rect(
                0, HUD_HEIGHT, self.size[0] - (SIDE_PANEL_W if side else 0), self.size[1] - HUD_HEIGHT))
        if st.game_over:
            txt = "ПОБЕДА — вы владеете миром!" if st.game_over == "victory" else "ПОРАЖЕНИЕ — ваша страна пала"
            t = get_font(40).render(txt, True, (255, 215, 0) if st.game_over == "victory" else (255, 90, 90))
            self.screen.blit(t, ((self.size[0] - t.get_width()) // 2, self.size[1] // 2 - 40))

    def run(self) -> None:
        """Главный цикл."""
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            try:
                for e in pygame.event.get():
                    self.handle(e)
                self.update(dt)
                self.render(dt)
            except Exception:
                log.exception("Необработанная ошибка в кадре")
            pygame.display.flip()
        if self.state and self.state.player_iso and not self.state.game_over and SETTINGS.autosave:
            save_game(self.state, "Автосохранение")
        pygame.quit()


def main() -> None:
    """Запуск приложения."""
    setup_logging()
    try:
        App().run()
    except Exception:
        log.exception("Критическая ошибка")
        raise


if __name__ == "__main__":
    main()
