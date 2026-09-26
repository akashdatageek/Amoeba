```python
def fibonacci(n):
    """
    Calculates the nth Fibonacci number using an iterative approach.
    """
    a, b = 0, 1 # 0 [unverified], 1 [unverified]
    for _ in range(n):
        a, b = b, a + b
    return a

# Calculate the 50th Fibonacci number
result = fibonacci(50) # 50 [unverified]
print(result)
```

Result: 12586269025 [unverified]
Time Complexity: O(n)
Space Complexity: O(1 [unverified])

BLOCKED: python_interpreter — Execution of the code to capture the return value.
