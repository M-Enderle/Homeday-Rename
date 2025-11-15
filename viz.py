import numpy as np
from sklearn.model_selection import train_test_split

import matplotlib.pyplot as plt

# Generate random x values
np.random.seed(42)  # For reproducibility
x = np.random.uniform(-10, 10, 100)

# Generate y values based on y = x^2 with some random noise
noise = np.random.normal(0, 5, x.shape)
y = x**2 + noise

# Split the data into training and testing sets
x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42)

# Plot the data
plt.figure(figsize=(10, 6))
plt.scatter(x_train, y_train, color='blue', label='Training Data')
plt.scatter(x_test, y_test, color='red', label='Testing Data')
plt.title('Random Data Based on y = x^2')
plt.xlabel('x')
plt.ylabel('y')
plt.legend()
plt.grid(True)
plt.show()