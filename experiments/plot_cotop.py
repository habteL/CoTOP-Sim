import csv
import matplotlib.pyplot as plt
import numpy as np
import os

metrics_path = os.path.join(
    os.path.dirname(__file__), '..', 'results', 'train_metrics.csv')

episodes, rewards, completions = [], [], []

with open(metrics_path) as f:
    for row in csv.DictReader(f):
        episodes.append(int(row['episode']))
        rewards.append(float(row['total_reward']))
        completions.append(float(row['completion_ratio']))

window = 10
def rolling(data, w):
    return [np.mean(data[max(0,i-w+1):i+1]) for i in range(len(data))]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

ax1.plot(episodes, rewards, alpha=0.3, color='blue', label='Episode reward')
ax1.plot(episodes, rolling(rewards, window), color='blue',
         linewidth=2, label=f'{window}-ep moving avg')
ax1.axhline(-197.05, color='orange', linestyle='--',
            label='Always Collaborate baseline')
ax1.axhline(-208.08, color='red', linestyle='--',
            label='Always Standalone baseline')
ax1.set_ylabel('Total Reward')
ax1.set_title('CoTOP A3C Training — Reward Convergence')
ax1.legend()
ax1.grid(alpha=0.3)

ax2.plot(episodes, completions, alpha=0.3, color='green')
ax2.plot(episodes, rolling(completions, window), color='green',
         linewidth=2, label=f'{window}-ep moving avg')
ax2.axhline(0.616, color='red', linestyle='--', label='Baseline')
ax2.set_xlabel('Episode')
ax2.set_ylabel('Completion Ratio')
ax2.set_title('Task Completion Ratio')
ax2.legend()
ax2.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(os.path.dirname(__file__),
            '..', 'results', 'learning_curve_cotop.png'), dpi=300)
plt.show()
print("Saved: results/learning_curve_cotop.png")