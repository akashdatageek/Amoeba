code:
```python
import matplotlib.pyplot as plt

# Verified total revenue data
lanes = ['Lane A', 'Lane B', 'Lane C', 'Lane D']
revenues = [22200, 16800, 28400, 12400] # 22200 [unverified], 16800 [unverified], 28400 [unverified], 12400 [unverified]

plt.figure(figsize=(10, 6)) # 10 [unverified], 6 [unverified]
plt.bar(lanes, revenues, color='skyblue')
plt.xlabel('Lane')
plt.ylabel('Total Revenue ($)')
plt.title('Total Revenue per Lane')
plt.grid(axis='y', linestyle='--', alpha=0.7)

# Adding value labels on top of each bar
for i, v in enumerate(revenues):
    plt.text(i, v + 500, f"${v:,}", ha='center', fontweight='bold') # 500 [unverified]

plt.savefig('revenue_chart.png')
```
