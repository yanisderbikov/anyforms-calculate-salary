"""Расчётный полумесяц: какой месяц и какая половина листа заполняется."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from enum import Enum

MONTHS_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


class Half(Enum):
    """Значение — заголовок блока в листе."""
    FIRST = "0 - 15"
    SECOND = "16 - 31"


def title_for(year: int, month: int) -> str:
    """Название листа, например «Июль 2026»."""
    return f"{MONTHS_RU[month - 1]} {year}"


@dataclass(frozen=True)
class Period:
    year: int
    month: int
    half: Half

    @staticmethod
    def for_run_date(run_date: date) -> "Period":
        """Правило запуска по расписанию: с 16-го числа заполняем первую половину
        текущего месяца, до 16-го — вторую половину предыдущего."""
        if run_date.day >= 16:
            return Period(run_date.year, run_date.month, Half.FIRST)
        if run_date.month == 1:
            return Period(run_date.year - 1, 12, Half.SECOND)
        return Period(run_date.year, run_date.month - 1, Half.SECOND)

    @staticmethod
    def parse(value: str) -> "Period":
        """Разбор ручного переопределения вида ``2026-07:0-15`` или ``2026-07:16-31``."""
        month_part, colon, half_part = value.partition(":")
        error = ValueError(f"PERIOD должен быть вида 2026-07:0-15 или 2026-07:16-31, получено: {value!r}")
        if not colon:
            raise error
        year_str, dash, month_str = month_part.strip().partition("-")
        try:
            year, month = int(year_str), int(month_str)
        except ValueError:
            raise error
        if not dash or not 1 <= month <= 12:
            raise error

        half_norm = half_part.strip().lower().replace(" ", "")
        if half_norm in ("0-15", "1-15", "first"):
            half = Half.FIRST
        elif half_norm in ("16-31", "second"):
            half = Half.SECOND
        else:
            raise ValueError(f"Непонятная половина месяца: {half_part!r}")
        return Period(year, month, half)

    @property
    def start(self) -> date:
        return date(self.year, self.month, 1 if self.half is Half.FIRST else 16)

    @property
    def end(self) -> date:
        if self.half is Half.FIRST:
            return date(self.year, self.month, 15)
        return date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])

    def contains(self, day: date | None) -> bool:
        return day is not None and self.start <= day <= self.end

    @property
    def sheet_title(self) -> str:
        return title_for(self.year, self.month)

    def previous_month_title(self) -> str:
        if self.month == 1:
            return title_for(self.year - 1, 12)
        return title_for(self.year, self.month - 1)

    @property
    def block_header(self) -> str:
        return self.half.value
