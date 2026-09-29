def find_primes(limit):
    if limit < 2:
        return []
    
    # We only track odd numbers to save space and time.
    # The number of odd integers from 3 up to limit-1.
    # If limit is 10,000, odd numbers are 1, 3, 5, ..., 9999.
    # Index 0 corresponds to 1, Index 1 to 3, Index 2 to 5, etc.
    # Formula: prime = 2 * index + 1
    size = (limit - 1) // 2
    # Use bytearray for memory efficiency. 1 represents prime, 0 represents non-prime.
    sieve = bytearray([1]) * (size + 1)
    sieve[0] = 0  # 1 is not prime
    
    for i in range(1, int(limit**0.5) // 2 + 1):
        if sieve[i]:
            p = 2 * i + 1
            # Mark multiples of p starting from p*p.
            # Index of p*p is (p*p - 1) // 2.
            start = (p * p - 1) // 2
            # Use slice assignment with a bytearray of zeros to avoid temporary lists.
            sieve[start::p] = bytearray(len(sieve[start::p]))
            
    # Convert indices back to prime numbers, starting with 2.
    primes = [2] + [2 * i + 1 for i in range(1, size + 1) if sieve[i]]
    
    # Ensure we only return primes strictly below the limit.
    return [p for p in primes if p < limit]

limit = 10000
primes_list = find_primes(limit)
print(f"Count: {len(primes_list)}")
print(f"Largest: {primes_list[-1]}")
