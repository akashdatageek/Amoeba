def fibonacci(n):
    """
    Calculates the nth Fibonacci number iteratively.
    Time Complexity: O(n)
    Space Complexity: O(1)
    """
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

if __name__ == "__main__":
    n = 50
    result = fibonacci(n)
    print(result)
