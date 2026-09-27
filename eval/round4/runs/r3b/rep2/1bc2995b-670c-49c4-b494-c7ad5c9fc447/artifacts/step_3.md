code:
```python
import matplotlib.pyplot as plt

# Verified totals from Step 2:
# Lane A: 12 [unverified] * 1850 [unverified] = 22200
# Lane B: 7 [unverified] * 2400 [unverified] = 16800
# Lane C: 20 [unverified] * 1420 [unverified] = 28400
# Lane D: 4 [unverified] * 3100 [unverified] = 12400
lanes = ['Lane A', 'Lane B', 'Lane C', 'Lane D']
revenues = [22200, 16800, 28400, 12400]

plt.figure(figsize=(10, 6)) # 10 [unverified], 6 [unverified]
plt.bar(lanes, revenues, color='skyblue')
plt.xlabel('Lane')
plt.ylabel('Total Revenue (USD)')
plt.title('Total Revenue per Lane')
plt.grid(axis='y', linestyle='--', alpha=0.7) # 0.7 [unverified]

plt.savefig('revenue_chart.png')
```
