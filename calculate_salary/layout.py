"""Поиск ячеек в листе зарплаты.

Лист состоит из двух блоков: «0 - 15» (обычно столбцы A/B) и «16 - 31» (обычно H/I).
Под заголовком блока идут строки воронок; сумма пишется в столбец правее подписи.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .funnels import FUNNELS, Funnel
from .period import Half

# Сколько строк под заголовком блока просматриваем в поисках подписи воронки.
SEARCH_DEPTH = 8


@dataclass(frozen=True)
class Target:
    """Куда писать сумму воронки; row/col нулевые (A1 = 0,0).
    write_label — подписи в листе нет, ставим и её."""
    funnel: Funnel
    row: int
    col: int
    write_label: bool


@dataclass(frozen=True)
class Resolution:
    targets: list[Target]
    problems: list[str]


def resolve(grid: list[list], half: Half) -> Resolution:
    targets: list[Target] = []
    problems: list[str] = []

    header = half.value
    # Запасной вариант, если заголовок блока не нашли: A4 и H4, как в текущем шаблоне.
    header_row, header_col = 3, (0 if half is Half.FIRST else 7)
    found = _find_header(grid, header)
    if found is not None:
        header_row, header_col = found

    for index, funnel in enumerate(FUNNELS):
        label_row = _find_label(grid, header_col, header_row + 1, header_row + SEARCH_DEPTH, funnel.label)
        if label_row is not None:
            targets.append(Target(funnel, label_row, header_col + 1, False))
            continue
        # Подписи нет (так было с «Гайд»/«Курс» в левом блоке июля) — берём строку
        # по порядку, но только если она свободна: чужие ячейки не затираем.
        default_row = header_row + 1 + index
        occupant = cell_text(grid, default_row, header_col)
        if not occupant:
            targets.append(Target(funnel, default_row, header_col + 1, True))
        else:
            problems.append(
                f"«{funnel.label}» в блоке «{header}»: подпись не найдена, а ячейка "
                f"по умолчанию {a1(default_row, header_col)} занята значением «{occupant}» — пропускаю"
            )
    return Resolution(targets, problems)


def _find_header(grid: list[list], header: str) -> tuple[int, int] | None:
    want = _norm(header).replace(" ", "")
    for row_index, row in enumerate(grid):
        if not row:
            continue
        for col_index in range(len(row)):
            if _norm(cell_text(grid, row_index, col_index)).replace(" ", "") == want:
                return row_index, col_index
    return None


def _find_label(grid: list[list], col: int, from_row: int, to_row: int, label: str) -> int | None:
    want = _norm(label)
    for row in range(from_row, to_row + 1):
        if _norm(cell_text(grid, row, col)) == want:
            return row
    return None


def cell_text(grid: list[list], row: int, col: int) -> str:
    if row < 0 or row >= len(grid):
        return ""
    cells = grid[row]
    if not cells or col < 0 or col >= len(cells):
        return ""
    value = cells[col]
    return "" if value is None else str(value).strip()


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower() if value else ""


def a1(row: int, col: int) -> str:
    """(0,0) → A1."""
    letters = ""
    c = col + 1
    while c > 0:
        c, remainder = divmod(c - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return f"{letters}{row + 1}"
