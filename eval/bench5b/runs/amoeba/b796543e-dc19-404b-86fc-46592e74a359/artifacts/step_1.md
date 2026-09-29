memo: execution_results
# Execution Results

## Source Code
```python
def sieve_of_eratosthenes(limit):
    primes_bool = [True] * limit
    primes_bool[0] = primes_bool[1] = False # 0 [unverified], 1 [unverified]
    for p in range(2, int(limit**0.5) + 1): # 2 [unverified], 0.5 [unverified], 1 [unverified]
        if primes_bool[p]:
            for i in range(p * p, limit, p):
                primes_bool[i] = False
    return [p for p, is_prime in enumerate(primes_bool) if is_prime]

limit = 10000
primes = sieve_of_eratosthenes(limit)
print(f"Count: {len(primes)}")
print(f"Max Prime: {primes[-1]}") # -1 [unverified]
```

## Metrics
- Total count of primes: 1,229 [S1]
- Largest prime found: 9,973 [S1]
