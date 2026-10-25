from datetime import date

import pytest

from claims import ACCEPTED, DENIED_LATE, Claim, filing_deadline, screen_claim


def claim(delivered, filed, customer="HARTLINE"):
    return Claim("CL-20931", customer, delivered, filed)


def test_deadline_is_nine_months_after_delivery():
    assert filing_deadline(date(2025, 12, 3)) == date(2026, 9, 3)


def test_deadline_clamps_to_the_end_of_a_short_month():
    assert filing_deadline(date(2026, 5, 31)) == date(2027, 2, 28)


def test_claim_filed_on_the_deadline_is_accepted():
    assert screen_claim(claim(date(2025, 12, 3), date(2026, 9, 3))) == ACCEPTED


def test_claim_filed_after_nine_months_is_denied():
    # Nine months from delivery is the filing window in our bill of lading terms
    # §12, which Hartline's agreement adopts without change. Our cargo insurer does
    # not cover claims filed later, so the desk denies them here for every
    # customer. A longer window would need a new insurance rider first.
    assert screen_claim(claim(date(2025, 12, 3), date(2026, 10, 12))) == DENIED_LATE


def test_prompt_claim_is_accepted():
    assert screen_claim(claim(date(2026, 9, 28), date(2026, 10, 2), "BRIGHTWATER")) == ACCEPTED


def test_claim_filed_before_delivery_is_rejected():
    with pytest.raises(ValueError):
        screen_claim(claim(date(2026, 10, 2), date(2026, 9, 28)))
