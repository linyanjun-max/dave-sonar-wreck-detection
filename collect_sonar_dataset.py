#!/usr/bin/env python3
"""Save one current DAVE sonar frame each time the user presses S."""

import argparse
import csv
import datetime as dt
import select
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image


# Add/rename choices here when collecting another object class.
CLASS_CHOICES = {
    "1": ("pipe", "水下管道 Pipe"),
    "2": ("box_crate", "箱体 Box/Crate"),
}
DEFAULT_TOPIC = "/model/blueview_p900/multibeam_sonar/sonar_image"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "sonar_dataset"


def choose_class(selected=None):
    if selected is not None:
        for key, (class_name, _) in CLASS_CHOICES.items():
            if class_name == selected:
                return key, class_name
        raise SystemExit(f"unknown class {selected!r}; edit CLASS_CHOICES to add it")
    print("\n请选择本次采集的目标类别：")
    for key, (_, label) in CLASS_CHOICES.items():
        print(f"  {key}) {label}")
    while True:
        choice = input("输入编号并按 Enter：").strip()
        if choice in CLASS_CHOICES:
            return choice, CLASS_CHOICES[choice][0]
        print("选项无效，请输入列表中的编号。")


def image_to_bgr(msg):
    """Convert common ROS Image encodings to an OpenCV BGR uint8 image."""
    enc = msg.encoding.lower()
    h, w, step = int(msg.height), int(msg.width), int(msg.step)
    raw = np.frombuffer(msg.data, dtype=np.uint8)
    if h <= 0 or w <= 0 or step <= 0 or raw.size < h * step:
        raise ValueError(f"invalid dimensions/step: {w}x{h}, step={step}")
    rows = raw[: h * step].reshape(h, step)

    if enc in ("mono8", "8uc1"):
        return cv2.cvtColor(rows[:, :w].copy(), cv2.COLOR_GRAY2BGR)
    if enc in ("rgb8", "bgr8"):
        src = np.ndarray((h, w, 3), np.uint8, buffer=msg.data, strides=(step, 3, 1)).copy()
        return cv2.cvtColor(src, cv2.COLOR_RGB2BGR) if enc == "rgb8" else src
    if enc in ("rgba8", "bgra8"):
        src = np.ndarray((h, w, 4), np.uint8, buffer=msg.data, strides=(step, 4, 1))
        code = cv2.COLOR_RGBA2BGR if enc == "rgba8" else cv2.COLOR_BGRA2BGR
        return cv2.cvtColor(src, code)
    if enc in ("mono16", "16uc1", "32fc1"):
        if enc == "32fc1":
            dtype = np.dtype(">f4" if msg.is_bigendian else "<f4")
            values = np.ndarray((h, w), dtype=dtype, buffer=msg.data, strides=(step, 4)).astype(np.float32)
        else:
            dtype = np.dtype(">u2" if msg.is_bigendian else "<u2")
            values = np.ndarray((h, w), dtype=dtype, buffer=msg.data, strides=(step, 2)).astype(np.float32)
        valid = np.isfinite(values)
        if not valid.any():
            gray = np.zeros((h, w), dtype=np.uint8)
        else:
            lo, hi = np.percentile(values[valid], (1, 99))
            if hi <= lo:
                hi = lo + 1.0
            gray = np.clip((np.nan_to_num(values, nan=lo) - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    raise ValueError(f"unsupported image encoding: {msg.encoding!r}")


class SonarCollector(Node):
    def __init__(self, topic):
        super().__init__("dave_sonar_dataset_collector")
        self.latest = None
        self.latest_received_at = 0.0
        self.subscription = self.create_subscription(
            Image, topic, self.on_image, qos_profile_sensor_data
        )
        self.get_logger().info(f"订阅声呐图像：{topic}")
        self.get_logger().info("只读取图像；不会发布摇杆、MAVROS 或推进器指令。")

    def on_image(self, msg):
        try:
            self.latest = image_to_bgr(msg)
            self.latest_received_at = time.monotonic()
            self.latest_msg = msg
        except Exception as exc:
            self.get_logger().error(f"图像解码失败：{exc}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="ROS 2 sonar Image topic")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Dataset output directory")
    parser.add_argument("--class-name", choices=[entry[0] for entry in CLASS_CHOICES.values()],
                        help="Selected class; omit to choose interactively")
    parser.add_argument("--stale-seconds", type=float, default=3.0,
                        help="Refuse capture if the latest sonar frame is older than this")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.stale_seconds <= 0:
        raise SystemExit("--stale-seconds must be positive")

    _, class_name = choose_class(args.class_name)
    output_dir = Path(args.output).expanduser().resolve() / class_name
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir.parent / "manifest.csv"
    manifest_exists = manifest_path.exists()

    rclpy.init()
    node = SonarCollector(args.topic)
    capture_count = 0
    old_termios = None
    try:
        if not sys.stdin.isatty():
            raise RuntimeError("请在交互式终端运行，以便使用 S/Q 按键。")
        import termios
        import tty

        old_termios = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        print(f"\n类别：{class_name}；保存位置：{output_dir}")
        print("等待声呐帧。按 S 保存一张当前帧；按 Q 退出。\n", flush=True)

        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.05)
            ready, _, _ = select.select([sys.stdin], [], [], 0)
            if not ready:
                continue
            key = sys.stdin.read(1).lower()
            if key == "q":
                break
            if key != "s":
                continue
            if node.latest is None:
                print("尚未收到声呐图像，请确认 DAVE 正在运行且话题正确。", flush=True)
                continue
            age = time.monotonic() - node.latest_received_at
            if age > args.stale_seconds:
                print(f"最新声呐帧已过期（{age:.1f}s），暂不保存。", flush=True)
                continue

            now = dt.datetime.now().astimezone()
            stamp = now.strftime("%Y%m%d_%H%M%S_%f")[:-3]
            image_path = output_dir / f"{class_name}_{stamp}.png"
            if not cv2.imwrite(str(image_path), node.latest):
                print(f"保存失败：{image_path}", flush=True)
                continue

            msg = node.latest_msg
            with manifest_path.open("a", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                if not manifest_exists:
                    writer.writerow(("image", "class", "topic", "encoding", "width", "height",
                                     "frame_id", "ros_stamp_sec", "ros_stamp_nanosec"))
                    manifest_exists = True
                writer.writerow((str(image_path.relative_to(manifest_path.parent)), class_name,
                                 args.topic, msg.encoding, msg.width, msg.height, msg.header.frame_id,
                                 msg.header.stamp.sec, msg.header.stamp.nanosec))
            capture_count += 1
            print(f"已保存第 {capture_count} 张：{image_path} ({msg.width}x{msg.height}, {msg.encoding})",
                  flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        if old_termios is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_termios)
        node.destroy_node()
        rclpy.shutdown()
    print(f"采集结束，本次保存 {capture_count} 张；目录：{output_dir}")


if __name__ == "__main__":
    main()
