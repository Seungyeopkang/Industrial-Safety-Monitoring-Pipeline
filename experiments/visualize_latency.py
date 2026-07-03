"""Visualize pipeline latency comparison: YOLO-only vs full pipeline."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
LAT = ROOT / "outputs" / "results" / "pipeline_latency_comparison.json"
TRIG = ROOT / "outputs" / "results" / "trigger_threshold_experiment.json"
OUT_IMG = ROOT / "outputs" / "results" / "pipeline_latency_comparison.png"

d = json.loads(LAT.read_text(encoding="utf-8"))
a = d["averages"]
t = json.loads(TRIG.read_text(encoding="utf-8"))

fig, axes = plt.subplots(1, 3, figsize=(18, 6))
fig.suptitle("Pipeline Latency: YOLO-only vs YOLO+VLM+LLM (Gemini 2.5 Flash)",
             fontsize=14, fontweight="bold", y=1.02)

# 1) Stacked bar: YOLO vs VLM vs LLM
ax = axes[0]
stages = ["YOLO only", "Full pipeline\n(YOLO+VLM+LLM)"]
yolo = [a["yolo_ms"]/1000, a["yolo_ms"]/1000]
vlm = [0, a["vlm_ms"]/1000]
llm = [0, a["llm_ms"]/1000]
x = np.arange(len(stages))
ax.bar(x, yolo, 0.5, label="YOLO (local)", color="#2ecc71")
ax.bar(x, vlm, 0.5, bottom=yolo, label="VLM (cloud)", color="#3498db")
ax.bar(x, llm, 0.5, bottom=[y+v for y,v in zip(yolo, vlm)], label="LLM (cloud)", color="#e67e22")
ax.set_title("Latency Breakdown", fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(stages)
ax.set_ylabel("Latency (s)")
ax.legend(fontsize=9)
for i, total in enumerate([a["yolo_ms"]/1000, a["full_pipeline_ms"]/1000]):
    ax.text(i, total + 0.5, f"{total:.1f}s", ha="center", fontweight="bold")
ax.grid(axis="y", linestyle="--", alpha=0.5)

# 2) Pie: share of full pipeline
ax = axes[1]
sizes = [a["yolo_ms"], a["vlm_ms"], a["llm_ms"]]
labels = [f"YOLO\n{a['yolo_ms']:.0f}ms ({a['yolo_share']*100:.0f}%)",
          f"VLM\n{a['vlm_ms']:.0f}ms ({a['vlm_ms']/a['full_pipeline_ms']*100:.0f}%)",
          f"LLM\n{a['llm_ms']:.0f}ms ({a['llm_ms']/a['full_pipeline_ms']*100:.0f}%)"]
colors = ["#2ecc71", "#3498db", "#e67e22"]
ax.pie(sizes, labels=labels, colors=colors, autopct="", startangle=90)
ax.set_title("Full Pipeline Time Share\n(Total: {:.1f}s)".format(a["full_pipeline_ms"]/1000), fontweight="bold")

# 3) Cost-benefit: trigger rate vs overhead saved
ax = axes[2]
trigger_rate = t["recommended"]["trigger_rate"]
overhead_s = a["vlm_llm_overhead_ms"] / 1000
# If trigger fires, full overhead paid. If not, only YOLO.
avg_with_trigger = a["yolo_ms"]/1000 + trigger_rate * overhead_s
avg_without = a["yolo_ms"]/1000 + overhead_s  # always run VLM/LLM
bars = ax.bar(["Always run\nVLM+LLM", "Hybrid trigger\n(0.60/0.30)", "YOLO only\n(no VLM)"],
              [avg_without, avg_with_trigger, a["yolo_ms"]/1000],
              color=["#e74c3c", "#f39c12", "#2ecc71"], width=0.55)
ax.set_title("Average Latency per Image\n(trigger rate {:.0%})".format(trigger_rate), fontweight="bold")
ax.set_ylabel("Avg Latency (s)")
for b, v in zip(bars, [avg_without, avg_with_trigger, a["yolo_ms"]/1000]):
    ax.text(b.get_x() + b.get_width()/2, v + 0.3, f"{v:.1f}s", ha="center", fontweight="bold")
ax.grid(axis="y", linestyle="--", alpha=0.5)

plt.tight_layout()
plt.savefig(OUT_IMG, dpi=150, bbox_inches="tight")
print(f"Saved: {OUT_IMG}")
plt.close()
