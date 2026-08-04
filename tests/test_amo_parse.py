from datetime import date

from calculate_salary.amo import Lead, extract_payment_date, parse_leads_page

FIELD = 2364807


def test_parses_lead_with_timestamp_payment_date():
    # 1753822800 = 2025-07-30 00:00 МСК (в UTC это ещё 29-е — день должен браться по Москве)
    payload = {"_embedded": {"leads": [{
        "id": 101,
        "price": 88240,
        "responsible_user_id": 13161462,
        "custom_fields_values": [
            {"field_id": 111, "values": [{"value": "другое поле"}]},
            {"field_id": FIELD, "values": [{"value": 1753822800}]},
        ],
    }]}}
    assert parse_leads_page(payload, FIELD) == [
        Lead(id=101, price=88240, responsible_user_id=13161462, payment_date=date(2025, 7, 30))
    ]


def test_parses_timestamp_sent_as_string():
    lead = {"id": 102, "custom_fields_values": [{"field_id": FIELD, "values": [{"value": "1753822800"}]}]}
    assert extract_payment_date(lead, FIELD) == date(2025, 7, 30)


def test_lead_without_payment_date_or_price_is_still_parsed():
    payload = {"_embedded": {"leads": [
        {"id": 103, "custom_fields_values": None},
        {"id": 104, "price": 100, "custom_fields_values": [{"field_id": FIELD, "values": []}]},
    ]}}
    leads = parse_leads_page(payload, FIELD)
    assert [lead.id for lead in leads] == [103, 104]
    assert leads[0].price == 0
    assert leads[0].payment_date is None
    assert leads[1].payment_date is None


def test_unparseable_date_gives_none():
    lead = {"id": 105, "custom_fields_values": [{"field_id": FIELD, "values": [{"value": "не дата"}]}]}
    assert extract_payment_date(lead, FIELD) is None


def test_empty_page_gives_empty_list():
    assert parse_leads_page({}, FIELD) == []
    assert parse_leads_page({"_embedded": {}}, FIELD) == []
