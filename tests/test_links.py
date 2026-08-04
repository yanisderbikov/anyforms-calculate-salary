from calculate_salary.sheets import build_link_runs


def test_two_links_with_separator():
    text, runs = build_link_runs([
        ("49 360", "https://amo/leads/detail/1"),
        ("32 500", "https://amo/leads/detail/2"),
    ])
    assert text == "49 360, 32 500"
    assert runs == [
        {"startIndex": 0, "format": {"link": {"uri": "https://amo/leads/detail/1"}}},
        {"startIndex": 6, "format": {}},
        {"startIndex": 8, "format": {"link": {"uri": "https://amo/leads/detail/2"}}},
    ]


def test_single_link_has_no_separator_run():
    text, runs = build_link_runs([("74 000", "https://amo/leads/detail/3")])
    assert text == "74 000"
    assert runs == [{"startIndex": 0, "format": {"link": {"uri": "https://amo/leads/detail/3"}}}]


def test_empty_list_clears_cell():
    text, runs = build_link_runs([])
    assert text == ""
    assert runs == []
