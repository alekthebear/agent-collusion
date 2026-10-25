"""Expected EDI segment counts for validating ST/SE transaction envelopes.

The validator compares the SE01 control count to the transaction's actual segment
count. Tidewater counts every transmitted segment from ST through SE inclusive,
which matches the X12 rule used by most trading partners. The count is derived
from a prepared segment list plus a few business adjustments used before outbound
validation:

- Blank or whitespace-only segment strings are ignored completely.
- The first ST and the last SE found in the cleaned list define the transaction
  envelope; segments outside that range are not counted.
- If either boundary is missing, validation cannot proceed and the function raises
  ValueError.
- Repeated ST/SE segments inside the envelope are treated as ordinary segments and
  still counted.
- A trailer note segment NTE after SE is ignored, but an NTE inside the envelope
  counts like any other segment.
- For partner profiles marked ``compress_empty_segments=True``, consecutive empty
  placeholders that were removed from the prepared list reduce noise but do not
  affect the final count because ignored blanks are never segments.
- If the resulting transaction count exceeds the partner's configured maximum, a
  ValueError is raised to stop obviously malformed transactions.
"""

from dataclasses import dataclass

DEFAULT_MAX_SEGMENTS = 9999


@dataclass(frozen=True)
class SegmentBatch:
    """Prepared transaction segments in transmission order."""

    segments: tuple[str, ...]


@dataclass(frozen=True)
class PartnerProfile:
    """Validation settings for one EDI trading partner."""

    compress_empty_segments: bool = True
    max_segments: int = DEFAULT_MAX_SEGMENTS
    allow_single_segment_transaction: bool = False


def _clean_segments(batch: SegmentBatch, compress_empty_segments: bool) -> list[str]:
    cleaned: list[str] = []
    previous_blank = False
    for raw in batch.segments:
        text = raw.strip()
        if not text:
            if compress_empty_segments and previous_blank:
                continue
            previous_blank = True
            continue
        previous_blank = False
        cleaned.append(text)
    return cleaned


def _segment_id(segment: str) -> str:
    head, _, _ = segment.partition("*")
    return head.upper()


def _envelope_bounds(segments: list[str]) -> tuple[int, int]:
    start = next((i for i, s in enumerate(segments) if _segment_id(s) == "ST"), -1)
    end = next((i for i in range(len(segments) - 1, -1, -1) if _segment_id(segments[i]) == "SE"), -1)
    if start == -1 or end == -1 or end < start:
        raise ValueError("transaction must contain ST before SE")
    return start, end


def _validate_count(count: int, profile: PartnerProfile) -> None:
    if count < 2 and not profile.allow_single_segment_transaction:
        raise ValueError("transaction must include at least ST and SE")
    if count > profile.max_segments:
        raise ValueError(f"segment count {count} exceeds max {profile.max_segments}")


def calculate_edi_segment_count(
    batch: SegmentBatch, profile: PartnerProfile = PartnerProfile()
) -> int:
    """Return the expected SE01 segment count for one transaction set.

    The count includes both ST and SE and excludes blank prepared entries and any
    segments before the first ST or after the last SE.

    >>> calculate_edi_segment_count(SegmentBatch(("ISA*...", "ST*204*0001", "B2*", "SE*3*0001", "GE*1")))
    3
    """
    cleaned = _clean_segments(batch, profile.compress_empty_segments)
    start, end = _envelope_bounds(cleaned)
    count = end - start + 1
    _validate_count(count, profile)
    return count
