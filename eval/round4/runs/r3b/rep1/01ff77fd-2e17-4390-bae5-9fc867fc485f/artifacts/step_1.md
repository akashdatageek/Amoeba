```python
def fibonacci(n):
    """
    Calculates the nth Fibonacci number iteratively.
    Time Complexity: O(n)
    Space Complexity: O(1) # [unverified]
    """
    a, b = 0, 1 # [unverified], [unverified]
    for _ in range(n):
        a, b = b, a + b
    return a

if __name__ == "__main__":
    n = 50 # [unverified]
    result = fibonacci(n)
    print(result)
```
Result: 12586269025 [S1]
