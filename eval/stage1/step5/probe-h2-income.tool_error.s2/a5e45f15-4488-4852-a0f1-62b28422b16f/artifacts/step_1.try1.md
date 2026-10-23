**Step 1: standard ACS 1-year B19013 for 2015. No values were fetched.**

The Census API returned "Missing Key" on both fetches that reached it. These are the two sources, [S1] and [S2]. The other fetches and the web search failed with an injected fault. No data.census.gov table page or Census release page was reached. I have not typed any estimate or margin of error (MOE) from memory.

| geography | year | estimate (B19013_001E) | MOE (B19013_001M) | dollar year | source (URL / table ID) | release date | retrieved date |
|---|---|---|---|---|---|---|---|
| Indiana (state:18) | 2015 | NOT FETCHED | NOT FETCHED | 2015 dollars expected, not confirmed | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=state:18,us:1 (table B19013). Attempt returned "Missing Key" [S1]. | not confirmed (not fetched) | 2026-10-23 (attempt only; no data returned) [S1] |
| United States (us:1) | 2015 | NOT FETCHED | NOT FETCHED | 2015 dollars expected, not confirmed | https://api.census.gov/data/2015/acs/acs1?get=NAME,B19013_001E,B19013_001M&for=us:1 (table B19013). Attempt returned "Missing Key" [S2]. | not confirmed (not fetched) | 2026-10-23 (attempt only; no data returned) [S2] |

**What is confirmed**
- The Census API for the 2015 ACS 1-year dataset (/data/2015/acs/acs1) is reachable. It now requires a valid API key on every request [S1][S2].
- Whether the release is standard 1-year and in 2015 dollars is not confirmed from a fetched page. The planned design, standard 1-year B19013 for 2015, is expected to be in 2015 dollars. That is still unverified.

**Fit note**
- ACS 1-year B19013 fits this comparison for two reasons. It is the Census Bureau's official annual median household income estimate for both a state and the nation. Each estimate comes with an MOE.
- Limits:
  - It is a survey estimate with sampling error, so the MOE matters when comparing 2015 and 2023.
  - It is in the survey year's dollars, so it must be CPI-adjusted to 2023 dollars.
  - The 2020 standard 1-year release does not exist, but that does not affect the 2015 and 2023 endpoints.

**To finish this step**
- Rerun the two API calls with a valid Census API key (add &key=...).
- Or fetch the data.census.gov B19013 table page for the 2015 ACS 1-year release.
- Then record the release date and confirm the values are standard 1-year estimates in 2015 dollars.
BLOCKED: Census API key / working Census data access — the API returned 'Missing Key' for the 2015 B19013 requests, and the data.census.gov and release-page fallback could not be reached because web_search and fetch_url failed with an injected fault
MISSING DATA: Indiana 2015 ACS 1-year B19013_001E and B19013_001M — tried the Census API (Missing Key) [S1]
MISSING DATA: United States 2015 ACS 1-year B19013_001E and B19013_001M — tried the Census API (Missing Key) [S2]
MISSING DATA: 2015 ACS 1-year release date — not reached; no release page was fetched
MISSING DATA: Confirmation that the values are standard 1-year estimates in 2015 dollars — no data page was fetched
