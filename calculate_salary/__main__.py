"""Раз в полмесяца считает суммы успешно закрытых сделок Ирины по воронкам amoCRM
и проставляет их в таблицу зарплаты в Google Sheets.

Запуск 1-го числа заполняет блок «16 - 31» предыдущего месяца, запуск 16-го числа —
блок «0 - 15» текущего. Сделка попадает в период по кастомному полю «Дата оплаты».

Запуск: ``python -m calculate_salary``.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from .amo import AmoClient, Lead
from .funnels import FUNNELS, Funnel
from .layout import a1, resolve
from .period import Half, Period
from .sheets import SheetsClient

# Системный статус amoCRM «Успешно реализовано» — одинаковый во всех воронках.
WON_STATUS_ID = 142

DEFAULT_SPREADSHEET_ID = "15SuV4LKn_edktKpp6Nwi01kXp9BGDv0gtblvT_HUyBI"
DEFAULT_RESPONSIBLE_USER_ID = 13161462  # Ирина
DEFAULT_PAYMENT_DATE_FIELD_ID = 2364807  # поле сделки «Дата оплаты»

# Список сделок пишем через одну колонку от суммы: B → D и I → K
# (между блоками это пустые колонки-разделители).
LINKS_COL_OFFSET = 2

MSK = ZoneInfo("Europe/Moscow")


class ConfigError(Exception):
    pass


def run() -> bool:
    subdomain = _require_env("AMOCRM_SUBDOMAIN")
    token = _require_env("AMOCRM_ACCESS_TOKEN")
    credentials_json = _require_env("GOOGLE_CREDENTIALS_JSON")
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip() or DEFAULT_SPREADSHEET_ID
    responsible_user_id = _int_env("RESPONSIBLE_USER_ID", DEFAULT_RESPONSIBLE_USER_ID)
    payment_date_field_id = _int_env("PAYMENT_DATE_FIELD_ID", DEFAULT_PAYMENT_DATE_FIELD_ID)

    period_override = os.getenv("PERIOD", "").strip()
    period = (Period.parse(period_override) if period_override
              else Period.for_run_date(datetime.now(MSK).date()))
    dry_run = os.getenv("DRY_RUN", "").strip().lower() in ("1", "true", "yes")

    print(f"Период: {period.start} — {period.end}, лист «{period.sheet_title}», блок «{period.block_header}»")
    if dry_run:
        print("Режим DRY_RUN: считаем и показываем, в таблицу не пишем")

    # 1. Суммы по воронкам из amoCRM. Сначала собираем всё — если amo недоступен,
    # падаем до записи в таблицу, а не затираем её нулями.
    amo = AmoClient(subdomain, token, payment_date_field_id)
    sums: dict[Funnel, int] = {}
    deals: dict[Funnel, list[Lead]] = {}
    for funnel in FUNNELS:
        won = amo.fetch_won_leads(funnel.pipeline_id, WON_STATUS_ID)
        matched = sorted(
            (lead for lead in won
             if lead.responsible_user_id == responsible_user_id and period.contains(lead.payment_date)),
            key=lambda lead: (lead.payment_date, lead.id),
        )
        deals[funnel] = matched
        sums[funnel] = sum(lead.price for lead in matched)
        print(f"{funnel.label}: успешных сделок всего {len(won)}, "
              f"в периоде у ответственного {len(matched)}, сумма {sums[funnel]}")

    # 2. Запись в Google Sheets.
    sheets = SheetsClient(credentials_json, spreadsheet_id)
    title = period.sheet_title
    existing = sheets.sheet_ids_by_title()

    grid_title = title
    if title not in existing:
        previous_title = period.previous_month_title()
        source_sheet_id = existing.get(previous_title)
        if source_sheet_id is None:
            raise ConfigError(
                f"в таблице нет листа «{title}» и нет листа «{previous_title}», "
                f"из которого его можно скопировать. Создай лист вручную."
            )
        if dry_run:
            print(f"[dry-run] листа «{title}» нет — был бы создан копией «{previous_title}»; "
                  f"разметку смотрю по «{previous_title}»")
            grid_title = previous_title
        else:
            print(f"Листа «{title}» нет — создаю копией «{previous_title}»")
            sheets.duplicate_sheet(source_sheet_id, title)
            _clear_copied_sums(sheets, title)
            print("Внимание: лист создан копированием — проверь формулы «прироста», "
                  "они могли остаться ссылаться на старый месяц.")

    grid = sheets.read_grid(grid_title)
    resolution = resolve(grid, period.half)

    writes: list[tuple[int, int, object]] = []
    link_cells: list[tuple[int, int, list[tuple[str, str]]]] = []
    for target in resolution.targets:
        if target.write_label:
            writes.append((target.row, target.col - 1, target.funnel.label))
        writes.append((target.row, target.col, sums[target.funnel]))
        link_cells.append((target.row, target.col + LINKS_COL_OFFSET,
                           _deal_links(subdomain, deals[target.funnel])))

    if dry_run:
        for target in resolution.targets:
            parts = _deal_links(subdomain, deals[target.funnel])
            listing = ", ".join(text for text, _ in parts) or "—"
            print(f"[dry-run] записал бы: {target.funnel.label} = {sums[target.funnel]} "
                  f"→ {title}!{a1(target.row, target.col)}, сделки в {a1(target.row, target.col + LINKS_COL_OFFSET)}: {listing}")
    else:
        sheets.write(title, writes)
        existing = sheets.sheet_ids_by_title()  # после duplicate мог появиться новый лист
        sheets.write_links(existing[title], link_cells)
        for target in resolution.targets:
            print(f"Записал: {target.funnel.label} = {sums[target.funnel]} → {title}!{a1(target.row, target.col)} "
                  f"(сделок: {len(deals[target.funnel])})")
    for problem in resolution.problems:
        print(f"Проблема: {problem}", file=sys.stderr)
    if resolution.problems:
        print(f"Часть значений не записана — проверь структуру листа «{title}».", file=sys.stderr)
        return False
    print("Готово.")
    return True


def _deal_links(subdomain: str, leads: list[Lead]) -> list[tuple[str, str]]:
    """Пары (текст, ссылка) для списка сделок: текст — сумма сделки."""
    return [
        (_format_price(lead.price), f"https://{subdomain}.amocrm.ru/leads/detail/{lead.id}")
        for lead in leads
    ]


def _format_price(price: int) -> str:
    return f"{price:,}".replace(",", " ")


def _clear_copied_sums(sheets: SheetsClient, title: str) -> None:
    """В свежескопированном листе затирает суммы и списки сделок обоих блоков,
    чтобы не остались цифры прошлого месяца."""
    grid = sheets.read_grid(title)
    sheet_id = sheets.sheet_ids_by_title()[title]
    clears: list[tuple[int, int, object]] = []
    link_clears: list[tuple[int, int, list[tuple[str, str]]]] = []
    for half in Half:
        for target in resolve(grid, half).targets:
            if not target.write_label:
                clears.append((target.row, target.col, ""))
            link_clears.append((target.row, target.col + LINKS_COL_OFFSET, []))
    sheets.write(title, clears)
    sheets.write_links(sheet_id, link_clears)


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"не задана переменная окружения {name}")
    return value


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    return int(value) if value else default


def main() -> None:
    # Локальный .env; в GitHub Actions переменные приходят из secrets
    # и имеют приоритет (load_dotenv не перекрывает уже заданные).
    load_dotenv()
    try:
        ok = run()
    except (ConfigError, ValueError) as error:
        print(f"Ошибка конфигурации: {error}", file=sys.stderr)
        sys.exit(2)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
