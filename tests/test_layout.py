from calculate_salary.funnels import FUNNELS
from calculate_salary.layout import a1, resolve
from calculate_salary.period import Half

GAID = next(f for f in FUNNELS if f.label == "Гайд")
KURS = next(f for f in FUNNELS if f.label == "Курс")
POD_ZAKAZ = next(f for f in FUNNELS if f.label == "Под заказ")
POVTORNYE = next(f for f in FUNNELS if f.label == "Повторные продажи")


def july_grid():
    """Структура июльского листа: слева три воронки, справа все пять."""
    return [
        [],                                                                                # 1
        ["Оклад в месяц", "25 000"],                                                       # 2
        [],                                                                                # 3
        ["0 - 15", "", "", "", "", "", "", "16 - 31"],                                     # 4
        ["Под заказ", "88 240", "91%", "", "Прирост", "-69%", "", "Под заказ", "87 733"],  # 5
        ["Розница", "9 000", "9%", "", "", "", "", "Розница", "2 000"],                    # 6
        ["Повторные продажи", "0", "", "", "", "", "", "Повторные продажи", "551 400"],    # 7
        ["", "", "", "", "", "", "", "Гайд"],                                              # 8
        ["", "", "", "", "", "", "", "Курс"],                                              # 9
        [],                                                                                # 10
        ["Итог", "97 240", "", "", "", "", "", "Итог", "641 133"],                         # 11
    ]


def by_funnel(resolution):
    return {target.funnel: target for target in resolution.targets}


def test_first_block_finds_labels_and_adds_missing_ones():
    resolution = resolve(july_grid(), Half.FIRST)
    assert resolution.problems == []
    targets = by_funnel(resolution)

    assert (targets[POD_ZAKAZ].row, targets[POD_ZAKAZ].col) == (4, 1)
    assert not targets[POD_ZAKAZ].write_label
    assert targets[POVTORNYE].row == 6

    # «Гайд» и «Курс» в левом блоке не подписаны — пишем в свободные строки вместе с подписью
    assert (targets[GAID].row, targets[GAID].write_label) == (7, True)
    assert (targets[KURS].row, targets[KURS].write_label) == (8, True)


def test_second_block_finds_all_five_labels():
    resolution = resolve(july_grid(), Half.SECOND)
    assert resolution.problems == []
    targets = by_funnel(resolution)

    assert len(targets) == 5
    assert all(target.col == 8 for target in targets.values())  # столбец I
    assert not any(target.write_label for target in targets.values())
    assert targets[POD_ZAKAZ].row == 4
    assert targets[GAID].row == 7
    assert targets[KURS].row == 8


def test_occupied_default_cell_becomes_problem_and_is_not_overwritten():
    grid = july_grid()
    grid[7][0] = "Что-то чужое"  # A8 занята не воронкой
    resolution = resolve(grid, Half.FIRST)

    assert len(resolution.problems) == 1
    targets = by_funnel(resolution)
    assert GAID not in targets
    assert targets[KURS].row == 8  # A9 свободна — «Курс» пишем


def test_commission_section_below_is_not_mistaken_for_sums():
    grid = july_grid()
    while len(grid) < 20:
        grid.append([])
    grid.append(["Повторные продажи", "0"])  # строка 21 — секция «процент с продаж»
    resolution = resolve(grid, Half.FIRST)
    assert by_funnel(resolution)[POVTORNYE].row == 6


def test_a1_addressing():
    assert a1(0, 0) == "A1"
    assert a1(4, 1) == "B5"
    assert a1(4, 8) == "I5"
    assert a1(0, 26) == "AA1"
