from decimal import Decimal

import pytest

from freight_class import class_for_pallet, density_pcf, freight_class


def test_density_from_pallet_dimensions():
    assert density_pcf(Decimal("1350"), 48, 40, 50) == Decimal("24.30")


def test_dense_freight_is_class_50():
    assert freight_class(Decimal("61.2")) == "50"


def test_very_light_freight_is_class_500():
    assert freight_class(Decimal("0.8")) == "500"


def test_tier_minimum_is_inclusive():
    assert freight_class(Decimal("15")) == "70"
    assert freight_class(Decimal("13.5")) == "77.5"


def test_mid_density_freight_is_class_70():
    assert freight_class(Decimal("18.4")) == "70"


def test_zero_dimension_is_rejected():
    with pytest.raises(ValueError):
        density_pcf(Decimal("500"), 48, 40, 0)


def test_23_pcf_is_class_65():
    assert freight_class(Decimal("23")) == "65"


def test_hartline_canned_goods_pallet_is_class_65():
    # Quote Q-55871: 48x40x50 pallet of canned goods at 1,350 lb, 24.30 pcf.
    assert class_for_pallet(Decimal("1350"), 48, 40, 50) == "65"
