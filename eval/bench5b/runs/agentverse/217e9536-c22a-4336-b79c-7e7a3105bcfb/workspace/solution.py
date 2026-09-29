def find_primes(limit):
    if limit < 2:
        return []
    
    # Sieve of Eratosthenes using bytearray for efficiency
    sieve = bytearray([1]) * limit
    sieve[0] = sieve[1] = 0
    
    for i in range(2, int(limit**0.5) + 1):
        if sieve[i]:
            # Mark multiples of i starting from i*i as non-prime
            sieve[i*i : limit : i] = bytearray([0]) * len(range(i*i, limit, i))
            
    return [i for i, is_prime in enumerate(sieve) if is_prime]

limit = 10000
primes = find_primes(limit)
print(f"Number of primes below {limit}: {len(primes)}")
print(f"Largest prime below {limit}: {primes[-1]}")
