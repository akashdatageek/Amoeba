```python
import matplotlib.pyplot as plt

# Verified data from Step 2
lanes = ['Lane A', 'Lane B', 'Lane C', 'Lane D']
revenues = [22200, 16800, 28400, 12400] # 22200 [S1], 16800 [S1], 28400 [S1], 12400 [S1]

# Create the bar chart
plt.figure(figsize=(10, 6)) # 10 [unverified], 6 [unverified]
plt.bar(lanes, revenues, color='skyblue')

# Add labels and title
plt.xlabel('Lane')
plt.ylabel('Total Revenue')
plt.title('Total Revenue per Lane')

# Save the plot as a PNG file
plt.savefig('revenue_chart.png')
plt.close()
```

BLOCKED: code_interpreter — Unable to execute the Python code to save the PNG file to the environment.
