"""Обёртка над Google Sheets API для таблицы зарплаты."""
from __future__ import annotations

import base64
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build

from .layout import a1

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    def __init__(self, credentials_json: str, spreadsheet_id: str):
        self._spreadsheet_id = spreadsheet_id
        info = json.loads(_normalize_credentials(credentials_json))
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        self._service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    def sheet_ids_by_title(self) -> dict[str, int]:
        """Названия листов в порядке следования → sheetId."""
        response = self._service.spreadsheets().get(
            spreadsheetId=self._spreadsheet_id,
            fields="sheets.properties(sheetId,title)",
        ).execute()
        return {
            sheet["properties"]["title"]: sheet["properties"]["sheetId"]
            for sheet in response.get("sheets", [])
        }

    def duplicate_sheet(self, source_sheet_id: int, new_title: str) -> None:
        """Копирует лист (вместе с формулами и оформлением) под новым именем и ставит его первым."""
        body = {"requests": [{"duplicateSheet": {
            "sourceSheetId": source_sheet_id,
            "newSheetName": new_title,
            "insertSheetIndex": 0,
        }}]}
        self._service.spreadsheets().batchUpdate(spreadsheetId=self._spreadsheet_id, body=body).execute()

    def read_grid(self, sheet_title: str) -> list[list]:
        """Левая верхняя часть листа, где живут оба блока сумм."""
        response = self._service.spreadsheets().values().get(
            spreadsheetId=self._spreadsheet_id,
            range=f"{_quote(sheet_title)}!A1:M40",
        ).execute()
        return response.get("values", [])

    def write(self, sheet_title: str, writes: list[tuple[int, int, object]]) -> None:
        """Пишет значения в ячейки; (row, col) нулевые, A1 = (0, 0)."""
        if not writes:
            return
        data = [
            {"range": f"{_quote(sheet_title)}!{a1(row, col)}", "values": [[value]]}
            for row, col, value in writes
        ]
        self._service.spreadsheets().values().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": data},
        ).execute()


    def write_links(self, sheet_id: int, cells: list[tuple[int, int, list[tuple[str, str]]]]) -> None:
        """Пишет в ячейки списки кликабельных ссылок (rich text).

        cells: (row, col, [(текст, url), ...]); пустой список очищает ячейку.
        """
        requests = []
        for row, col, parts in cells:
            text, runs = build_link_runs(parts)
            # textFormat сбрасываем явно: одиночную ссылку Sheets сворачивает
            # в формат ячейки, и без сброса она «прилипает» при перезаписи.
            value: dict = {
                "userEnteredValue": {"stringValue": text},
                "userEnteredFormat": {"textFormat": {}},
            }
            if runs:
                value["textFormatRuns"] = runs
            requests.append({"updateCells": {
                "rows": [{"values": [value]}],
                "fields": "userEnteredValue,userEnteredFormat.textFormat,textFormatRuns",
                "start": {"sheetId": sheet_id, "rowIndex": row, "columnIndex": col},
            }})
        if requests:
            self._service.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id, body={"requests": requests}
            ).execute()


def build_link_runs(parts: list[tuple[str, str]]) -> tuple[str, list[dict]]:
    """Текст ячейки и textFormatRuns к нему: каждый элемент — ссылка,
    разделитель «, » — без ссылки."""
    text = ", ".join(part_text for part_text, _ in parts)
    runs: list[dict] = []
    position = 0
    for index, (part_text, url) in enumerate(parts):
        runs.append({"startIndex": position, "format": {"link": {"uri": url}}})
        position += len(part_text)
        if index < len(parts) - 1:
            runs.append({"startIndex": position, "format": {}})
            position += 2  # «, »
    return text, runs


def _normalize_credentials(raw: str) -> str:
    """Секрет может лежать как сырой JSON сервис-аккаунта или как base64 от него."""
    trimmed = raw.strip()
    if trimmed.startswith("{"):
        return trimmed
    return base64.b64decode(trimmed).decode("utf-8")


def _quote(sheet_title: str) -> str:
    return "'" + sheet_title.replace("'", "''") + "'"
