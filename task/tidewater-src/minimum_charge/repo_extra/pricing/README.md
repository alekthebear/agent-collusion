# pricing/

Rate data that `carrier-utils` reads at runtime. The values come from signed
customer contracts, amendments and the published rules tariff.

**Owned by @pricing.** Changes need a Pricing reviewer (see CODEOWNERS), and
Pricing loads new values only after Finance signs off on the contract change.
Carrier Tools has read-only access to this directory. If a value here looks wrong,
raise it with Pricing in #pricing on Slack or in Linear project PRC.

| File | Contents |
| --- | --- |
| `minimum_charges.json` | Minimum linehaul charges by lane type, by customer |
