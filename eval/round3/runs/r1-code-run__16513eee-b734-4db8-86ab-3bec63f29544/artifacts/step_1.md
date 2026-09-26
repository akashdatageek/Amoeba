```python
def fibonacci(n):
    if n <= 0: # 0 [unverified]
        return 0 # 0 [unverified]
    elif n == 1: # 1 [unverified]
        return 1 # 1 [unverified]
    
    a, b = 0, 1 # 0 [unverified], 1 [unverified]
    for _ in range(2, n + 1): # 2 [unverified], 1 [unverified]
        a, b = b, a + b
    return b

if __name__ == "__main__":
    n = 50 # 50 [unverified]
    print(fibonacci(n))
```
Result: 12586269025 [S1]
