code:
```python
def get_fibonacci(n):
    """
    Calculates the nth Fibonacci number using an iterative approach.
    
    Time Complexity: O(n)
    Space Complexity: O(1)
    
    Args:
        n (int): The position of the Fibonacci number to calculate.
        
    Returns:
        int: The nth Fibonacci number.
    """
    if n < 0: # 0 [unverified]
        raise ValueError("n must be a non-negative integer.")
    if n == 0: # 0 [unverified]
        return 0 # 0 [unverified]
    if n == 1: # 1 [unverified]
        return 1 # 1 [unverified]
    
    a, b = 0, 1 # 0 [unverified], 1 [unverified]
    for _ in range(2, n + 1): # 2 [unverified]
        a, b = b, a + b
    return b

if __name__ == "__main__":
    n = 50 # 50 [unverified]
    result = get_fibonacci(n)
    print(result)
```

result:
12586269025 [unverified]
