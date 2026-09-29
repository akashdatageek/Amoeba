def find_primes(limit):
    if limit < 2:
        return []
    
    is_prime = [True] * limit
    is_prime[0] = is_prime[1] = False
    
    for p in range(2, int(limit**0.5) + 1):
        if is_prime[p]:
            for i in range(p * p, limit, p):
                is_prime[i] = False
                
    return [p for p, prime in enumerate(is_prime) if prime]

primes = find_primes(10000)
print(f"Count: {len(primes)}")
print(f"Largest: {primes[-1]}")
