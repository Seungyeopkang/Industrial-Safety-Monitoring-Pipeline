"""Visualize prompt optimization + trigger threshold results - Sprint 2."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "outputs" / "results" / "prompt_optimization_results.json"
TRIGGER = ROOT / "outputs" / "results" / "trigger_threshold_experiment.json"
OUT_IMG = ROOT / "outputs" / "results" / "prompt_optimization_chart.png"

d = json.loads(RESULTS.read_text(encoding="utf-8"))
t = json.loads(TRIGGER.read_text(encoding="utf-8"))
vlm = sorted(d.get("vlm", []), key=lambda x: -x["rubric"]["total"])
llm = sorted(d.get("llm", []), key=lambda x: -x["rubric"]["total"])

fig, axes = plt.subplots(2, 3, figsize=(20, 11))
fig.suptitle("Sprint 2 - Prompt Optimization & VLM Trigger Threshold (Gemini 2.5 Flash)",
             fontsize=15, fontweight="bold", y=0.995)
colors = ["#2ecc71", "#27ae60", "#3498db", "#e67e22", "#e74c3c", "#9b59b6", "#1abc9c"]

ax = axes[0, 0]
names = [v["variant"] for v in vlm]; scores = [v["rubric"]["total"] for v in vlm]
bars = ax.barh(names, scores, color=colors[:len(names)])
ax.set_title("VLM Rubric by Prompt Variant (right=better)", fontweight="bold")
ax.set_xlabel("Rubric Total (max 12)"); ax.set_xlim(0, 12)
for b, s in zip(bars, scores):
    ax.text(s + 0.15, b.get_y() + b.get_height()/2, str(s) + "/12", va="center", fontweight="bold")
ax.grid(axis="x", linestyle="--", alpha=0.5)

ax = axes[0, 1]
for i, v in enumerate(vlm):
    ax.scatter(v["latency_ms"]/1000, v["rubric"]["total"], s=160, color=colors[i], zorder=3)
    ax.annotate(v["variant"], (v["latency_ms"]/1000, v["rubric"]["total"]), xytext=(7, 7), textcoords="offset points", fontsize=8)
ax.set_title("VLM Latency vs Quality (lower-right=better)", fontweight="bold")
ax.set_xlabel("Latency (s)"); ax.set_ylabel("Rubric (max 12)"); ax.set_ylim(0, 12)
ax.grid(linestyle="--", alpha=0.5); ax.axhspan(7.5, 8.5, color="#2ecc71", alpha=0.08)

ax = axes[0, 2]
names = [v["variant"] for v in llm]; x = np.arange(len(names)); w = 0.2
viol = [len(v["parsed"]["violations"]) for v in llm]; act = [len(v["parsed"]["recommended_actions"]) for v in llm]
cite = [len(v["parsed"]["citations"]) for v in llm]; rub = [v["rubric"]["total"] for v in llm]
ax.bar(x - 1.5*w, rub, w, label="Rubric/12", color="#2ecc71")
ax.bar(x - 0.5*w, viol, w, label="Violations", color="#e74c3c")
ax.bar(x + 0.5*w, act, w, label="Actions", color="#3498db")
ax.bar(x + 1.5*w, cite, w, label="Citations", color="#e67e22")
ax.set_title("LLM Report Quality by Variant", fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(names, rotation=15)
ax.legend(fontsize=8); ax.grid(axis="y", linestyle="--", alpha=0.5)

ax = axes[1, 0]
cs = t["confidence_stats"]
vals = [cs["min"], cs["median"], cs["mean"], cs["max"]]
ax.barh(["min", "median", "mean", "max"], vals, color=["#e74c3c", "#f39c12", "#3498db", "#2ecc71"])
ax.set_title("Detection Confidence (10 imgs, 68 dets)", fontweight="bold")
ax.set_xlabel("Confidence"); ax.set_xlim(0, 1)
for i, val in enumerate(vals):
    ax.text(val + 0.02, i, f"{val:.3f}", va="center", fontweight="bold")
ax.grid(axis="x", linestyle="--", alpha=0.5)

ax = axes[1, 1]
lines = t["lines"]; labels = [f"h={l['high']}\nl={l['low']}" for l in lines]
trig = [l["trigger_rate"]*100 for l in lines]
rec_idx = next((i for i, l in enumerate(lines) if l == t.get("recommended")), None)
bar_colors = ["#e74c3c" if i == rec_idx else "#3498db" for i in range(len(lines))]
bars = ax.bar(labels, trig, color=bar_colors)
ax.set_title("VLM Trigger Rate by Threshold Line (red=recommended)", fontweight="bold")
ax.set_ylabel("Trigger Rate (%)"); ax.set_ylim(0, 60)
for b, tr in zip(bars, trig):
    ax.text(b.get_x() + b.get_width()/2, tr + 1, f"{tr:.1f}%", ha="center", fontweight="bold")
ax.grid(axis="y", linestyle="--", alpha=0.5)

ax = axes[1, 2]
cd = t["class_distribution"]; items = sorted(cd.items(), key=lambda x: -x[1])
cls_names = [k for k, _ in items]; counts = [v for _, v in items]
cls_colors = ["#e74c3c" if k.startswith("NO-") else "#2ecc71" for k in cls_names]
bars = ax.barh(cls_names, counts, color=cls_colors)
ax.set_title("Class Distribution (red=violation, always-trigger)", fontweight="bold")
ax.set_xlabel("Count")
for b, c in zip(bars, counts):
    ax.text(c + 0.3, b.get_y() + b.get_height()/2, str(c), va="center")
ax.grid(axis="x", linestyle="--", alpha=0.5)

plt.tight_layout(rect=[0, 0, 1, 0.98])
plt.savefig(OUT_IMG, dpi=150)
print(f"Saved: {OUT_IMG}")
plt.close()
