#!/usr/bin/env bash

# Launch a fixed BlueView P900 over the selected target and capture sonar frames.
# This standalone sensor launch does not start ArduSub, MAVROS, a vehicle, or controls.
set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORLD_FILE="$ROOT/sonar_collection_static.world"
WORLD_NAME="dave_sonar_collection_static"
SONAR_TOPIC=""
OUTPUT_DIR="$ROOT/sonar_dataset"
OVERLAY=""
WORLD_PID=""
RVIZ_PID=""

echo "选择本轮要采集的目标："
echo "  1) Pipe（水下管道）"
echo "  2) Box/Crate（箱体）"
read -r -p "输入 1 或 2，然后按 Enter：" choice
case "$choice" in
  1)
    class_name="pipe"
    sensor_x=48; sensor_y=16; sensor_z=-12
    sensor_roll=0; sensor_pitch=0.60; sensor_yaw=1.5707963
    ;;
  2)
    class_name="box_crate"
    sensor_x=30; sensor_y=12; sensor_z=-12
    sensor_roll=0; sensor_pitch=0.60; sensor_yaw=0
    ;;
  *) echo "无效选项，请输入 1 或 2。" >&2; exit 2 ;;
esac

if [[ ! -f "$WORLD_FILE" ]]; then
  echo "[ERROR] 找不到采集专用 world：$WORLD_FILE" >&2
  exit 2
fi
source /opt/ros/jazzy/setup.bash
source "$HOME/dave_ws/install/setup.bash" 2>/dev/null || true
source "$HOME/dave_ws_official/install/setup.bash" 2>/dev/null || true

# Resolve DAVE's existing sonar RViz config only after ROS workspaces are sourced.
RVIZ_PREFIX="$(ros2 pkg prefix dave_multibeam_sonar_demo 2>/dev/null || true)"
RVIZ_CONFIG="$RVIZ_PREFIX/share/dave_multibeam_sonar_demo/rviz/multibeam_sonar.rviz"
if [[ -z "$RVIZ_PREFIX" || ! -f "$RVIZ_CONFIG" ]]; then
  echo "[ERROR] 找不到 DAVE 声呐 RViz 配置：$RVIZ_CONFIG" >&2
  echo "       请确认 dave_multibeam_sonar_demo 包已安装并 source。" >&2
  exit 2
fi

# WSL display/CUDA setup matching the existing DAVE launcher.
export LD_LIBRARY_PATH="/usr/lib/wsl/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/mnt/wslg/runtime-dir}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$HOME/dave_ws/install/multibeam_sonar_system/lib/multibeam_sonar_system:$HOME/dave_ws/install/multibeam_sonar/lib/multibeam_sonar${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"

if [[ -f "$HOME/venv-dave-stage1/bin/activate" ]]; then
  source "$HOME/venv-dave-stage1/bin/activate"
elif [[ -f "$HOME/venv-ardupilot/bin/activate" && -z "${VIRTUAL_ENV:-}" ]]; then
  source "$HOME/venv-ardupilot/bin/activate"
fi

if ! python3 - <<'PY'
import importlib.util
required = ("rclpy", "sensor_msgs", "numpy", "cv2")
missing = [name for name in required if importlib.util.find_spec(name) is None]
for name in required:
    print(f"[依赖] {name}: {'MISSING' if name in missing else 'OK'}", flush=True)
raise SystemExit(bool(missing))
PY
then
  echo "[ERROR] 缺少 ROS 图像采集依赖。请在 ROS 兼容的 Python 环境安装 numpy 和 opencv-python。" >&2
  exit 2
fi

# Temporarily expose the private copy of the world through DAVE's world package.
OVERLAY="$(mktemp -d "${TMPDIR:-/tmp}/dave-sonar-collection.XXXXXX")"
mkdir -p "$OVERLAY/share/ament_index/resource_index/packages" \
         "$OVERLAY/share/dave_worlds/worlds"
: > "$OVERLAY/share/ament_index/resource_index/packages/dave_worlds"
cp -- "$WORLD_FILE" "$OVERLAY/share/dave_worlds/worlds/$WORLD_NAME.world"
export AMENT_PREFIX_PATH="$OVERLAY${AMENT_PREFIX_PATH:+:$AMENT_PREFIX_PATH}"

cleanup() {
  if [[ -n "$RVIZ_PID" ]] && kill -0 "$RVIZ_PID" 2>/dev/null; then
    kill "$RVIZ_PID" 2>/dev/null || true
    wait "$RVIZ_PID" 2>/dev/null || true
  fi
  if [[ -n "$WORLD_PID" ]] && kill -0 "$WORLD_PID" 2>/dev/null; then
    kill -INT "$WORLD_PID" 2>/dev/null || true
    for _ in $(seq 1 10); do
      kill -0 "$WORLD_PID" 2>/dev/null || break
      sleep 1
    done
    kill "$WORLD_PID" 2>/dev/null || true
    wait "$WORLD_PID" 2>/dev/null || true
  fi
  if [[ -n "$OVERLAY" && -d "$OVERLAY" ]]; then
    rm -rf -- "$OVERLAY"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "[DAVE] 启动无潜水器的静态声呐采集场景。"
echo "[DAVE] 目标类别：$class_name；声呐固定位置：($sensor_x, $sensor_y, $sensor_z)"
ros2 launch dave_demos dave_sensor.launch.py \
  namespace:=blueview_p900 \
  "world_name:=$WORLD_NAME" \
  paused:=false \
  gui:=true \
  "x:=$sensor_x" "y:=$sensor_y" "z:=$sensor_z" \
  "roll:=$sensor_roll" "pitch:=$sensor_pitch" "yaw:=$sensor_yaw" &
WORLD_PID=$!

echo "[DAVE] 等待声呐图像话题（最长 180 秒）"
ready=0
for _ in $(seq 1 180); do
  if ! kill -0 "$WORLD_PID" 2>/dev/null; then
    echo "[ERROR] 静态声呐场景启动失败。" >&2
    exit 1
  fi
  # dave_sensor.launch.py publishes an absolute /sensor/... topic in this setup;
  # discover it instead of assuming the vehicle-style /model/<name>/... path.
  SONAR_TOPIC="$(ros2 topic list 2>/dev/null | awk '/\/multibeam_sonar\/sonar_image$/ { print; exit }')"
  if [[ -n "$SONAR_TOPIC" ]]; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo "[ERROR] 声呐图像话题未出现；请检查 Gazebo 和 DAVE 启动日志。" >&2
  exit 1
fi

echo "[DAVE] 检测到声呐图像话题：$SONAR_TOPIC"
# Reuse DAVE's sonar RViz layout, but point its image and point-cloud displays
# at the topics emitted by the standalone sensor.
RVIZ_CONFIG_LOCAL="$OVERLAY/sonar_collection.rviz"
SONAR_POINT_CLOUD_TOPIC="${SONAR_TOPIC%/sonar_image}/point_cloud"
sed \
  -e "s#Value: .*/multibeam_sonar/sonar_image#Value: $SONAR_TOPIC#" \
  -e "s#Value: .*/multibeam_sonar/point_cloud#Value: $SONAR_POINT_CLOUD_TOPIC#" \
  "$RVIZ_CONFIG" > "$RVIZ_CONFIG_LOCAL"

echo "[DAVE] 启动 RViz 声呐图窗口..."
rviz2 -d "$RVIZ_CONFIG_LOCAL" &
RVIZ_PID=$!

echo "[DAVE] 场景就绪。采集终端按 S 保存当前帧，按 Q 结束采集。"
python3 "$ROOT/collect_sonar_dataset.py" \
  --class-name "$class_name" \
  --topic "$SONAR_TOPIC" \
  --output "$OUTPUT_DIR"
