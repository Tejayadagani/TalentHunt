import matplotlib.pyplot as plt
import numpy as np
import os

# Ensure the artifacts directory exists
os.makedirs("artifacts", exist_ok=True)

# ==========================================
# 1. Bar Chart: Config A vs Config C
# ==========================================
labels = ['Composite Score', 'NDCG@10']
initial_scores = [0.8160, 0.7786]
final_scores = [0.8652, 0.8354]

x = np.arange(len(labels))
width = 0.35

fig, ax = plt.subplots(figsize=(8, 5))
rects1 = ax.bar(x - width/2, initial_scores, width, label='Initial Weights (40% Semantic)', color='#b0bec5')
rects2 = ax.bar(x + width/2, final_scores, width, label='Final Weights (30/30/20/20)', color='#1976d2')

ax.set_ylabel('Score (0.0 to 1.0)', fontsize=12)
ax.set_title('Empirical Validation: Ranking Quality Improvement', fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=12, fontweight='bold')
ax.set_ylim(0.75, 0.88)
ax.legend(fontsize=11, loc='upper left')

# Add text labels on bars
def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height:.4f}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=11, fontweight='bold')

autolabel(rects1)
autolabel(rects2)

fig.tight_layout()
plt.savefig('artifacts/validation_chart.png', dpi=300, bbox_inches='tight')
print("Generated artifacts/validation_chart.png")
plt.close()

# ==========================================
# 2. Rank-Flip Visualization Diagram
# ==========================================
fig, ax = plt.subplots(figsize=(10, 5))
ax.axis('off')

# Candidate A (The Fluent Talker)
ax.add_patch(plt.Rectangle((0.05, 0.55), 0.4, 0.35, facecolor='#ffebee', edgecolor='#c62828', lw=2, alpha=0.8))
ax.text(0.25, 0.80, "Candidate A\n(The 'Fluent Talker')", ha='center', va='center', fontsize=13, fontweight='bold', color='#c62828')
ax.text(0.25, 0.65, "Semantic Score: 0.92\nVerified Skill Score: 0.18", ha='center', va='center', fontsize=12)

# Candidate B (The Quiet Expert)
ax.add_patch(plt.Rectangle((0.55, 0.55), 0.4, 0.35, facecolor='#e8f5e9', edgecolor='#2e7d32', lw=2, alpha=0.8))
ax.text(0.75, 0.80, "Candidate B\n(The 'Quiet Expert')", ha='center', va='center', fontsize=13, fontweight='bold', color='#2e7d32')
ax.text(0.75, 0.65, "Semantic Score: 0.61\nVerified Skill Score: 0.30", ha='center', va='center', fontsize=12)

# Arrows and Text for Initial vs Final
ax.text(0.5, 0.40, "Under Initial Weights (40% Semantic):", ha='center', va='center', fontsize=13, fontweight='bold')
ax.text(0.5, 0.30, "Candidate A Outranked Candidate B ❌", ha='center', va='center', fontsize=14, color='#c62828', fontweight='bold')

ax.text(0.5, 0.15, "Under Final Weights (30/30/20/20):", ha='center', va='center', fontsize=13, fontweight='bold')
ax.text(0.5, 0.05, "Candidate B Correctly Outranks Candidate A ✅", ha='center', va='center', fontsize=14, color='#2e7d32', fontweight='bold')

plt.title("The 'Rank-Flip' Correction Methodology", fontsize=16, fontweight='bold', pad=20)
fig.tight_layout()
plt.savefig('artifacts/rank_flip_diagram.png', dpi=300, bbox_inches='tight')
print("Generated artifacts/rank_flip_diagram.png")
plt.close()
