import matplotlib.pyplot as plt

lanes = ['Lane A', 'Lane B', 'Lane C', 'Lane D']
revenues = [22200, 16800, 28400, 12400]

plt.figure(figsize=(10, 6))
plt.bar(lanes, revenues, color='skyblue')
plt.xlabel('Lane')
plt.ylabel('Total Revenue ($)')
plt.title('Total Revenue per Lane')
plt.grid(axis='y', linestyle='--', alpha=0.7)

# Adding value labels on top of each bar
for i, v in enumerate(revenues):
    plt.text(i, v + 500, f"${v:,}", ha='center', fontweight='bold')

plt.savefig('revenue_chart.png')
