**Result: the 2015 standard ACS 1-year B19013 values for Indiana and the US were NOT fetched. I have not typed any figure from memory.**

| geography | year | estimate (B19013_001E) | MOE (B19013_001M) | dollar year | source | release date | retrieved date |
|---|---|---|---|---|---|---|---|
| Indiana (state:18 / 04000US18) | 2015 | NOT FETCHED | NOT FETCHED | 2015 expected, but not confirmed from a table title | Census Reporter mirror (not the original): https://censusreporter.org/data/table/?table=B19013&geo_ids=04000US18,01000US&primary_geo_id=04000US18&release=acs2015_1yr [S28]. Original table ID: ACS 2015 1-year B19013 | not found | 2026-10-23 [S28] |
| United States (us:1 / 01000US) | 2015 | NOT FETCHED | NOT FETCHED | 2015 expected, but not confirmed from a table title | Same Census Reporter mirror URL [S28]. Original table ID: ACS 2015 1-year B19013 | not found | 2026-10-23 [S28] |

What happened:
- The keyless Census API call, https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18,us:1, returned a "Missing Key" page, not data [S1, S30].
- The Census Reporter page was fetched [S28]. The saved text is only the page shell: a citation template with placeholders such as "TABLE NAME" and "RELEASE YEAR", and no Indiana or United States data rows [S31]. The page header reads "Table B19013 (ACS 2015 1-Year)" [S28], but the full table title with "in 2015 inflation-adjusted dollars" was not retrieved. So the 2015-dollar basis is not confirmed from the table title here.
- Other saved sources (S4, S5, S6, S10, S11, S12, S20) were searched for Indiana and B19013 values. They gave no usable 2015 1-year Indiana or US estimate and MOE. S4 is a 5-year table page for another geography and is not usable.

Fit note: ACS 1-year B19013 is the Census Bureau's standard annual median household income estimate for states and the nation. It is published with margins of error, so it suits an Indiana vs US comparison. Its limits are that it is a sample survey, so the MOE matters, and each year is stated in that year's dollars. A later step needs the CPI-U to put the 2015 and 2023 values on the same 2023-dollar basis.

What the work-around does not cover: the 2015 estimates, MOEs, the release date and the dollar-year confirmation. The Census Reporter data grid is loaded by JavaScript and did not come through the text fetch. A later step needs a source that returns the values, such as the Census API with a key, a data.census.gov table page, or a Census Reporter API/CSV download. Until then the 2015 rows must not be used in any calculation.
BLOCKED: Census API with a key — the keyless 2015 acs1 call returned 'Missing Key', so no B19013 values came back
BLOCKED: data.census.gov table page fetch — not available in this run; the Census Reporter mirror page returned only a shell with no data rows
MISSING DATA: Indiana 2015 B19013_001E and B19013_001M — Census API (Missing Key), Census Reporter acs2015_1yr page S28 (no data rows), saved sources S4/S5/S6/S10/S11/S12/S20
MISSING DATA: United States 2015 B19013_001E and B19013_001M — same sources
MISSING DATA: 2015 ACS 1-year release date — not found in any fetched source
MISSING DATA: Full table title confirming 2015 inflation-adjusted dollars — Census Reporter page showed only a placeholder title
