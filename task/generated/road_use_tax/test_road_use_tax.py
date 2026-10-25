from decimal import Decimal

import pytest

from road_use_tax import JurisdictionMiles, TaxTerms, calculate_road_use_tax


def test_loaded_and_empty_miles_are_taxed():
    miles = JurisdictionMiles(name="OR", loaded_miles=Decimal("120"), empty_miles=Decimal("30"))
    terms = TaxTerms(rate_per_mile=Decimal("0.08"))
    assert calculate_road_use_tax(miles, terms) == Decimal("12.00")


def test_yard_and_ferry_miles_do_not_count():
    miles = JurisdictionMiles(
        name="KY",
        loaded_miles=Decimal("50"),
        empty_miles=Decimal("20"),
        yard_miles=Decimal("200"),
        ferry_miles=Decimal("40"),
    )
    terms = TaxTerms(rate_per_mile=Decimal("0.10"))
    assert calculate_road_use_tax(miles, terms) == Decimal("7.00")


def test_exempt_miles_reduce_taxable_miles():
    miles = JurisdictionMiles(
        name="NM",
        loaded_miles=Decimal("100"),
        empty_miles=Decimal("20"),
        exempt_miles=Decimal("25"),
    )
    terms = TaxTerms(rate_per_mile=Decimal("0.12"))
    assert calculate_road_use_tax(miles, terms) == Decimal("11.40")


def test_exempt_miles_cannot_exceed_road_miles():
    miles = JurisdictionMiles(name="KS", loaded_miles=Decimal("40"), exempt_miles=Decimal("80"))
    terms = TaxTerms(rate_per_mile=Decimal("0.09"))
    assert calculate_road_use_tax(miles, terms) == Decimal("0.00")


def test_fewer_than_ten_taxable_miles_is_de_minimis():
    miles = JurisdictionMiles(name="NY", loaded_miles=Decimal("9.99"))
    terms = TaxTerms(rate_per_mile=Decimal("0.50"))
    assert calculate_road_use_tax(miles, terms) == Decimal("0.00")


def test_exactly_ten_taxable_miles_is_taxed():
    miles = JurisdictionMiles(name="NY", loaded_miles=Decimal("10.00"))
    terms = TaxTerms(rate_per_mile=Decimal("0.50"))
    assert calculate_road_use_tax(miles, terms) == Decimal("5.00")


def test_half_up_rounding_applies_to_base_tax():
    miles = JurisdictionMiles(name="UT", loaded_miles=Decimal("3"), empty_miles=Decimal("7"))
    terms = TaxTerms(rate_per_mile=Decimal("0.3335"))
    assert calculate_road_use_tax(miles, terms) == Decimal("3.34")


def test_electric_surcharge_applies_at_threshold():
    miles = JurisdictionMiles(name="WA", loaded_miles=Decimal("100"))
    terms = TaxTerms(rate_per_mile=Decimal("0.05"), is_electric=True, electric_surcharge=Decimal("18.00"))
    assert calculate_road_use_tax(miles, terms) == Decimal("23.00")


def test_bulk_discount_applies_only_above_one_thousand_taxable_miles():
    miles = JurisdictionMiles(name="OR", loaded_miles=Decimal("1001"))
    terms = TaxTerms(rate_per_mile=Decimal("0.20"))
    assert calculate_road_use_tax(miles, terms) == Decimal("196.20")


def test_negative_values_are_rejected():
    miles = JurisdictionMiles(name="ID", loaded_miles=Decimal("10"), empty_miles=Decimal("-1"))
    terms = TaxTerms(rate_per_mile=Decimal("0.08"))
    with pytest.raises(ValueError):
        calculate_road_use_tax(miles, terms)
