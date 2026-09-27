code:
```python
import matplotlib.pyplot as plt

# Verified totals from Step 2 [S1]
lanes = ['Lane A', 'Lane B', 'Lane C', 'Lane D']
revenues = [22200, 16800, 28400, 12400] # [S1]

plt.figure(figsize=(10, 6)) # 10 [unverified], 6 [unverified]
plt.bar(lanes, revenues, color='skyblue')
plt.title('Total Revenue per Lane')
plt.xlabel('Lane')
plt.ylabel('Total Revenue ($)')
plt.grid(axis='y', linestyle='--', alpha=0.7) # 0.7 [unverified]

plt.savefig('revenue_chart.png')
```
local:Bash — Used to generate and verify the PNG file.
