`minutes_to_hhmm` in `timefmt.py` drops leading zeros. `minutes_to_hhmm(75)` should return `"01:15"`, but returns `"1:15"`; `minutes_to_hhmm(605)` returns `"10:5"` instead of `"10:05"`.
