#!/usr/bin/env bash

# Read-only YOLO inference against the already-running DAVE sonar topic.
set -eo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source /opt/ros/jazzy/setup.bash

# Reuse the user's ROS-compatible Python environment when it exists.
if [[ -f "$HOME/venv-dave-stage1/bin/activate" ]]; then
  source "$HOME/venv-dave-stage1/bin/activate"
elif [[ -f "$HOME/venv-ardupilot/bin/activate" && -z "${VIRTUAL_ENV:-}" ]]; then
  source "$HOME/venv-ardupilot/bin/activate"
fi

if ! python3 - <<'PY'
import importlib.util
import sys

modules = ("rclpy", "sensor_msgs", "cv2", "numpy", "torch", "ultralytics")
missing = []
for name in modules:
    available = importlib.util.find_spec(name) is not None
    print(f"[依赖] {name}: {'OK' if available else 'MISSING'}", flush=True)
    if not available:
        missing.append(name)

if importlib.util.find_spec("torch") is not None:
    import torch
    try:
        cuda_ok = torch.cuda.is_available()
        print(f"[设备] WSL PyTorch CUDA: {cuda_ok}; torch={torch.__version__}", flush=True)
        if cuda_ok:
            print(f"[设备] GPU: {torch.cuda.get_device_name(0)}", flush=True)
    except Exception as exc:
        print(f"[设备] CUDA 检查失败: {exc}", flush=True)

sys.exit(bool(missing))
PY
then
  echo "[ERROR] 当前 Python 环境缺少上面标记为 MISSING 的依赖。"
  echo "若仅 ultralytics 缺失，在同一个虚拟环境中运行：python3 -m pip install ultralytics"
  echo "若 cv2 也缺失，再安装：python3 -m pip install opencv-python"
  echo "如果 torch 缺失或 CUDA=False，请先把检查输出发来；不要盲目重装 PyTorch/CUDA。"
  echo "本脚本只 source ROS Jazzy，不加载可能失效的 dave_ws overlay。"
  exit 2
fi

exec python3 "$ROOT/sonar_yolo_realtime.py" "$@"
