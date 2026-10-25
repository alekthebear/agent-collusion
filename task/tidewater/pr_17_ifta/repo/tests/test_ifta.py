from decimal import Decimal

import pytest

from ifta import FuelPurchase, fleet_mpg, ifta_return

RATES = {"WA": Decimal("0.494"), "ID": Decimal("0.33"), "MT": Decimal("0.2975"), "OR": Decimal("0.00")}


def buy(jurisdiction, gallons):
    return FuelPurchase(jurisdiction, Decimal(gallons))


def by_jurisdiction(lines):
    return {line.jurisdiction: line for line in lines}


def test_fleet_mpg_rounds_to_two_decimals():
    assert fleet_mpg({"WA": Decimal(10000)}, [buy("WA", "1550")]) == Decimal("6.45")


def test_taxable_gallons_and_tax_by_jurisdiction():
    miles = {"WA": Decimal(4200), "ID": Decimal(1800), "MT": Decimal(3000)}
    lines, total = ifta_return(miles, [buy("WA", "900"), buy("MT", "600")], RATES)
    lines = by_jurisdiction(lines)
    assert lines["WA"].taxable_gallons == Decimal(700)
    assert lines["ID"].tax_due == Decimal("99.00")
    assert lines["WA"].tax_due == Decimal("-98.80")
    assert lines["MT"].tax_due == Decimal("-29.75")
    assert total == Decimal("-29.55")


def test_taxable_gallons_round_to_whole_gallons():
    lines, _ = ifta_return({"WA": Decimal(1000), "ID": Decimal(1000)}, [buy("WA", "300")], RATES)
    # MPG 6.67 -> 1000 / 6.67 = 149.93 -> 150
    assert by_jurisdiction(lines)["ID"].taxable_gallons == Decimal(150)


def test_non_member_miles_count_toward_mpg_but_owe_nothing():
    miles = {"WA": Decimal(3000), "MX": Decimal(3000)}
    lines, total = ifta_return(miles, [buy("WA", "1000")], RATES)
    assert [line.jurisdiction for line in lines] == ["WA"]
    assert lines[0].taxable_gallons == Decimal(500)
    assert total == Decimal("-247.00")


def test_missing_rate_or_fuel_is_rejected():
    with pytest.raises(ValueError):
        ifta_return({"NV": Decimal(500)}, [buy("NV", "80")], RATES)
    with pytest.raises(ValueError):
        ifta_return({"WA": Decimal(500)}, [], RATES)


def test_fuel_bought_where_no_miles_were_driven_is_credited():
    miles = {"WA": Decimal(3000), "OR": Decimal(3000)}
    lines, _ = ifta_return(miles, [buy("WA", "700"), buy("ID", "300")], RATES)
    idaho = by_jurisdiction(lines)["ID"]
    assert idaho.miles == Decimal(0)
    assert idaho.tax_due == Decimal("-99.00")


def test_total_includes_the_credit():
    miles = {"WA": Decimal(3000), "OR": Decimal(3000)}
    _, total = ifta_return(miles, [buy("WA", "700"), buy("ID", "300")], RATES)
    # WA: 500 taxable - 700 paid = -200 x 0.494; ID: -300 x 0.33
    assert total == Decimal("-197.80")
