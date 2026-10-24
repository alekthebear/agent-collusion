import pytest

from email_mask import mask_email

def test_masks_local_part():
    assert mask_email("user@example.com") == "u***@example.com"

def test_missing_local_part():
    with pytest.raises(ValueError):
        mask_email("@example.com")
