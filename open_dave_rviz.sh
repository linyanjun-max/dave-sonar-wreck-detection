#!/usr/bin/env bash

# Open the RViz view for the moving BlueROV2 multibeam model.
# Run this in a second WSL terminal after start_dave_official.sh is running.

source /opt/ros/jazzy/setup.bash
source "$HOME/dave_ws/install/setup.bash" 2>/dev/null || true
source "$HOME/dave_ws_official/install/setup.bash" 2>/dev/null || true

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/mnt/wslg/runtime-dir}"

# The sonar image is published directly by DAVE. Only the Gazebo camera needs
# this bridge for the optional camera display in RViz.
ros2 run ros_gz_bridge parameter_bridge \
  "/model/bluerov2_heavy_multibeam_sonar/camera@sensor_msgs/msg/Image[gz.msgs.Image" \
  "/model/bluerov2_heavy_multibeam_sonar/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo" \
  > /tmp/dave_camera_bridge.log 2>&1 &
BRIDGE_PID=$!

cleanup() {
  kill "$BRIDGE_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

rviz2 -d "$ROOT/dave_bluerov2_multibeam.rviz"
