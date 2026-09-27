code:
```python
import matplotlib.pyplot as plt

# Data from verified totals
lanes = ['Lane A', 'Lane B', 'Lane C', 'Lane D']
revenues = [22200, 16800, 28400, 12400]

plt.figure(figsize=(10, 6)) # 10 [unverified], 6 [unverified]
plt.bar(lanes, revenues, color='skyblue')
plt.xlabel('Lane')
plt.ylabel('Total Revenue (USD)')
plt.title('Total Revenue per Lane')

# Adding the values on top of the bars for clarity
for i, v in enumerate(revenues):
    plt.text(i, v + 500, f"${v:,}", ha='center', fontweight='bold') # 500 [unverified]

plt.tight_layout()
plt.savefig('revenue_chart.png')
```
