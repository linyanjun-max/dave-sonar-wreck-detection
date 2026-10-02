#!/usr/bin/env python3
"""YOLOv8-seg inference for DAVE sonar images. This node never commands the ROV."""

import argparse
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
import torch
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, qos_profile_sensor_data
from sensor_msgs.msg import Image
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = ROOT / "models" / "shipwreck_seg_v1-5_best.pt"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument(
        "--topic",
        default="/model/bluerov2_heavy_multibeam_sonar/multibeam_sonar/sonar_image",
    )
    parser.add_argument("--output-topic", default="/dave_yolo/annotated")
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    parser.add_argument("--rate", type=float, default=2.0, help="Maximum inference rate in Hz")
    parser.add_argument("--imgsz", type=int, default=512)
    parser.add_argument("--conf", type=float, default=0.47)
    return parser.parse_args()


def image_to_bgr(msg):
    """Decode common DAVE sonar Image encodings without requiring cv_bridge."""
    enc = msg.encoding.lower()
    h, w, step = int(msg.height), int(msg.width), int(msg.step)
    raw = np.frombuffer(msg.data, dtype=np.uint8)
    if h <= 0 or w <= 0 or step <= 0 or raw.size < h * step:
        raise ValueError(f"invalid image dimensions/step: {w}x{h}, step={step}")
    rows = raw[: h * step].reshape(h, step)

    if enc in ("mono8", "8uc1"):
        gray = rows[:, :w].copy()
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if enc == "rgb8":
        rgb = np.ndarray((h, w, 3), np.uint8, buffer=msg.data, strides=(step, 3, 1))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    if enc == "bgr8":
        return np.ndarray((h, w, 3), np.uint8, buffer=msg.data, strides=(step, 3, 1)).copy()
    if enc in ("rgba8", "bgra8"):
        src = np.ndarray((h, w, 4), np.uint8, buffer=msg.data, strides=(step, 4, 1))
        code = cv2.COLOR_RGBA2BGR if enc == "rgba8" else cv2.COLOR_BGRA2BGR
        return cv2.cvtColor(src, code)
    if enc in ("mono16", "16uc1"):
        dtype = np.dtype(">u2" if msg.is_bigendian else "<u2")
        values = np.ndarray((h, w), dtype=dtype, buffer=msg.data, strides=(step, 2)).astype(np.float32)
        return gray_to_bgr(normalize_intensity(values))
    if enc == "32fc1":
        dtype = np.dtype(">f4" if msg.is_bigendian else "<f4")
        values = np.ndarray((h, w), dtype=dtype, buffer=msg.data, strides=(step, 4)).astype(np.float32)
        return gray_to_bgr(normalize_intensity(values))
    raise ValueError(f"unsupported sonar image encoding {msg.encoding!r}")


def normalize_intensity(values):
    valid = np.isfinite(values)
    if not valid.any():
        return np.zeros(values.shape, dtype=np.uint8)
    lo, hi = np.percentile(values[valid], (1, 99))
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((np.nan_to_num(values, nan=lo) - lo) * (255.0 / (hi - lo)), 0, 255)
    return scaled.astype(np.uint8)


def gray_to_bgr(gray):
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


class SonarYoloNode(Node):
    def __init__(self, args, device):
        super().__init__("dave_sonar_yolo")
        self.args = args
        self.device = device
        self.model = YOLO(args.model)
        self.bridge_error_reported = False
        self.last_inference = 0.0
        self.last_summary = time.monotonic()
        self.frames = 0
        self.inferences = 0
        self.detection_count = 0
        self.inference_ms = 0.0
        self.last_detection_line = 0.0
        self.first_image = True

        input_qos = qos_profile_sensor_data
        output_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.publisher = self.create_publisher(Image, args.output_topic, output_qos)
        self.subscription = self.create_subscription(Image, args.topic, self.on_image, input_qos)
        self.create_timer(5.0, self.report_stats)

        names = getattr(self.model, "names", {})
        self.get_logger().info(
            f"Loaded {args.model}; classes={names}; device={device}; "
            f"rate_limit={args.rate:g} Hz; imgsz={args.imgsz}; conf={args.conf:g}"
        )
        self.get_logger().info(f"Input: {args.topic}; annotated output: {args.output_topic}")
        self.get_logger().info("Read-only perception mode: no joystick, MAVROS, or thruster commands are published.")

    def on_image(self, msg):
        self.frames += 1
        now = time.monotonic()
        if now - self.last_inference < 1.0 / max(self.args.rate, 0.1):
            return  # QoS depth=1 means the next callback uses a fresh frame, not a backlog.
        self.last_inference = now

        try:
            frame = image_to_bgr(msg)
            if self.first_image:
                self.first_image = False
                self.get_logger().info(
                    f"First sonar frame: encoding={msg.encoding}, image={msg.width}x{msg.height}"
                )
            start = time.perf_counter()
            result = self.model.predict(
                source=frame,
                imgsz=self.args.imgsz,
                conf=self.args.conf,
                device=self.device,
                verbose=False,
            )[0]
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            annotated = result.plot()
            output = Image()
            output.header = msg.header
            output.height, output.width = annotated.shape[:2]
            output.encoding = "bgr8"
            output.is_bigendian = 0
            output.step = output.width * 3
            output.data = annotated.tobytes()
            self.publisher.publish(output)

            self.inferences += 1
            self.inference_ms += elapsed_ms
            count = len(result.boxes) if result.boxes is not None else 0
            self.detection_count += count
            if count and time.monotonic() - self.last_detection_line >= 1.0:
                labels = []
                for box in result.boxes:
                    class_id = int(box.cls.item())
                    confidence = float(box.conf.item())
                    labels.append(f"{self.model.names[class_id]} {confidence:.2f}")
                self.get_logger().info(
                    f"Detections: {', '.join(labels)} | inference={elapsed_ms:.0f} ms"
                )
                self.last_detection_line = time.monotonic()
        except Exception as exc:
            if not self.bridge_error_reported:
                self.get_logger().error(f"Inference/image conversion failed: {exc}")
                self.bridge_error_reported = True

    def report_stats(self):
        now = time.monotonic()
        interval = max(now - self.last_summary, 1e-3)
        input_fps = self.frames / interval
        infer_fps = self.inferences / interval
        avg_ms = self.inference_ms / max(self.inferences, 1)
        self.get_logger().info(
            f"Status: input={input_fps:.1f} fps, inference={infer_fps:.1f} fps, "
            f"avg_inference={avg_ms:.0f} ms, detections={self.detection_count}"
        )
        self.frames = self.inferences = self.detection_count = 0
        self.inference_ms = 0.0
        self.last_summary = now


def main():
    args = parse_args()
    if args.rate <= 0:
        raise SystemExit("--rate must be greater than zero")
    if not Path(args.model).is_file():
        raise SystemExit(f"YOLO weights not found: {args.model}")

    if args.device == "auto":
        device = "0" if torch.cuda.is_available() else "cpu"
    elif args.device == "cuda":
        if not torch.cuda.is_available():
            raise SystemExit("CUDA was requested but PyTorch in this WSL environment cannot see a CUDA GPU")
        device = "0"
    else:
        device = "cpu"

    rclpy.init()
    node = SonarYoloNode(args, device)
    if device == "0":
        node.get_logger().info(f"CUDA GPU: {torch.cuda.get_device_name(0)}")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
