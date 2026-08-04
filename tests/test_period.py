from datetime import date

import pytest

from calculate_salary.period import Half, Period


def test_sixteenth_fills_first_half_of_current_month():
    period = Period.for_run_date(date(2026, 8, 16))
    assert (period.year, period.month, period.half) == (2026, 8, Half.FIRST)
    assert period.start == date(2026, 8, 1)
    assert period.end == date(2026, 8, 15)
    assert period.sheet_title == "Август 2026"
    assert period.block_header == "0 - 15"


def test_first_day_fills_second_half_of_previous_month():
    period = Period.for_run_date(date(2026, 8, 1))
    assert (period.year, period.month, period.half) == (2026, 7, Half.SECOND)
    assert period.start == date(2026, 7, 16)
    assert period.end == date(2026, 7, 31)
    assert period.sheet_title == "Июль 2026"
    assert period.block_header == "16 - 31"


def test_january_first_goes_to_december_of_previous_year():
    period = Period.for_run_date(date(2027, 1, 1))
    assert (period.year, period.month) == (2026, 12)
    assert period.sheet_title == "Декабрь 2026"
    assert period.end == date(2026, 12, 31)


def test_february_second_half_ends_on_last_day():
    assert Period.parse("2026-02:16-31").end == date(2026, 2, 28)
    assert Period.parse("2028-02:16-31").end == date(2028, 2, 29)


@pytest.mark.parametrize("value,half", [
    ("2026-07:0-15", Half.FIRST),
    ("2026-07:1-15", Half.FIRST),
    ("2026-07:first", Half.FIRST),
    ("2026-07:16-31", Half.SECOND),
    ("2026-07:second", Half.SECOND),
    ("2026-07: 16 - 31", Half.SECOND),
])
def test_parse_supported_forms(value, half):
    period = Period.parse(value)
    assert (period.year, period.month, period.half) == (2026, 7, half)


@pytest.mark.parametrize("value", ["2026-07", "2026-07:1-14", "июль:0-15", "2026:0-15"])
def test_parse_rejects_garbage(value):
    with pytest.raises(ValueError):
        Period.parse(value)


def test_contains_checks_boundaries_inclusive():
    period = Period.parse("2026-07:16-31")
    assert period.contains(date(2026, 7, 16))
    assert period.contains(date(2026, 7, 31))
    assert not period.contains(date(2026, 7, 15))
    assert not period.contains(date(2026, 8, 1))
    assert not period.contains(None)


def test_previous_month_title_handles_january():
    assert Period.parse("2026-08:0-15").previous_month_title() == "Июль 2026"
    assert Period.parse("2026-01:0-15").previous_month_title() == "Декабрь 2025"
