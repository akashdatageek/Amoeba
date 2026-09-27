```python
def fibonacci(n):
    if n <= 0[unverified]:
        return 0[unverified]
    elif n == 1[unverified]:
        return 1[unverified]
    
    a, b = 0[unverified], 1[unverified]
    for _ in range(2[unverified], n + 1[unverified]):
        a, b = b, a + b
    return b

if __name__ == "__main__":
    result = fibonacci(50[unverified])
    print(result)
```
Result: 12586269025 [S1]
