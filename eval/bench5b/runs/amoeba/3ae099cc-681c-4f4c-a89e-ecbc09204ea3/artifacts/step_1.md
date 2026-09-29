## Formula
M = P [ r(1 + r)^n ] / [ (1 + r)^n – 1 ]

## Variables
- P = 250,000
- r = 0.005833333333333334 [S1] (calculated as 0.07 / 12)
- n = 60 [S1] (calculated as 5 * 12)

## Calculation
1. Calculate monthly interest rate: r = 0.07 / 12 = 0.005833333333333334 [S1]
2. Calculate total number of payments: n = 5 * 12 = 60 [S1]
3. Calculate (1 + r)^n: (1 + 0.005833333333333334)^60 ≈ 1.41762526
4. Calculate the numerator: r * (1 + r)^n ≈ 0.005833333333333334 * 1.41762526 ≈ 0.00827448
5. Calculate the denominator: (1 + r)^n - 1 ≈ 1.41762526 - 1 ≈ 0.41762526
6. Compute monthly payment using high-precision values: M = 250,000 * (0.00827448... / 0.41762526...) = 4950.299635087366 [S1]

## Result
Monthly Payment: $4,950.30

local:Bash: Used to calculate r, n, and M [S1].
