def sieve_of_eratosthenes(limit):
    primes_mask = [True] * limit
    if limit > 0:
        primes_mask[0] = False
    if limit > 1:
        primes_mask[1] = False
    
    for p in range(2, int(limit**0.5) + 1):
        if primes_mask[p]:
            for i in range(p * p, limit, p):
                primes_mask[i] = False
    
    return [p for p, is_prime in enumerate(primes_mask) if is_prime]

if __name__ == "__main__":
    limit = 10000
    primes = sieve_of_eratosthenes(limit)
    print(f"Primes: {primes}")
    print(f"Count: {len(primes)}")
    print(f"Max Prime: {primes[-1] if primes else None}")
