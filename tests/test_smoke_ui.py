"""Дымовой тест без окна: импорт pygame/pygame_gui, создание App и несколько кадров."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    import pygame
    import pygame_gui
    assert hasattr(pygame, "DIRECTION_LTR"), "Нужен pygame-ce, а не pygame (pip uninstall pygame; pip install pygame-ce)"
    import main as game
    app = game.App()
    assert app.provs, "карта не загружена"
    assert not app.fallback_map, "используется запасная карта — нет provinces.geojson"
    for _ in range(5):
        app.manager.update(0.016)
        app.screen.fill((0, 0, 0))
        app.manager.draw_ui(app.screen)
    app.new_game(tutorial=False)
    pygame.quit()
    print("SMOKE OK", pygame_gui.__name__)


if __name__ == "__main__":
    main()
