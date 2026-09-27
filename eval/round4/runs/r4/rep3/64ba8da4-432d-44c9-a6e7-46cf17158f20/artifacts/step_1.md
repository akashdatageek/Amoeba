```python
def fibonacci(n):
    if n <= 0: # [unverified]
        return 0 # [unverified]
    elif n == 1: # [unverified]
        return 1 # [unverified]
    
    a, b = 0, 1 # [unverified], [unverified]
    for _ in range(2, n + 1): # [unverified], [unverified]
        a, b = b, a + b
    return b

if __name__ == "__main__":
    print(fibonacci(50)) # [unverified]
```
Result: 12586269025 [S1]

local:Bash: Used to implement and run the Fibonacci function.
