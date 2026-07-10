
'''detector.py - YOLO PPE Detection with OpenCV Bounding Box Visualization

Sprint 1 deliverable: OpenCV-based detection result visualization and verification script.
Uses the selected Hansung-Cho/yolov8-ppe-detection model (yolov8_hansung.pt).
Implements confidence-based VLM trigger rules (see vlm_trigger_rules.md).
'''
import os
import cv2
import json
from functools import lru_cache
from pathlib import Path
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEIGHTS_DIR = PROJECT_ROOT / 'detection' / 'weights'
DEFAULT_WEIGHT = WEIGHTS_DIR / 'yolov8_hansung.pt'

CLASS_COLORS = {
    'Hardhat': (0, 255, 0),
    'NO-Hardhat': (0, 0, 255),
    'Safety Vest': (0, 255, 255),
    'NO-Safety Vest': (0, 102, 255),
    'Mask': (255, 255, 0),
    'NO-Mask': (204, 0, 204),
    'Person': (128, 128, 128),
    'machinery': (255, 165, 0),
    'vehicle': (255, 165, 0),
    'Safety Cone': (200, 200, 0),
}
DEFAULT_COLOR = (255, 255, 255)

CONF_THRESHOLD = 0.25
# Thresholds empirically determined via experiments/trigger_threshold_experiment.py
# (10 images, 68 detections, confidence median 0.785). Safety-first: violation
# classes (NO-Hardhat/NO-Safety Vest/NO-Mask) ALWAYS trigger VLM regardless of
# confidence, because no_helmet F1 was 0.08-0.22 (unreliable alone).
# Line 0.60/0.30 triggers 27.9% of detections while keeping 100% of violations.
VLM_TRIGGER_HIGH = 0.60
VLM_TRIGGER_LOW = 0.30


def determine_vlm_trigger(detections):
    results = []
    for det in detections:
        conf = det['confidence']
        cls = det['class_name']
        if cls in ('NO-Hardhat', 'NO-Safety Vest', 'NO-Mask'):
            trigger = True
            reason = 'violation_class_low_f1'
        elif conf >= VLM_TRIGGER_HIGH:
            trigger = False
            reason = 'high_confidence_skip'
        elif conf >= VLM_TRIGGER_LOW:
            trigger = True
            reason = 'ambiguous_confidence_verify'
        else:
            trigger = False
            reason = 'low_confidence_noise'
        results.append({
            'class_name': cls,
            'confidence': round(conf, 3),
            'bbox': det['bbox'],
            'vlm_trigger': trigger,
            'trigger_reason': reason,
        })
    return results


def _overlap(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    return ix2 > ix1 and iy2 > iy1


def _build_summary(trigger_info):
    persons = [d for d in trigger_info if d['class_name'] == 'Person']
    workers = []
    for i, p in enumerate(persons, 1):
        helmet = any(d['class_name'] == 'Hardhat' and _overlap(p['bbox'], d['bbox']) for d in trigger_info)
        no_helmet = any(d['class_name'] == 'NO-Hardhat' and _overlap(p['bbox'], d['bbox']) for d in trigger_info)
        vest = any(d['class_name'] == 'Safety Vest' and _overlap(p['bbox'], d['bbox']) for d in trigger_info)
        no_vest = any(d['class_name'] == 'NO-Safety Vest' and _overlap(p['bbox'], d['bbox']) for d in trigger_info)
        h_status = 'Y' if helmet else ('N' if no_helmet else '?')
        v_status = 'Y' if vest else ('N' if no_vest else '?')
        workers.append('Worker ' + str(i) + ' (helmet: ' + h_status + ', vest: ' + v_status + ')')
    return workers


def draw_detections(image, detections):
    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        cls = det['class_name']
        conf = det['confidence']
        color = CLASS_COLORS.get(cls, DEFAULT_COLOR)
        cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        label = cls + ' ' + str(round(conf, 2))
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(image, (int(x1), int(y1) - th - 6), (int(x1) + tw + 4, int(y1)), color, -1)
        cv2.putText(image, label, (int(x1) + 2, int(y1) - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    return image


@lru_cache(maxsize=2)
def _load_cached_model(weight_path: str):
    """Keep one model instance per weight file for the lifetime of the process."""
    return YOLO(weight_path)


def load_model(weight_path=None):
    """Return a process-cached PPE detector; video and API jobs reuse it."""
    return _load_cached_model(str(Path(weight_path or DEFAULT_WEIGHT).resolve()))


def run_detection_frame(image, model):
    """Run detection on one already-decoded OpenCV frame."""
    results = model(image, conf=CONF_THRESHOLD, verbose=False)
    r = results[0]
    detections = []
    for box in r.boxes:
        cls_id = int(box.cls[0])
        cls_name = model.names[cls_id]
        conf = float(box.conf[0])
        bbox = box.xyxy[0].tolist()
        detections.append({'class_name': cls_name, 'confidence': conf, 'bbox': bbox})
    trigger_info = determine_vlm_trigger(detections)
    annotated = draw_detections(r.orig_img.copy(), detections)
    output = {
        'model': Path(getattr(model, 'ckpt_path', DEFAULT_WEIGHT)).name,
        'detections': trigger_info,
        'summary': _build_summary(trigger_info),
    }
    return output, annotated


def run_detection(image_path, weight_path=None, save_dir=None):
    model = load_model(weight_path)
    output, annotated = run_detection_frame(image_path, model)
    output['image_path'] = str(image_path)
    if save_dir: #단독 실행시만 됨. api로 호출시에는 다음 rag나 vlm에 전달하고, job status도 관리해야해서 따로 진행
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(image_path).stem
        cv2.imwrite(str(save_dir / (stem + '_detected.jpg')), annotated)
        (save_dir / (stem + '_result.json')).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    return output, annotated


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='YOLO PPE Detection with OpenCV visualization')
    parser.add_argument('image', help='Path to input image')
    parser.add_argument('--weight', default=str(DEFAULT_WEIGHT), help='Path to model weight')
    parser.add_argument('--save-dir', default='outputs/results/visualized', help='Directory to save outputs')
    args = parser.parse_args()
    output, annotated = run_detection(args.image, args.weight, args.save_dir)
    print(json.dumps(output, indent=2, ensure_ascii=False))
