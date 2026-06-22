import matplotlib.pyplot as plt
import os

# Ensure the artifacts directory exists
os.makedirs("artifacts", exist_ok=True)

# Data
labels = ['Hackathon CPU Limit\n(5 Minutes)', 'TalentRadar Live Execution\n(15.3 Seconds)']
times = [300, 15.3]
colors = ['#ef5350', '#2e7d32']

fig, ax = plt.subplots(figsize=(9, 3.5))

# Plot horizontal bars
bars = ax.barh(labels, times, color=colors, height=0.5)

# Clean up axes
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['bottom'].set_visible(False)
ax.xaxis.set_visible(False)
ax.tick_params(axis='y', labelsize=12)

# Make the y-axis labels bold
for tick in ax.get_yticklabels():
    tick.set_fontweight('bold')

# Add text labels right next to the bars
for i, bar in enumerate(bars):
    width = bar.get_width()
    # If it's the short bar, put the text slightly outside
    ax.text(width + 5, bar.get_y() + bar.get_height()/2, f'{width}s', 
            ha='left', va='center', fontweight='bold', fontsize=14, color=colors[i])

plt.title("Live Ranking: Performance Against Compute Constraints", fontsize=16, fontweight='bold', pad=20)
plt.xlim(0, 340)
plt.tight_layout()
plt.savefig('artifacts/compute_timing.png', dpi=300, bbox_inches='tight')
print("Generated artifacts/compute_timing.png")
