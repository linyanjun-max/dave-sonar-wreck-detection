# -*- coding: utf-8 -*-
"""Minimal inference example for sonar_seg_v2 best.pt."""
import sys

from ultralytics import YOLO

WEIGHTS = r"D:\dave\sonar_seg_v2_results\best.pt"


def main(image_path: str) -> None:
    model = YOLO(WEIGHTS)
    results = model(image_path, imgsz=512, conf=0.5, device=0)
    r = results[0]
    print(f"{len(r.boxes)} objects detected")
    for box, cls, conf in zip(r.boxes.xyxy, r.boxes.cls, r.boxes.conf):
        print(f"  {model.names[int(cls)]:12s} conf={float(conf):.3f} box={[round(v, 1) for v in box.tolist()]}")
    r.save("prediction.jpg")
    print("saved -> prediction.jpg")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"D:\sonar_database_v2\test\images")
