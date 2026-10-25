from decimal import Decimal

import pytest

from trainer_pay_split import PaySplit, TrainingProgram, TripMiles, calculate_trainer_pay_split


def test_orientation_pays_all_to_trainer():
    split = calculate_trainer_pay_split(
        Decimal("500.00"),
        TripMiles(loaded_miles=400, authorized_empty_miles=50, trainee_miles=450),
        TrainingProgram("orientation"),
    )
    assert split == PaySplit(trainer_pay=Decimal("500.00"), trainee_pay=Decimal("0.00"))


def test_seat1_pays_full_phase_percent_when_minimum_share_met():
    split = calculate_trainer_pay_split(
        Decimal("800.00"),
        TripMiles(loaded_miles=300, authorized_empty_miles=100, trainee_miles=80),
        TrainingProgram("seat1"),
    )
    assert split == PaySplit(trainer_pay=Decimal("600.00"), trainee_pay=Decimal("200.00"))


def test_unauthorized_empty_miles_are_excluded_from_eligibility():
    split = calculate_trainer_pay_split(
        Decimal("1000.00"),
        TripMiles(loaded_miles=100, authorized_empty_miles=0, unauthorized_empty_miles=900, trainee_miles=30),
        TrainingProgram("seat2"),
    )
    assert split == PaySplit(trainer_pay=Decimal("600.00"), trainee_pay=Decimal("400.00"))


def test_soft_landing_applies_when_shortfall_is_under_five_points():
    split = calculate_trainer_pay_split(
        Decimal("1000.00"),
        TripMiles(loaded_miles=200, authorized_empty_miles=0, trainee_miles=52),
        TrainingProgram("seat2"),
    )
    assert split == PaySplit(trainer_pay=Decimal("800.00"), trainee_pay=Decimal("200.00"))


def test_exactly_five_point_shortfall_gets_no_trainee_pay():
    split = calculate_trainer_pay_split(
        Decimal("1000.00"),
        TripMiles(loaded_miles=100, authorized_empty_miles=0, trainee_miles=40),
        TrainingProgram("team"),
    )
    assert split == PaySplit(trainer_pay=Decimal("1000.00"), trainee_pay=Decimal("0.00"))


def test_team_phase_under_fifty_eligible_miles_is_trainer_only():
    split = calculate_trainer_pay_split(
        Decimal("300.00"),
        TripMiles(loaded_miles=40, authorized_empty_miles=9, trainee_miles=49),
        TrainingProgram("team"),
    )
    assert split == PaySplit(trainer_pay=Decimal("300.00"), trainee_pay=Decimal("0.00"))


def test_trainee_miles_above_eligible_are_capped_for_share_test():
    split = calculate_trainer_pay_split(
        Decimal("120.05"),
        TripMiles(loaded_miles=80, authorized_empty_miles=20, trainee_miles=300),
        TrainingProgram("team"),
    )
    assert split == PaySplit(trainer_pay=Decimal("60.02"), trainee_pay=Decimal("60.03"))


def test_zero_eligible_miles_returns_zero_split_even_with_pay():
    split = calculate_trainer_pay_split(
        Decimal("250.00"),
        TripMiles(loaded_miles=0, authorized_empty_miles=0, unauthorized_empty_miles=50, trainee_miles=25),
        TrainingProgram("seat1"),
    )
    assert split == PaySplit(trainer_pay=Decimal("0.00"), trainee_pay=Decimal("0.00"))


def test_unknown_phase_is_rejected():
    with pytest.raises(ValueError):
        calculate_trainer_pay_split(
            Decimal("100.00"),
            TripMiles(loaded_miles=10, trainee_miles=5),
            TrainingProgram("graduate"),
        )


def test_negative_miles_are_rejected():
    with pytest.raises(ValueError):
        calculate_trainer_pay_split(
            Decimal("100.00"),
            TripMiles(loaded_miles=-1, trainee_miles=0),
            TrainingProgram("seat1"),
        )
