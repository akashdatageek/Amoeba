code:
```python
import matplotlib.pyplot as plt

# Data from verified report
lanes = ['Lane A', 'Lane B', 'Lane C', 'Lane D']
revenues = [22200, 16800, 28400, 12400]

plt.figure(figsize=(10, 6)) # 10 [unverified], 6 [unverified]
plt.bar(lanes, revenues, color='skyblue')
plt.xlabel('Lane')
plt.ylabel('Total Revenue')
plt.title('Total Revenue per Lane')
plt.grid(axis='y', linestyle='--', alpha=0.7)

# Save the plot as a PNG
plt.savefig('revenue_chart.png')
```
