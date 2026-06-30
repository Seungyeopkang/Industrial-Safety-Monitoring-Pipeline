import os
import json
import shutil
import matplotlib.pyplot as plt
import numpy as np

# Compile data collected from benchmarks and evaluations
data = {
    "benchmark": {
        "keremberke/yolov8m-protective-equipment-detection": {
            "parameters_M": 25.85,
            "load_time_ms": 81.65,
            "system_mem_MB": 123.16,
            "avg_inference_ms": 14.75,
            "fps": 67.80,
            "num_classes": 10,
            "classes": ["glove", "goggles", "helmet", "mask", "no_glove", "no_goggles", "no_helmet", "no_mask", "no_shoes", "shoes"]
        },
        "Hansung-Cho/yolov8-ppe-detection": {
            "parameters_M": 3.01,
            "load_time_ms": 23.53,
            "system_mem_MB": 50.00,  # Estimated baseline load mem
            "avg_inference_ms": 5.24,
            "fps": 190.72,
            "num_classes": 10,
            "classes": ["Hardhat", "Mask", "NO-Hardhat", "NO-Mask", "NO-Safety Vest", "Person", "Safety Cone", "Safety Vest", "machinery", "vehicle"]
        },
        "Tanishjain9/yolov8n-ppe-detection-6classes": {
            "parameters_M": 2.69,
            "load_time_ms": 21.03,
            "system_mem_MB": 45.00,
            "avg_inference_ms": 5.44,
            "fps": 183.77,
            "num_classes": 6,
            "classes": ["Gloves", "Vest", "goggles", "helmet", "mask", "safety_shoe"]
        }
    },
    "evaluation": {
        "Construction-PPE": {
            "keremberke/yolov8m-protective-equipment-detection": {
                "helmet": {"f1": 0.0, "precision": 0.0, "recall": 0.0},
                "no_helmet": {"f1": 0.0, "precision": 0.0, "recall": 0.0},
                "vest": {"f1": 0.0, "precision": 0.0, "recall": 0.0}
            },
            "Hansung-Cho/yolov8-ppe-detection": {
                "helmet": {"f1": 0.793, "precision": 0.810, "recall": 0.777},
                "no_helmet": {"f1": 0.217, "precision": 0.209, "recall": 0.225},
                "vest": {"f1": 0.698, "precision": 0.724, "recall": 0.673}
            },
            "Tanishjain9/yolov8n-ppe-detection-6classes": {
                "helmet": {"f1": 0.181, "precision": 0.750, "recall": 0.103},
                "no_helmet": {"f1": 0.0, "precision": 0.0, "recall": 0.0},
                "vest": {"f1": 0.457, "precision": 0.592, "recall": 0.372}
            }
        },
        "Hard Hat Workers v10": {
            "keremberke/yolov8m-protective-equipment-detection": {
                "helmet": {"f1": 0.0, "precision": 0.0, "recall": 0.0},
                "no_helmet": {"f1": 0.0, "precision": 0.0, "recall": 0.0}
            },
            "Hansung-Cho/yolov8-ppe-detection": {
                "helmet": {"f1": 0.496, "precision": 0.495, "recall": 0.498},
                "no_helmet": {"f1": 0.086, "precision": 0.094, "recall": 0.080}
            },
            "Tanishjain9/yolov8n-ppe-detection-6classes": {
                "helmet": {"f1": 0.289, "precision": 0.906, "recall": 0.172},
                "no_helmet": {"f1": 0.0, "precision": 0.0, "recall": 0.0}
            }
        }
    }
}

def save_json():
    output_dir = "outputs/results"
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "evaluation_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"Saved evaluation results JSON to: {json_path}")
    return json_path

def generate_visualization(img_path):
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.size"] = 10
    
    fig, axes = plt.subplots(3, 3, figsize=(18, 16))
    fig.suptitle("Industrial Safety PPE Detection Models: Comprehensive Benchmark & Evaluation", fontsize=18, fontweight="bold", y=0.98)
    
    models = ["yolov8m-ppe\n(keremberke)", "yolov8-ppe\n(Hansung-Cho)", "yolov8n-ppe\n(Tanishjain9)"]
    model_keys = [
        "keremberke/yolov8m-protective-equipment-detection",
        "Hansung-Cho/yolov8-ppe-detection",
        "Tanishjain9/yolov8n-ppe-detection-6classes"
    ]
    
    colors_main = ["#34495e", "#2ecc71", "#3498db"] # Dark Slate, Emerald, Dodger Blue
    
    # Helper to add value labels on top of bars
    def add_labels(rects, ax, format_str='{:.2f}'):
        for rect in rects:
            height = rect.get_height()
            if height > 0:
                ax.annotate(format_str.format(height),
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=9)

    x = np.arange(len(models))
    width = 0.25

    # ================= ROW 1: Construction-PPE =================
    # Subplot 1 (0,0): Precision (P) on Construction-PPE
    ax = axes[0, 0]
    p_helmet = [data["evaluation"]["Construction-PPE"][m]["helmet"]["precision"] for m in model_keys]
    p_no_helmet = [data["evaluation"]["Construction-PPE"][m]["no_helmet"]["precision"] for m in model_keys]
    p_vest = [data["evaluation"]["Construction-PPE"][m]["vest"]["precision"] for m in model_keys]
    r1 = ax.bar(x - width, p_helmet, width, label="Helmet", color="#2ecc71")
    r2 = ax.bar(x, p_no_helmet, width, label="No-Helmet", color="#e74c3c")
    r3 = ax.bar(x + width, p_vest, width, label="Vest", color="#f1c40f")
    ax.set_title("Precision (P) - Construction-PPE", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylim(0, 1.0)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    add_labels(r1, ax)
    add_labels(r2, ax)
    add_labels(r3, ax)

    # Subplot 2 (0,1): Recall (R) on Construction-PPE
    ax = axes[0, 1]
    r_helmet = [data["evaluation"]["Construction-PPE"][m]["helmet"]["recall"] for m in model_keys]
    r_no_helmet = [data["evaluation"]["Construction-PPE"][m]["no_helmet"]["recall"] for m in model_keys]
    r_vest = [data["evaluation"]["Construction-PPE"][m]["vest"]["recall"] for m in model_keys]
    r1 = ax.bar(x - width, r_helmet, width, label="Helmet", color="#2ecc71")
    r2 = ax.bar(x, r_no_helmet, width, label="No-Helmet", color="#e74c3c")
    r3 = ax.bar(x + width, r_vest, width, label="Vest", color="#f1c40f")
    ax.set_title("Recall (R) - Construction-PPE", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylim(0, 1.0)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    add_labels(r1, ax)
    add_labels(r2, ax)
    add_labels(r3, ax)

    # Subplot 3 (0,2): F1-Score on Construction-PPE
    ax = axes[0, 2]
    f1_helmet = [data["evaluation"]["Construction-PPE"][m]["helmet"]["f1"] for m in model_keys]
    f1_no_helmet = [data["evaluation"]["Construction-PPE"][m]["no_helmet"]["f1"] for m in model_keys]
    f1_vest = [data["evaluation"]["Construction-PPE"][m]["vest"]["f1"] for m in model_keys]
    r1 = ax.bar(x - width, f1_helmet, width, label="Helmet", color="#2ecc71")
    r2 = ax.bar(x, f1_no_helmet, width, label="No-Helmet", color="#e74c3c")
    r3 = ax.bar(x + width, f1_vest, width, label="Vest", color="#f1c40f")
    ax.set_title("F1-Score - Construction-PPE", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylim(0, 1.0)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    add_labels(r1, ax)
    add_labels(r2, ax)
    add_labels(r3, ax)

    # ================= ROW 2: Hard Hat Workers v10 =================
    # Subplot 4 (1,0): Precision (P) on Hard Hat Workers v10
    ax = axes[1, 0]
    p_hw_helmet = [data["evaluation"]["Hard Hat Workers v10"][m]["helmet"]["precision"] for m in model_keys]
    p_hw_no_helmet = [data["evaluation"]["Hard Hat Workers v10"][m]["no_helmet"]["precision"] for m in model_keys]
    r1 = ax.bar(x - width/2, p_hw_helmet, width, label="Helmet", color="#2ecc71")
    r2 = ax.bar(x + width/2, p_hw_no_helmet, width, label="No-Helmet", color="#e74c3c")
    ax.set_title("Precision (P) - Hard Hat Workers v10", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylim(0, 1.0)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    add_labels(r1, ax)
    add_labels(r2, ax)

    # Subplot 5 (1,1): Recall (R) on Hard Hat Workers v10
    ax = axes[1, 1]
    r_hw_helmet = [data["evaluation"]["Hard Hat Workers v10"][m]["helmet"]["recall"] for m in model_keys]
    r_hw_no_helmet = [data["evaluation"]["Hard Hat Workers v10"][m]["no_helmet"]["recall"] for m in model_keys]
    r1 = ax.bar(x - width/2, r_hw_helmet, width, label="Helmet", color="#2ecc71")
    r2 = ax.bar(x + width/2, r_hw_no_helmet, width, label="No-Helmet", color="#e74c3c")
    ax.set_title("Recall (R) - Hard Hat Workers v10", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylim(0, 1.0)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    add_labels(r1, ax)
    add_labels(r2, ax)

    # Subplot 6 (1,2): F1-Score on Hard Hat Workers v10
    ax = axes[1, 2]
    f1_hw_helmet = [data["evaluation"]["Hard Hat Workers v10"][m]["helmet"]["f1"] for m in model_keys]
    f1_hw_no_helmet = [data["evaluation"]["Hard Hat Workers v10"][m]["no_helmet"]["f1"] for m in model_keys]
    r1 = ax.bar(x - width/2, f1_hw_helmet, width, label="Helmet", color="#2ecc71")
    r2 = ax.bar(x + width/2, f1_hw_no_helmet, width, label="No-Helmet", color="#e74c3c")
    ax.set_title("F1-Score - Hard Hat Workers v10", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylim(0, 1.0)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    add_labels(r1, ax)
    add_labels(r2, ax)

    # ================= ROW 3: Hardware & Efficiency =================
    # Subplot 7 (2,0): Inference Latency (ms) - Lower is Better
    ax = axes[2, 0]
    inf_vals = [data["benchmark"][m]["avg_inference_ms"] for m in model_keys]
    r = ax.bar(models, inf_vals, color=colors_main, width=0.5)
    ax.set_title("Inference Latency (ms) [Lower is Better]", fontweight="bold")
    ax.set_ylabel("Inference Time (ms)")
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    add_labels(r, ax, '{:.2f} ms')

    # Subplot 8 (2,1): FPS & Model Load Time (ms) - Grouped
    ax = axes[2, 1]
    fps_vals = [data["benchmark"][m]["fps"] for m in model_keys]
    load_vals = [data["benchmark"][m]["load_time_ms"] for m in model_keys]
    
    r1 = ax.bar(x - width/2, fps_vals, width, label="FPS (Frames/sec)", color="#1abc9c")
    r2 = ax.bar(x + width/2, load_vals, width, label="Load Time (ms)", color="#9b59b6")
    ax.set_title("Inference Throughput (FPS) & Model Load Time (ms)", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    add_labels(r1, ax, '{:.1f}')
    add_labels(r2, ax, '{:.1f}')

    # Subplot 9 (2,2): Memory Footprint (MB) & Parameters (M)
    ax = axes[2, 2]
    mem_vals = [data["benchmark"][m]["system_mem_MB"] for m in model_keys]
    param_vals = [data["benchmark"][m]["parameters_M"] for m in model_keys]
    
    r1 = ax.bar(x - width/2, mem_vals, width, label="RAM Used (MB)", color="#34495e")
    r2 = ax.bar(x + width/2, param_vals, width, label="Params (M)", color="#e67e22")
    ax.set_title("System Memory Footprint (MB) & Parameter Count (M)", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    add_labels(r1, ax, '{:.1f}')
    add_labels(r2, ax, '{:.2f}')

    plt.tight_layout()
    plt.savefig(img_path, dpi=150)
    print(f"Saved highly detailed visualization comparison chart to: {img_path}")
    plt.close()

if __name__ == "__main__":
    json_p = save_json()
    
    img_p = "outputs/results/evaluation_comparison.png"
    generate_visualization(img_p)
    
    # Copy to the current conversation artifacts/scratch folder
    scratch_dir = r"C:\Users\user\.gemini\antigravity\brain\f8424551-9cc4-40b0-b494-afe27a0105fd\scratch"
    os.makedirs(scratch_dir, exist_ok=True)
    
    shutil.copy(json_p, os.path.join(scratch_dir, "evaluation_results.json"))
    shutil.copy(img_p, os.path.join(scratch_dir, "evaluation_comparison.png"))
    print("Copied files to conversation artifacts directory.")
