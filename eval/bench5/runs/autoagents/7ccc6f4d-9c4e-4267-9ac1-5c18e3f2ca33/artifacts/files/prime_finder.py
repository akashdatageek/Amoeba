def sieve_of_eratosthenes(limit):
    primes = []
    is_prime = [True] * limit
    if limit > 0: is_prime[0] = False
    if limit > 1: is_prime[1] = False
    for p in range(2, int(limit**0.5) + 1):
        if is_prime[p]:
            for i in range(p * p, limit, p):
                is_prime[i] = False
    for p in range(2, limit):
        if is_prime[p]:
            primes.append(p)
    return primes

if __name__ == "__main__":
    limit = 10000
    primes = sieve_of_eratosthenes(limit)
    print(f"Primes: {primes}")
    print(f"Total Count: {len(primes)}")
    print(f"Largest Prime: {primes[-1]}")
