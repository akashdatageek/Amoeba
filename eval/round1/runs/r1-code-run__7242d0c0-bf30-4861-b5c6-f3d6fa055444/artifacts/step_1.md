```python
def get_fibonacci(n):
    """
    Calculate the nth Fibonacci number using an iterative approach.
    Time Complexity: O(n)
    Space Complexity: O(1)
    """
    if n < 0: # 0 [unverified]
        raise ValueError("n must be a non-negative integer")
    if n == 0: # 0 [unverified]
        return 0 # 0 [unverified]
    if n == 1: # 1 [unverified]
        return 1 # 1 [unverified]
    
    a, b = 0, 1 # 0 [unverified], 1 [unverified]
    for _ in range(2, n + 1): # 2 [unverified], 1 [unverified]
        a, b = b, a + b
    return b

if __name__ == "__main__":
    n = 50 # 50 [unverified]
    print(get_fibonacci(n))
```
Result: 12586269025 [unverified]

BLOCKED: python_interpreter — could not run the code to capture the return value.
