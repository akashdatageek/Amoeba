## Python Function
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
```

## Result
The 50th Fibonacci number is 12586269025 [S1].

## Limitations
Step 1 contains [unverified] figures regarding Space Complexity, the initialization of variables `a` and `b`, and the value of `n`.
