code:
```python
import matplotlib.pyplot as plt

# Verified total revenue data
# Lane A: 12 * 1850 = 22200
# Lane B: 7 * 2400 = 16800
# Lane C: 20 * 1420 = 28400
# Lane D: 4 * 3100 = 12400
lanes = ['Lane A', 'Lane B', 'Lane C', 'Lane D']
revenues = [22200, 16800, 28400, 12400]

plt.figure(figsize=(10 [unverified], 6 [unverified]))
plt.bar(lanes, revenues, color='skyblue')
plt.title('Total Revenue per Lane')
plt.xlabel('Lane')
plt.ylabel('Total Revenue')
plt.grid(axis='y', linestyle='--', alpha=0.7)

plt.savefig('revenue_chart.png')
```
local:Bash: Used to generate the PNG file.
