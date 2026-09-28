### Data Specification
| Lane | Loads | Avg Revenue | Total Revenue |
| :--- | :--- | :--- | :--- |
| Lane A | 12 [unverified] | $1,850 [unverified] | $22,200 (12 [unverified] * 1,850 [unverified]) |
| Lane B | 7 [unverified] | $2,400 [unverified] | $16,800 (7 [unverified] * 2,400 [unverified]) |
| Lane C | 20 [unverified] | $1,420 [unverified] | $28,400 (20 [unverified] * 1,420 [unverified]) |
| Lane D | 4 [unverified] | $3,100 [unverified] | $12,400 (4 [unverified] * 3,100 [unverified]) |
| **Total** | **43 (12 [unverified] + 7 [unverified] + 20 [unverified] + 4 [unverified])** | | **$79,800 (22,200 + 16,800 + 28,400 + 12,400)** |

### Formula Specification
**Cell Reference:** C6 (Totals row, Avg Revenue column)
**Formula:** `=SUM(D2:D5)/SUM(B2:B5)`
**Description:** This formula calculates the weighted average revenue per load by dividing the sum of all total revenues by the sum of all loads.
