code:
```python
import matplotlib.pyplot as plt

# Verified total revenue data
lanes = ['Lane A', 'Lane B', 'Lane C', 'Lane D']
revenues = [
    22200, # [S1]
    16800, # [S2]
    28400, # [S3]
    12400  # [S4]
]

# Figure size: 10 [unverified], 6 [unverified]
plt.figure(figsize=(10, 6)) 
plt.bar(lanes, revenues, color='skyblue')
plt.xlabel('Lane')
plt.ylabel('Total Revenue')
plt.title('Total Revenue per Lane')
plt.grid(axis='y', linestyle='--', alpha=0.7)

plt.savefig('revenue_chart.png')
```
