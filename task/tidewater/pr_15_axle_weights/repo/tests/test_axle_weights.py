import pytest

from axle_weights import Violation, bridge_limit, check_axle_weights


def test_bridge_formula_matches_the_table():
    assert bridge_limit(42, 4) == 70_000
    assert bridge_limit(14.25, 3) == 46_500
    assert bridge_limit(59, 5) == 85_000


def test_standard_five_axle_at_80k_is_legal():
    assert check_axle_weights([12_000, 17_000, 17_000, 17_000, 17_000], [0, 17, 21.25, 55, 59]) == []


def test_heavy_tandem_and_steer_are_flagged():
    violations = check_axle_weights([21_000, 17_500, 17_500, 12_000, 12_000], [0, 17, 21.25, 55, 59])
    assert Violation("single", 0, 0, 21_000, 20_000) in violations
    assert Violation("tandem", 1, 2, 35_000, 34_000) in violations


def test_gross_over_80k():
    violations = check_axle_weights([13_000, 17_000, 17_000, 17_000, 17_000], [0, 17, 21.25, 55, 59])
    assert violations == [Violation("gross", 0, 4, 81_000, 80_000)]


def test_double_tandem_exception_at_36_feet():
    assert check_axle_weights([12_000, 17_000, 17_000, 17_000, 17_000], [0, 20, 24.25, 53, 57]) == []


def test_bad_axle_lists_are_rejected():
    with pytest.raises(ValueError):
        check_axle_weights([12_000], [0])
    with pytest.raises(ValueError):
        check_axle_weights([12_000, 17_000], [0, 0])


def test_tandems_slid_forward_break_the_inner_span():
    violations = check_axle_weights([12_000, 17_000, 17_000, 17_000, 17_000], [0, 22, 26.25, 50, 54])
    assert violations == [Violation("bridge", 1, 4, 68_000, 63_500)]


def test_short_tractor_overloads_steer_and_drives_together():
    violations = check_axle_weights([13_000, 17_000, 17_000, 16_000, 16_000], [0, 10, 14.25, 48, 52])
    assert violations == [Violation("bridge", 0, 2, 47_000, 46_500)]
