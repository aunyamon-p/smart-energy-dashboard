# Pre-Step 3.5: Thai Public Holiday API Feasibility Test

## Scope

This step tests whether Nager.Date can provide Thailand public-holiday data
for 2018 and whether it is safe to use as a Holiday feature. It does not
modify the Raw Dataset, Step 2 outputs, `process_dataset.py`, or any backend
API. The Holiday Model experiment was not run because the API data did not
pass the required completeness gate.

## Nager.Date request

- Endpoint: `https://date.nager.at/api/v3/PublicHolidays/2018/TH`
- HTTP status from the repeatable Python client: `204 No Content`
- Response body from the repeatable Python client: empty
- Response schema: invalid for this use because no JSON array was returned
- Item count: not available
- Duplicate dates: none (there are no items)
- Date range: not applicable; no dates were returned
- Required holiday fields: not testable because there are no records

A separate command-line probe in the same session received HTTP `200` with an
empty JSON array (`[]`). This response variation does not make the endpoint
usable: both observations contain zero holiday records. The saved evidence is
from the repeatable Python script and records the `204` response and empty
body.

The exact captured response and validation metadata are in
`backend/data/external/thai_public_holidays_nager_2018.json`.

The repeatable test script is
`backend/test_thai_holidays.py`. It exits with code `2` when the response is
not usable for modeling, which makes the failure explicit rather than
silently treating an empty holiday calendar as a valid calendar.

## External cross-check

The secondary reference [Office Holidays Thailand 2018](https://www.officeholidays.com/countries/thailand/2018)
lists 2018 dates including:

- National/ordinary holidays such as Jan 1, Mar 1, Apr 6, Apr 12-16,
  May 1, May 29, Jul 27, Aug 13, Oct 15, Oct 23, Dec 5, Dec 10, and Dec 31.
- Compensation/observed days such as Jan 2, Aug 13, and Oct 15.
- Government or special/observance entries such as May 14 and Jul 27.
- Regional Chinese New Year on Feb 16 for specified southern provinces.

This cross-check demonstrates that an empty Nager response is not a complete
2018 Thailand holiday calendar. Office Holidays is a secondary reference, not
a primary Thai government publication; therefore it is used only as evidence
of the API gap, not as an automatic replacement dataset.

Holiday classification must remain explicit in a future integration:

- **Regular/public holiday:** a national holiday applicable to the target
  calendar.
- **Compensation/observed holiday:** a substitute weekday because the actual
  holiday falls on a weekend.
- **Special/government/ regional holiday:** applicable only under its stated
  scope and should not be applied to every building without confirmation.

The Nager response contains no records and therefore provides no reliable
classification for any of these categories.

## Model experiment decision

Model A vs Model B with a Holiday feature was **not run**. The requested
stop condition applies: the API returned an empty 2018 dataset, so adding a
Holiday feature would either omit known holidays or require inventing/filling
dates. Both would make the experiment invalid and could create false
negatives by treating holidays as ordinary weekdays.

Consequently, there are no valid before/after Alert Event or Severity counts
for this step. Existing Step 2 alert counts remain unchanged and were not
recomputed:

- Alert Events: `23,123`
- High: `10,310`
- Medium: `4,639`
- Low: `8,174`

These are preserved as reference only; they are not results of a holiday
adjustment.

## Risks and recommendation

Using the empty response as a valid feature would mark all 2018 dates as
non-holidays. This could raise false positives on holidays, distort the
weekday/time baseline, and potentially miss anomalies if expected usage were
incorrectly relaxed. A lower alert count alone would not demonstrate an
improvement.

Recommendation: do not integrate Nager.Date for 2018 Thailand until its
historical coverage is corrected and independently validated against a
primary or authoritative Thai calendar. If a future source passes validation,
keep separate fields for `is_public_holiday`, `is_compensation_day`,
`is_special_or_regional`, and `holiday_name`, and evaluate alert recall,
precision proxies, severity changes, and missed-event risk—not just alert
volume.

## Tests

Passed:

- Direct Python syntax compilation.
- Live request reached Nager.Date and returned `204 No Content` through the
  repeatable client; an independent command-line probe returned `200` with
  an empty array.
- JSON parsing and empty-array detection.
- Validation correctly rejected the response for model use.
- Raw Dataset and Step 2 outputs were not written by this step.

Not run by design:

- Holiday-feature Model A vs Model B comparison.
- Any change to anomaly detection or alert generation.
