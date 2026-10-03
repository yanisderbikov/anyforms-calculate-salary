"""Минимальный клиент amoCRM: постраничная выборка сделок воронки в заданном статусе."""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

PAGE_LIMIT = 250  # amoCRM не отдаёт больше 250 сущностей на страницу
MAX_PAGES = 400   # предохранитель от бесконечного цикла: до 100 000 сделок на воронку
MAX_ATTEMPTS = 4


@dataclass(frozen=True)
class Lead:
    """Данные сделки, нужные для расчёта."""
    id: int
    price: int
    responsible_user_id: int | None
    payment_date: date | None


class AmoClient:
    def __init__(self, subdomain: str, token: str, payment_date_field_id: int):
        self._base_url = f"https://{subdomain}.amocrm.ru"
        self._payment_date_field_id = payment_date_field_id
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"
        self._timezone: ZoneInfo | None = None

    def account_timezone(self) -> ZoneInfo:
        """Часовой пояс аккаунта amo. Date-поля amo хранит как полночь именно в нём
        (у anyforms это Asia/Omsk, а не Москва), так что день считаем по нему."""
        if self._timezone is None:
            payload = self._get("/api/v4/account", {"with": "datetime_settings"}) or {}
            name = ((payload.get("_embedded") or {}).get("datetime_settings") or {}).get("timezone")
            if not name:
                raise RuntimeError("amoCRM не вернул часовой пояс аккаунта (datetime_settings.timezone)")
            self._timezone = ZoneInfo(name)
        return self._timezone

    def fetch_won_leads(self, pipeline_id: int, status_id: int) -> list[Lead]:
        """Все сделки воронки в указанном статусе. Дата оплаты и ответственный
        фильтруются потом на нашей стороне — так выборка не зависит от поддержки
        фильтров по кастомным полям в amo."""
        timezone = self.account_timezone()
        leads: list[Lead] = []
        for page in range(1, MAX_PAGES + 1):
            # Фильтр по статусу работает только через filter[statuses][N][...] —
            # плоский filter[status_id] amo молча игнорирует.
            params = {
                "filter[statuses][0][pipeline_id]": pipeline_id,
                "filter[statuses][0][status_id]": status_id,
                "page": page,
                "limit": PAGE_LIMIT,
            }
            payload = self._get("/api/v4/leads", params)
            if payload is None:
                break  # 204 — страницы кончились
            page_leads = parse_leads_page(payload, self._payment_date_field_id, timezone)
            leads.extend(page_leads)
            if len(page_leads) < PAGE_LIMIT:
                break
            time.sleep(0.15)  # лимит amo — 7 запросов/сек
        return leads

    def _get(self, path: str, params: dict) -> dict | None:
        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._session.get(self._base_url + path, params=params, timeout=60)
            except requests.RequestException as error:
                last_error = error
                time.sleep(attempt)
                continue
            if response.status_code == 200:
                return response.json() if response.text.strip() else None
            if response.status_code == 204:
                return None
            if response.status_code == 429 or response.status_code >= 500:
                last_error = RuntimeError(f"amoCRM {response.status_code}: {response.text[:500]}")
                time.sleep(2 * attempt)
                continue
            raise RuntimeError(f"amoCRM {response.status_code} на {path}: {response.text[:500]}")
        raise RuntimeError(f"amoCRM: исчерпаны попытки, {path}") from last_error


def parse_leads_page(payload: dict, payment_date_field_id: int, timezone: ZoneInfo) -> list[Lead]:
    result: list[Lead] = []
    for lead in (payload.get("_embedded") or {}).get("leads") or []:
        if not isinstance(lead, dict) or lead.get("id") is None:
            continue
        responsible = lead.get("responsible_user_id")
        result.append(Lead(
            id=int(lead["id"]),
            price=int(lead.get("price") or 0),
            responsible_user_id=int(responsible) if responsible is not None else None,
            payment_date=extract_payment_date(lead, payment_date_field_id, timezone),
        ))
    return result


def extract_payment_date(lead: dict, field_id: int, timezone: ZoneInfo) -> date | None:
    """Дата оплаты из кастомного поля сделки. amo отдаёт date-поля unix-таймстампом
    полуночи в часовом поясе аккаунта; день берём в нём же, иначе в любом поясе
    западнее (например, по Москве) дата уезжает на предыдущие сутки."""
    for field in lead.get("custom_fields_values") or []:
        if not isinstance(field, dict) or field.get("field_id") != field_id:
            continue
        values = field.get("values") or []
        if not values or not isinstance(values[0], dict):
            return None
        raw = values[0].get("value")
        if raw is None:
            return None
        try:
            return datetime.fromtimestamp(int(raw), timezone).date()
        except (ValueError, TypeError, OSError):
            pass  # не таймстамп — пробуем ISO-формат
        try:
            parsed = datetime.fromisoformat(str(raw))
            return (parsed.astimezone(timezone) if parsed.tzinfo else parsed).date()
        except ValueError:
            print(f"Сделка {lead.get('id')}: не смог разобрать дату оплаты {raw!r}", file=sys.stderr)
            return None
    return None
