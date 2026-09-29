def sieve_of_eratosthenes(limit):
    primes_bool = [True] * limit
    primes_bool[0] = primes_bool[1] = False
    for p in range(2, int(limit**0.5) + 1):
        if primes_bool[p]:
            for i in range(p * p, limit, p):
                primes_bool[i] = False
    return [p for p, is_prime in enumerate(primes_bool) if is_prime]

limit = 10000
primes = sieve_of_eratosthenes(limit)
print(f"Count: {len(primes)}")
print(f"Max Prime: {primes[-1]}")
