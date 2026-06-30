import os
import time
import numpy as np
import psutil
import torch
from huggingface_hub import hf_hub_download
from ultralytics import YOLO

# Candidate models list
MODELS = {
    "keremberke/yolov8m-protective-equipment-detection": {
        "repo": "keremberke/yolov8m-protective-equipment-detection",
        "local_name": "yolov8m_ppe.pt"
    },
    "Hansung-Cho/yolov8-ppe-detection": {
        "repo": "Hansung-Cho/yolov8-ppe-detection",
        "local_name": "yolov8_hansung.pt"
    },
    "Tanishjain9/yolov8n-ppe-detection-6classes": {
        "repo": "Tanishjain9/yolov8n-ppe-detection-6classes",
        "local_name": "yolov8n_tanish.pt"
    }
}

def get_memory_usage():
    """Returns the current RSS memory usage of the process in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def download_models(weights_dir):
    os.makedirs(weights_dir, exist_ok=True)
    downloaded_paths = {}
    for name, cfg in MODELS.items():
        target_path = os.path.join(weights_dir, cfg["local_name"])
        if not os.path.exists(target_path):
            print(f"Downloading {name} best.pt from HF Hub...")
            try:
                path = hf_hub_download(repo_id=cfg["repo"], filename="best.pt")
                import shutil
                shutil.copy(path, target_path)
                print(f"Saved to {target_path}")
            except Exception as e:
                print(f"Error downloading {name}: {e}")
        downloaded_paths[name] = target_path
    return downloaded_paths

def benchmark_model(model_name, model_path):
    print(f"\n==========================================")
    print(f"Benchmarking Model: {model_name}")
    print(f"==========================================")
    
    # Measure memory before loading
    mem_before = get_memory_usage()
    
    # Load Model
    start_load = time.time()
    model = YOLO(model_path)
    load_time = (time.time() - start_load) * 1000
    
    # Measure memory after loading
    mem_after = get_memory_usage()
    model_mem = mem_after - mem_before
    
    # Get model info
    num_classes = len(model.names)
    class_list = list(model.names.values())
    
    # Input size from model config or defaults
    input_size = model.overrides.get("imgsz", 640)
    
    # CUDA details
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Running on device: {device.upper()}")
    
    # Warmup
    dummy_img = np.random.randint(0, 255, (input_size, input_size, 3), dtype=np.uint8)
    for _ in range(5):
        _ = model(dummy_img, verbose=False, device=device)
        
    # Benchmark speed (50 runs)
    runs = 50
    inference_times = []
    
    # GPU memory measurement if CUDA
    gpu_mem_used = 0.0
    if device == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        mem_gpu_before = torch.cuda.memory_allocated() / (1024 * 1024)
        
    for _ in range(runs):
        t0 = time.time()
        _ = model(dummy_img, verbose=False, device=device)
        t1 = time.time()
        inference_times.append((t1 - t0) * 1000)
        
    mean_inf_time = np.mean(inference_times)
    fps = 1000.0 / mean_inf_time
    
    if device == "cuda":
        mem_gpu_after = torch.cuda.memory_allocated() / (1024 * 1024)
        gpu_mem_used = mem_gpu_after - mem_gpu_before
        
    # Get model parameters info
    params = 0
    try:
        # access underlying torch model params
        params = sum(p.numel() for p in model.model.parameters()) / 1e6 # in Millions
    except Exception:
        pass
        
    print(f"  - Parameters: {params:.2f} M" if params > 0 else "  - Parameters: N/A")
    print(f"  - Load Time: {load_time:.2f} ms")
    print(f"  - System Memory Footprint: {model_mem:.2f} MB")
    if device == "cuda":
        print(f"  - GPU Memory Used: {gpu_mem_used:.2f} MB")
    print(f"  - Default Input Size: {input_size}x{input_size}")
    print(f"  - Average Inference Time: {mean_inf_time:.2f} ms")
    print(f"  - FPS: {fps:.2f}")
    print(f"  - Number of Classes: {num_classes}")
    print(f"  - Classes: {class_list}")
    
    return {
        "model": model_name,
        "params_M": round(params, 2) if params > 0 else "N/A",
        "load_time_ms": round(load_time, 2),
        "sys_mem_MB": round(model_mem, 2),
        "gpu_mem_MB": round(gpu_mem_used, 2) if device == "cuda" else 0.0,
        "input_size": f"{input_size}x{input_size}",
        "avg_inf_ms": round(mean_inf_time, 2),
        "fps": round(fps, 2),
        "num_classes": num_classes,
        "classes": class_list
    }

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    weights_dir = os.path.join(current_dir, "weights")
    
    print("Step 1: Downloading model weights from Hugging Face...")
    paths = download_models(weights_dir)
    
    print("\nStep 2: Starting benchmark runs...")
    results = []
    for name, path in paths.items():
        if os.path.exists(path):
            results.append(benchmark_model(name, path))
            
    print("\n" + "="*80)
    print("BENCHMARK COMPARISON TABLE")
    print("="*80)
    print(f"{'Model Name':<50} | {'Input Size':<10} | {'Params (M)':<10} | {'Inf Time (ms)':<13} | {'FPS':<6} | {'Classes':<7}")
    print("-"*106)
    for r in results:
        print(f"{r['model']:<50} | {r['input_size']:<10} | {r['params_M']:<10} | {r['avg_inf_ms']:<13} | {r['fps']:<6} | {r['num_classes']:<7}")
    print("="*80)
