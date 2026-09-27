## Final Summary
memo:
- project_status: Failed
- details:
    - conversion_result: 239,550 INR [S3]
    - email_status: Not sent to test@example.com

R1: 95.82 [S3]
R2: 239,550 INR [S3] (from $2,500 [S2])
R3: Not sent

## Limitations
- Step 2: FAIL; lacked `currency_api` to verify rate 95.82 [S3] and result 239,550 INR [S3].
- Step 3: Email not sent due to Step 2 failure.
