"""Воронки amoCRM, участвующие в расчёте зарплаты.

Подпись должна совпадать со строкой в листе зарплаты Google Sheets.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Funnel:
    label: str
    pipeline_id: int


FUNNELS = [
    Funnel("Под заказ", 9784138),
    Funnel("Розница", 10557858),
    Funnel("Повторные продажи", 9939750),
    Funnel("Гайд", 11156742),
    Funnel("Курс", 10863606),
]
