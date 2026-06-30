import os
import glob
import numpy as np
import cv2
import torch
from ultralytics import YOLO

# Mapped class mappings from each model's class list to target dataset standard classes.
# Standard classes we will evaluate:
# 0: helmet (or Hardhat)
# 1: no_helmet (or NO-Hardhat)
# 2: vest (or Safety Vest)

MODEL_MAPPINGS = {
    "keremberke/yolov8m-protective-equipment-detection": {
        "local_path": "detection/weights/yolov8m_ppe.pt",
        "map": {
            "helmet": 0,
            "no_helmet": 1,
            # we map gloves/goggles just in case but target is helmet/no_helmet/vest
        }
    },
    "Hansung-Cho/yolov8-ppe-detection": {
        "local_path": "detection/weights/yolov8_hansung.pt",
        "map": {
            "Hardhat": 0,
            "NO-Hardhat": 1,
            "Safety Vest": 2
        }
    },
    "Tanishjain9/yolov8n-ppe-detection-6classes": {
        "local_path": "detection/weights/yolov8n_tanish.pt",
        "map": {
            "helmet": 0,
            "Vest": 2
        }
    }
}

# Dataset standard class mappings (from dataset data.yaml classes to our standard classes)
# Construction-PPE classes:
# 0: helmet, 2: vest, 7: no_helmet
CONSTRUCTION_PPE_MAP = {
    0: 0,  # helmet -> helmet
    7: 1,  # no_helmet -> no_helmet
    2: 2   # vest -> vest
}

# Hard Hat Workers classes:
# 1: helmet, 0: head (treated as no_helmet for evaluation)
HARD_HAT_WORKERS_MAP = {
    1: 0,  # helmet -> helmet
    0: 1   # head -> no_helmet (head without helmet = no_helmet)
}

def calculate_iou(box1, box2):
    """Calculate IoU of two bounding boxes in [x1, y1, x2, y2] format."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection
    
    return intersection / union if union > 0 else 0

def load_yolo_labels(label_path, img_width, img_height, dataset_class_map):
    """Load and convert normalized YOLO labels to [class_id, x1, y1, x2, y2]."""
    labels = []
    if not os.path.exists(label_path):
        return labels
        
    with open(label_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            cls_id = int(parts[0])
            # Map dataset class to standard class
            if cls_id not in dataset_class_map:
                continue
            std_cls = dataset_class_map[cls_id]
            
            x_center = float(parts[1]) * img_width
            y_center = float(parts[2]) * img_height
            width = float(parts[3]) * img_width
            height = float(parts[4]) * img_height
            
            x1 = x_center - (width / 2.0)
            y1 = y_center - (height / 2.0)
            x2 = x_center + (width / 2.0)
            y2 = y_center + (height / 2.0)
            
            labels.append({
                "class_id": std_cls,
                "bbox": [x1, y1, x2, y2]
            })
    return labels

def evaluate_on_dataset(model_name, model_cfg, dataset_dir, dataset_class_map, iou_threshold=0.5, conf_threshold=0.25):
    """Evaluate a model on a dataset's test split using standard IoU matching."""
    model_path = model_cfg["local_path"]
    if not os.path.exists(model_path):
        print(f"Model path {model_path} not found.")
        return None
        
    model = YOLO(model_path)
    class_map = model_cfg["map"]
    
    # Determine split folder (images/test or test/images)
    test_img_dir = os.path.join(dataset_dir, "images", "test")
    test_label_dir = os.path.join(dataset_dir, "labels", "test")
    if not os.path.exists(test_img_dir):
        # Alternative structure (Hard Hat Workers: test/images)
        test_img_dir = os.path.join(dataset_dir, "test", "images")
        test_label_dir = os.path.join(dataset_dir, "test", "labels")
        
    if not os.path.exists(test_img_dir):
        print(f"Test image directory not found in {dataset_dir}")
        return None

    img_files = glob.glob(os.path.join(test_img_dir, "*.jpg")) + glob.glob(os.path.join(test_img_dir, "*.png"))
    
    # Global TP, FP, FN counts per standard class (0: helmet, 1: no_helmet, 2: vest)
    stats = {0: {"tp": 0, "fp": 0, "fn": 0}, 1: {"tp": 0, "fp": 0, "fn": 0}, 2: {"tp": 0, "fp": 0, "fn": 0}}
    
    # Run evaluation limit to max 50 images for speed if needed, but let's do all test set since test set is ~140 images
    for img_path in img_files:
        # Read image to get shape
        img = cv2.imread(img_path)
        if img is None:
            continue
        height, width, _ = img.shape
        
        # Load ground truth
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        label_path = os.path.join(test_label_dir, f"{base_name}.txt")
        gts = load_yolo_labels(label_path, width, height, dataset_class_map)
        
        # Run inference
        results = model(img_path, conf=conf_threshold, verbose=False)[0]
        preds = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            conf = float(box.conf[0])
            
            # Map model class to standard class
            if cls_name not in class_map:
                continue
            std_cls = class_map[cls_name]
            
            bbox = box.xyxy[0].tolist() # [x1, y1, x2, y2]
            preds.append({
                "class_id": std_cls,
                "bbox": bbox,
                "conf": conf
            })
            
        # Match predictions and ground truth per class
        for c in [0, 1, 2]:
            class_gts = [gt for gt in gts if gt["class_id"] == c]
            class_preds = sorted([pred for pred in preds if pred["class_id"] == c], key=lambda x: x["conf"], reverse=True)
            
            matched_gts = set()
            for pred in class_preds:
                best_iou = 0
                best_gt_idx = -1
                for idx, gt in enumerate(class_gts):
                    if idx in matched_gts:
                        continue
                    iou = calculate_iou(pred["bbox"], gt["bbox"])
                    if iou > best_iou:
                        best_iou = iou
                        best_gt_idx = idx
                        
                if best_iou >= iou_threshold:
                    stats[c]["tp"] += 1
                    matched_gts.add(best_gt_idx)
                else:
                    stats[c]["fp"] += 1
                    
            stats[c]["fn"] += (len(class_gts) - len(matched_gts))
            
    # Calculate Precision, Recall, F1 for each class and average
    results_summary = {}
    for c, c_name in [(0, "helmet"), (1, "no_helmet"), (2, "vest")]:
        tp = stats[c]["tp"]
        fp = stats[c]["fp"]
        fn = stats[c]["fn"]
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # If there are no ground truths and no predictions, F1 is N/A (e.g. model doesn't support vest)
        if tp == 0 and fp == 0 and fn == 0:
            results_summary[c_name] = {"precision": "N/A", "recall": "N/A", "f1": "N/A"}
        else:
            results_summary[c_name] = {
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1": round(f1, 3)
            }
            
    return results_summary

if __name__ == "__main__":
    datasets = {
        "Construction-PPE": {
            "dir": "datasets/construction-ppe",
            "map": CONSTRUCTION_PPE_MAP
        },
        "Hard Hat Workers v10": {
            "dir": "datasets/Hard Hat Workers.v10-raw_allclasses.yolov8",
            "map": HARD_HAT_WORKERS_MAP
        }
    }
    
    for d_name, d_cfg in datasets.items():
        print(f"\n==========================================")
        print(f"Evaluating Models on {d_name} Dataset (Test Split)")
        print(f"==========================================")
        for m_name, m_cfg in MODEL_MAPPINGS.items():
            print(f"Evaluating {m_name}...")
            res = evaluate_on_dataset(m_name, m_cfg, d_cfg["dir"], d_cfg["map"])
            if res:
                print(f"  Results:")
                for cls_name, metrics in res.items():
                    print(f"    - {cls_name:<10}: F1={metrics['f1']}, P={metrics['precision']}, R={metrics['recall']}")
