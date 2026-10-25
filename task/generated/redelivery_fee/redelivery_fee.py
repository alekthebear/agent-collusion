"""Redelivery charges for freight that must be attempted again after a failed delivery.

A redelivery fee is billed only when the first delivery failed for a customer-fault
reason such as a closed consignee, refusal, or no dock space. Carrier-fault and
force-majeure failures are not billable. The charge combines a tariff minimum with
mileage retraced from the point of failure back toward the terminal and out again on
redelivery. Local freight under 10 retraced miles bills the minimum only; longer
retraces add a per-mile amount. Rural deliveries use a higher mileage rate.

Special handling rules mirror common LTL tariffs: residential shipments are charged
half of the computed fee on the first customer-fault failure, but not below a
residential minimum. On a second or later customer-fault failure, the full computed
fee applies plus a repeat-failure surcharge. All amounts round half up to the cent.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
BASE_MINIMUM = Decimal("85.00")
RESIDENTIAL_MINIMUM = Decimal("55.00")
PER_MILE_RATE = Decimal("4.25")
RURAL_PER_MILE_RATE = Decimal("5.10")
REPEAT_FAILURE_SURCHARGE = Decimal("35.00")
MILEAGE_THRESHOLD = Decimal("10")
CUSTOMER_FAULT_REASONS = frozenset({"closed", "refused", "no_dock", "bad_address", "no_one_available"})
NON_BILLABLE_REASONS = frozenset({"carrier_missed_appt", "equipment_failure", "weather", "act_of_god"})


@dataclass(frozen=True)
class RedeliveryRequest:
    failed_reason: str
    retraced_miles: Decimal
    customer_fault_count: int = 1
    is_residential: bool = False
    is_rural: bool = False
    appointment_kept: bool = True


@dataclass(frozen=True)
class RedeliveryTariff:
    minimum_fee: Decimal = BASE_MINIMUM
    residential_minimum_fee: Decimal = RESIDENTIAL_MINIMUM
    per_mile_rate: Decimal = PER_MILE_RATE
    rural_per_mile_rate: Decimal = RURAL_PER_MILE_RATE
    repeat_failure_surcharge: Decimal = REPEAT_FAILURE_SURCHARGE
    mileage_threshold: Decimal = MILEAGE_THRESHOLD


def _validate(request: RedeliveryRequest) -> None:
    if request.retraced_miles < 0:
        raise ValueError("retraced_miles cannot be negative")
    if request.customer_fault_count < 0:
        raise ValueError("customer_fault_count cannot be negative")


def _is_billable_reason(request: RedeliveryRequest) -> bool:
    if request.failed_reason in NON_BILLABLE_REASONS:
        return False
    if request.failed_reason not in CUSTOMER_FAULT_REASONS:
        return False
    if request.failed_reason == "no_one_available" and not request.appointment_kept:
        return False
    return True


def _mileage_charge(request: RedeliveryRequest, tariff: RedeliveryTariff) -> Decimal:
    if request.retraced_miles < tariff.mileage_threshold:
        return Decimal("0.00")
    rate = tariff.rural_per_mile_rate if request.is_rural else tariff.per_mile_rate
    return request.retraced_miles * rate


def _base_fee(request: RedeliveryRequest, tariff: RedeliveryTariff) -> Decimal:
    return tariff.minimum_fee + _mileage_charge(request, tariff)


def _apply_residential_rule(amount: Decimal, request: RedeliveryRequest, tariff: RedeliveryTariff) -> Decimal:
    if not request.is_residential or request.customer_fault_count != 1:
        return amount
    reduced = amount / Decimal("2")
    if reduced < tariff.residential_minimum_fee:
        return tariff.residential_minimum_fee
    return reduced


def calculate_redelivery_fee(
    request: RedeliveryRequest, tariff: RedeliveryTariff = RedeliveryTariff()
) -> Decimal:
    """Return the billable redelivery fee in dollars.

    Bill only customer-fault failures. Charge the tariff minimum plus mileage when
    retraced miles meet or exceed the threshold. Residential first failures bill at
    half of the computed fee but not below the residential minimum. Second and later
    customer-fault failures add the repeat-failure surcharge.
    """
    _validate(request)
    if not _is_billable_reason(request):
        return Decimal("0.00")

    amount = _base_fee(request, tariff)
    amount = _apply_residential_rule(amount, request, tariff)
    if request.customer_fault_count >= 2:
        amount += tariff.repeat_failure_surcharge
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
