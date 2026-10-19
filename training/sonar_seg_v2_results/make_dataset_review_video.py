#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""随机抽取整个 YOLO 数据集的图片，用分割权重推理并拼成分段视频。

默认遍历 train/valid/test 的所有 images。每张图片只进入一个视频帧；
按模型置信度最高的类别分组，每个连续类别段最多 20 帧，段间切换类别。
"""

from __future__ import annotations

import argparse
import json
import random
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


RESULTS_DIR = Path(__file__).resolve().parent


def find_default_dataset() -> Path:
    """Locate the published dataset both in the workspace and after repo cloning."""
    for base in (RESULTS_DIR, *RESULTS_DIR.parents):
        candidates = (
            base / "datasets" / "sonar_database-yolov8",
            base / "dave-sonar-wreck-detection" / "datasets" / "sonar_database-yolov8",
        )
        for candidate in candidates:
            if candidate.is_dir():
                return candidate
    return RESULTS_DIR.parent / "dave-sonar-wreck-detection" / "datasets" / "sonar_database-yolov8"


DEFAULT_DATASET = find_default_dataset()
DEFAULT_WEIGHTS = RESULTS_DIR / "best.pt"
DEFAULT_VIDEO = RESULTS_DIR / "sonar_seg_v2_dataset_review.mp4"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def collect_images(dataset: Path) -> list[Path]:
    """收集各 split/images 下的图像，不读取标签来决定模型分类。"""
    roots = [dataset / split / "images" for split in ("train", "valid", "test")]
    images = sorted(
        path
        for root in roots
        if root.is_dir()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not images:
        raise FileNotFoundError(f"在 {dataset} 的 train/valid/test images 目录中没有找到图片")
    return images


def predicted_group(result, names: dict[int, str]) -> str:
    """用该图置信度最高的预测类别作为分组；无检测图像归为背景/未检出。"""
    if result.boxes is None or len(result.boxes) == 0:
        return "background_no_detection"
    classes = result.boxes.cls.cpu().tolist()
    confidences = result.boxes.conf.cpu().tolist()
    best_index = max(range(len(confidences)), key=confidences.__getitem__)
    return names.get(int(classes[best_index]), f"class_{int(classes[best_index])}")


def make_block_order(
    buckets: dict[str, list[Path]], max_per_block: int, rng: random.Random
) -> list[tuple[str, list[Path]]]:
    """每类内部随机打乱，再抽取不超过 max_per_block 帧的类别段。"""
    remaining = {name: list(paths) for name, paths in buckets.items() if paths}
    for paths in remaining.values():
        rng.shuffle(paths)

    blocks: list[tuple[str, list[Path]]] = []
    previous = None
    while remaining:
        choices = [name for name, paths in remaining.items() if paths and name != previous]
        if not choices:  # 仅剩一个类别时，避免陷入死循环
            choices = [name for name, paths in remaining.items() if paths]
        name = rng.choice(choices)
        paths = remaining[name]
        block = paths[:max_per_block]
        del paths[: len(block)]
        blocks.append((name, block))
        previous = name
        if not paths:
            del remaining[name]
    return blocks


def render_frame(image, category: str, frame_number: int, total: int, fps: float):
    """生成统一大小的视频帧，顶部显示模型分组，底部显示进度。"""
    height, width = 720, 1024
    header_h, footer_h = 58, 46
    canvas = image.copy()
    ih, iw = canvas.shape[:2]
    max_w, max_h = width - 32, height - header_h - footer_h - 16
    scale = min(max_w / iw, max_h / ih)
    resized = cv2.resize(canvas, (round(iw * scale), round(ih * scale)), interpolation=cv2.INTER_AREA)

    frame = 24 * np.ones((height, width, 3), dtype=np.uint8)
    frame[:header_h] = (35, 35, 35)
    frame[height - footer_h :] = (35, 35, 35)
    x = (width - resized.shape[1]) // 2
    y = header_h + (height - header_h - footer_h - resized.shape[0]) // 2
    frame[y : y + resized.shape[0], x : x + resized.shape[1]] = resized

    title = {
        "background_no_detection": "BACKGROUND / NO DETECTION",
        "box_crate": "BOX / CRATE",
        "pipe": "PIPE",
        "shipwreck": "SHIPWRECK",
    }.get(category, category.upper())
    cv2.putText(frame, f"Model group: {title}", (18, 39), cv2.FONT_HERSHEY_SIMPLEX, 0.88, (90, 235, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, f"Frame {frame_number}/{total}   |   {fps:g} FPS", (18, height - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1, cv2.LINE_AA)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="数据集根目录")
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS, help="新训练的 best.pt")
    parser.add_argument("--output", type=Path, default=DEFAULT_VIDEO, help="输出 MP4 路径")
    parser.add_argument("--conf", type=float, default=0.25, help="检测置信度阈值")
    parser.add_argument("--imgsz", type=int, default=512, help="模型推理尺寸")
    parser.add_argument("--batch", type=int, default=4, help="推理批量；内存紧张时可设为 1")
    parser.add_argument("--device", default="cpu", help="推理设备；默认 CPU，避免占用仿真/训练显存")
    parser.add_argument("--fps", type=float, default=8.0, help="视频帧率")
    parser.add_argument("--max-per-class", type=int, default=20, help="同一类别连续显示的最大帧数")
    parser.add_argument("--seed", type=int, default=20261020, help="随机种子，便于复现顺序")
    args = parser.parse_args()

    if not args.weights.is_file():
        raise FileNotFoundError(f"找不到权重文件：{args.weights}")
    if args.fps <= 0 or args.max_per_class < 1:
        raise ValueError("--fps 必须大于 0，--max-per-class 必须至少为 1")

    images = collect_images(args.dataset)
    print(f"[数据集] 找到 {len(images)} 张图片：{args.dataset}", flush=True)
    print(f"[模型] 加载权重：{args.weights}", flush=True)
    model = YOLO(str(args.weights))
    names = {int(index): str(name) for index, name in model.names.items()}
    print(f"[类别] {names}", flush=True)

    buckets: dict[str, list[Path]] = defaultdict(list)
    # 只在系统临时目录缓存分割可视化，避免将中间帧混入数据集或结果文件夹。
    with tempfile.TemporaryDirectory(prefix="sonar_seg_v2_frames_") as temp_dir:
        temp_path = Path(temp_dir)
        annotated: dict[Path, Path] = {}
        stream = model.predict(
            source=[str(path) for path in images],
            stream=True,
            batch=args.batch,
            imgsz=args.imgsz,
            conf=args.conf,
            device=args.device,
            verbose=False,
        )
        for index, result in enumerate(stream, start=1):
            original_path = Path(result.path).resolve()
            category = predicted_group(result, names)
            buckets[category].append(original_path)
            marked = result.plot()
            cache_file = temp_path / f"{index:06d}.jpg"
            if not cv2.imwrite(str(cache_file), marked, [cv2.IMWRITE_JPEG_QUALITY, 92]):
                raise RuntimeError(f"无法写入临时图像：{cache_file}")
            annotated[original_path] = cache_file
            if index % 100 == 0 or index == len(images):
                print(f"[推理] {index}/{len(images)}", flush=True)

        rng = random.Random(args.seed)
        blocks = make_block_order(buckets, args.max_per_class, rng)
        ordered = [(category, path) for category, group in blocks for path in group]
        if len(ordered) != len(images):
            raise RuntimeError(f"帧数不匹配：计划 {len(ordered)}，源图像 {len(images)}")

        args.output.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (1024, 720)
        )
        if not writer.isOpened():
            raise RuntimeError(f"无法创建 MP4 视频：{args.output}（请检查 OpenCV MP4 编码支持）")
        try:
            for frame_number, (category, path) in enumerate(ordered, start=1):
                marked = cv2.imread(str(annotated[path]), cv2.IMREAD_COLOR)
                if marked is None:
                    raise RuntimeError(f"无法读取临时推理帧：{annotated[path]}")
                writer.write(render_frame(marked, category, frame_number, len(ordered), args.fps))
                if frame_number % 100 == 0 or frame_number == len(ordered):
                    print(f"[合成] {frame_number}/{len(ordered)}", flush=True)
        finally:
            writer.release()

    counts = {name: len(paths) for name, paths in sorted(buckets.items())}
    summary = {
        "video": str(args.output),
        "weights": str(args.weights),
        "dataset": str(args.dataset),
        "images_processed": len(images),
        "fps": args.fps,
        "max_consecutive_frames_per_category": args.max_per_class,
        "confidence_threshold": args.conf,
        "predicted_primary_category_counts": counts,
        "block_order": [{"category": name, "frames": len(group)} for name, group in blocks],
    }
    summary_path = args.output.with_suffix(".json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[完成] 视频：{args.output}", flush=True)
    print(f"[统计] 各图按最高置信度预测分组：{counts}", flush=True)
    print(f"[统计] 类别段数：{len(blocks)}；顺序记录：{summary_path}", flush=True)


if __name__ == "__main__":
    main()
