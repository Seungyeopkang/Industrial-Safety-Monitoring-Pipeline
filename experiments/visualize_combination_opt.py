"""Visualize combined-prompt optimization results - Sprint 2 deep dive.

Focuses on: single vs combined variant comparison, Pareto front (quality vs
latency), and the final adopted decision highlighted.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "outputs" / "results" / "prompt_optimization_results.json"
OUT_IMG = ROOT / "outputs" / "results" / "prompt_combination_optimization.png"

d = json.loads(RESULTS.read_text(encoding="utf-8"))
vlm = sorted(d.get("vlm", []), key=lambda x: -x["rubric"]["total"])
llm = sorted(d.get("llm", []), key=lambda x: -x["rubric"]["total"])

# classify variants
SINGLE = {"default", "role_stepwise", "fewshot", "constraints"}
COMBINED = {"role_constraints", "role_constraints_fewshot", "safety_first"}

fig, axes = plt.subplots(2, 2, figsize=(16, 11))
fig.suptitle("Sprint 2 - Prompt Combination & Optimization Decision (Gemini 2.5 Flash)",
             fontsize=15, fontweight="bold", y=0.995)

# 1) Single vs Combined: rubric grouped bar
ax = axes[0, 0]
single = [v for v in vlm if v["variant"] in SINGLE]
combined = [v for v in vlm if v["variant"] in COMBINED]
labels = [v["variant"] for v in single] + ["---"] + [v["variant"] for v in combined]
scores = [v["rubric"]["total"] for v in single] + [0] + [v["rubric"]["total"] for v in combined]
colors = ["#3498db"] * len(single) + ["#aaaaaa"] + ["#e67e22"] * len(combined)
bars = ax.bar(range(len(labels)), scores, color=colors)
ax.set_title("Single (blue) vs Combined (orange) Variant Rubric", fontweight="bold")
ax.set_ylabel("Rubric Total (max 12)")
ax.set_xticks(range(len(labels)))
ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
ax.set_ylim(0, 12)
for b, s in zip(bars, scores):
    if s > 0:
        ax.text(b.get_x() + b.get_width()/2, s + 0.2, str(s), ha="center", fontweight="bold")
ax.grid(axis="y", linestyle="--", alpha=0.5)

# 2) Pareto front: latency vs rubric, highlight adopted
ax = axes[0, 1]
for v in vlm:
    is_combined = v["variant"] in COMBINED
    is_adopted = v["variant"] == "role_constraints"
    color = "#e74c3c" if is_adopted else ("#e67e22" if is_combined else "#3498db")
    size = 220 if is_adopted else 140
    ax.scatter(v["latency_ms"]/1000, v["rubric"]["total"], s=size, color=color, zorder=3,
               edgecolors="black", linewidths=1.5 if is_adopted else 0)
    ax.annotate(v["variant"], (v["latency_ms"]/1000, v["rubric"]["total"]),
                xytext=(7, 7), textcoords="offset points", fontsize=8,
                fontweight="bold" if is_adopted else "normal")
ax.set_title("Pareto: Latency vs Quality (red=adopted role_constraints)", fontweight="bold")
ax.set_xlabel("Latency (s)")
ax.set_ylabel("Rubric (max 12)")
ax.set_ylim(0, 12)
ax.grid(linestyle="--", alpha=0.5)
# legend
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#3498db", label="single"), Patch(color="#e67e22", label="combined"),
                    Patch(color="#e74c3c", label="adopted")], fontsize=8, loc="lower right")

# 3) VLM sub-rubric radar-ish grouped: top 3 variants
ax = axes[1, 0]
top3 = vlm[:3]
metrics = ["worker_coverage", "ppe_specificity", "context_richness", "danger_awareness"]
x = np.arange(len(metrics)); w = 0.25
bar_colors = ["#2ecc71", "#e67e22", "#9b59b6"]
for i, v in enumerate(top3):
    vals = [v["rubric"][m] for m in metrics]
    bars = ax.bar(x + i*w - w, vals, w, label=v["variant"], color=bar_colors[i])
ax.set_title("VLM Sub-Rubric of Top 3 Variants", fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(metrics, rotation=15, fontsize=8)
ax.set_ylabel("Score (0-3)")
ax.set_ylim(0, 3.2)
ax.legend(fontsize=8); ax.grid(axis="y", linestyle="--", alpha=0.5)

# 4) LLM final decision summary
ax = axes[1, 1]
ax.axis("off")
txt = "FINAL OPTIMIZATION DECISION\n\n"
txt += "VLM (scene analysis):\n"
txt += "  ADOPTED: role_constraints\n"
txt += "    rubric 8/12 (= default best) | latency 7.5s (44% faster)\n"
txt += "    -> combination (role+constraints) beats single variants\n\n"
txt += "  REJECTED: fewshot family (2-3/12, worst + slowest)\n"
txt += "    -> fewshot causes bias to examples, hurts this domain\n\n"
txt += "  PENDING: safety_first (429 quota, next session)\n\n"
txt += "LLM (safety report):\n"
txt += "  ADOPTED: default (safety-first -> conservative sev=HIGH)\n"
txt += "    rubric 9/12 | 2 violations | 2 OSHA citations\n"
txt += "  ALT: severity_first (9/12, 4 actions, sev=MEDIUM)\n\n"
txt += "Trigger line: 0.60/0.30 + violation classes always trigger\n"
txt += "Model: Gemini 2.5 Flash (2.5 Pro = paid only)\n"
txt += "Principle: SAFETY-FIRST (false negative forbidden)"
ax.text(0.02, 0.98, txt, transform=ax.transAxes, fontsize=10.5, verticalalignment="top",
        family="monospace",
        bbox=dict(boxstyle="round", facecolor="#f8f9fa", edgecolor="#34495e", alpha=0.9))

plt.tight_layout(rect=[0, 0, 1, 0.98])
plt.savefig(OUT_IMG, dpi=150)
print(f"Saved: {OUT_IMG}")
plt.close()
