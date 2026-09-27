import matplotlib.pyplot as plt

lanes = ['Lane A', 'Lane B', 'Lane C', 'Lane D']
revenues = [22200, 16800, 28400, 12400]

plt.figure(figsize=(10, 6))
plt.bar(lanes, revenues, color='skyblue')
plt.title('Total Revenue per Lane')
plt.xlabel('Lane')
plt.ylabel('Total Revenue')
plt.grid(axis='y', linestyle='--', alpha=0.7)

plt.savefig('revenue_chart.png')
