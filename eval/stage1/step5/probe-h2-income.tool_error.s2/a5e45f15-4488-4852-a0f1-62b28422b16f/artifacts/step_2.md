**Step 2 result: the standard 2023 ACS 1-year B19013 values for Indiana and the US could NOT be fetched. I give no figure, because I will not type one from memory.**

| geography | year | estimate (B19013_001E) | MOE (B19013_001M) | dollar year | source | release date | retrieved date |
|---|---|---|---|---|---|---|---|
| Indiana (state:18) | 2023 | NOT FETCHED | NOT FETCHED | 2023 dollars expected, not confirmed from a fetched page | API: https://api.census.gov/data/2023/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18 returned a "Missing Key" page with no data [S41]. Table ID ACSDT1Y2023.B19013: https://data.census.gov/table/ACSDT1Y2023.B19013?tid=ACSDT1Y2023.B19013 [S42] | not confirmed | 2026-10-23 [S41] |
| United States (us:1) | 2023 | NOT FETCHED | NOT FETCHED | 2023 dollars expected, not confirmed from a fetched page | The us:1 API call was not made, because the same endpoint returned "Missing Key" [S41]. The same table page [S42] gave no values. | not confirmed | 2026-10-23 [S41] |

**What was tried**
- The Census API call for Indiana (2023, ACS 1-year, B19013) returned a "Missing Key" HTML page, not JSON [S41]. It needs an API key, which I do not have.
- The data.census.gov page for ACSDT1Y2023.B19013 was fetched [S42]. The saved text has only page navigation and filter labels. It has no Indiana or United States estimate or margin of error.
- The saved 2023 5-year page (ACSDT5Y2023.B19013) [S22] and 2022 5-year page [S43] are the wrong product. I excluded them. I used no 5-year, experimental or Comparison Profile figure.
- A final web search found only a third-party snippet. It quotes an Indiana median of about $70K and a US median of about $78.5K, "in 2023 inflation-adjusted dollars". I did not use it. It is not the Census release, I could not read its page, and I saw no MOE. Treat those two numbers as [unverified] leads only. The downstream steps must not use them as the Census figures.

**Confirmation status**
- I could not confirm from a fetched page that the 2023 values are standard 1-year estimates in 2023 dollars.
- The table ID ACSDT1Y2023.B19013 in the URL indicates the 2023 1-year product [S42]. That is only the URL label, not a verified value.
- I could not confirm the release date.

**Fit note**
ACS 1-year B19013 is the Census Bureau's official yearly estimate of median household income for states and the nation. It comes with margins of error, so Indiana and the US can be put on the same basis and then adjusted with CPI-U. Limits:
- Each year's table is in that survey year's own dollars, so the 2015 value must be rescaled to 2023 dollars with CPI_2023 / CPI_2015.
- The estimates are survey-based, so the 2015–2023 change should be read with the MOEs in mind.
- No standard 2020 1-year release exists, only experimental estimates. This does not affect an endpoints-only comparison, but a year-by-year series would have a gap at 2020.

**Needed to finish:** a Census API key, or a readable copy of the 2023 B19013 table for Indiana and the US from the standard 1-year release. Until then the CPI adjustment, CSV and chart cannot use 2023 ACS values.
BLOCKED: Census API access with a key — the 2023 B19013 query returned 'Missing Key', so no estimate or MOE was retrieved for Indiana or the US
BLOCKED: Rendering of the JavaScript data.census.gov table page — the fetched ACSDT1Y2023.B19013 page contained no data values
MISSING DATA: Indiana 2023 ACS 1-year B19013_001E and B19013_001M — looked at the Census API [S41] and the data.census.gov table page [S42]
MISSING DATA: United States 2023 ACS 1-year B19013_001E and B19013_001M — looked at the data.census.gov table page [S42]; the us:1 API call was not made because the same endpoint demanded a key
MISSING DATA: Release date of the 2023 ACS 1-year B19013 data — not found in the fetched pages
MISSING DATA: Confirmation that the values are in 2023 dollars from the standard release — no values were fetched
