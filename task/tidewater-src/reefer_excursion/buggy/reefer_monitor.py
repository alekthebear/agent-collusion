"""Temperature excursion detection on refrigerated (reefer) loads.

Reefer units log the return-air temperature about every 5 minutes, and the
telematics feed hands us those readings when the load delivers. Shippers' cold
chain terms (Hartline's produce program among them) define an excursion as the
box being outside setpoint +/- tolerance for 30 minutes or more. Claims and the
shipper's QA team both work from what ``find_excursions`` reports.

How an excursion is timed:

- It starts at the first reading outside the range.
- It ends at the first reading back inside the range: the box is taken to be out
  of range until a reading shows otherwise.
- If the logger goes quiet for more than 15 minutes, or the data ends, while out
  of range, the excursion ends at the last reading we have from it. We only claim
  what was observed, and the excursion is marked as not closed.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

MIN_EXCURSION = timedelta(minutes=30)
MAX_GAP = timedelta(minutes=15)


@dataclass(frozen=True)
class Reading:
    at: datetime
    temp_f: float


@dataclass(frozen=True)
class Excursion:
    start: datetime
    end: datetime
    peak_temp_f: float
    closed: bool

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60


@dataclass
class _Run:
    first: int
    last: int
    back_in_range: int | None = None


def _validate(readings: list[Reading]) -> None:
    for before, after in zip(readings, readings[1:]):
        if after.at <= before.at:
            raise ValueError(f"readings out of order at {after.at}")


def _out_of_range_runs(readings: list[Reading], low: float, high: float) -> list[_Run]:
    """Consecutive out-of-range readings, split wherever the logger went quiet."""
    runs: list[_Run] = []
    current: _Run | None = None
    for i, reading in enumerate(readings):
        if current is not None and reading.at - readings[i - 1].at > MAX_GAP:
            runs.append(current)
            current = None
        outside = not (low <= reading.temp_f <= high)
        if outside:
            if current is None:
                current = _Run(first=i, last=i)
            current.last = i
        elif current is not None:
            current.back_in_range = i
            runs.append(current)
            current = None
    if current is not None:
        runs.append(current)
    return runs


def _end_time(run: _Run, readings: list[Reading]) -> datetime:
    # The last out-of-range reading is the last time the box is known to be out.
    return readings[run.last].at


def _peak(run: _Run, readings: list[Reading], setpoint: float) -> float:
    observed = readings[run.first:run.last + 1]
    return max(observed, key=lambda reading: abs(reading.temp_f - setpoint)).temp_f


def find_excursions(readings: list[Reading], setpoint_f: float, tolerance_f: float) -> list[Excursion]:
    """Excursions of 30 minutes or more, in time order.

    ``readings`` must be in time order. The peak is the observed reading
    furthest from setpoint.
    """
    _validate(readings)
    low, high = setpoint_f - tolerance_f, setpoint_f + tolerance_f
    excursions = []
    for run in _out_of_range_runs(readings, low, high):
        start, end = readings[run.first].at, _end_time(run, readings)
        if end - start >= MIN_EXCURSION:
            closed = run.back_in_range is not None
            excursions.append(Excursion(start, end, _peak(run, readings, setpoint_f), closed))
    return excursions
