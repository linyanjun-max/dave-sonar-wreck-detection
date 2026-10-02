#!/usr/bin/env bash

# Start the existing DAVE world first, then open its existing RViz view.
# This script does not modify the scene or either original launch script.
set -eo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORLD_PID=""
RVIZ_PID=""
KEEP_ARMED_PID=""

cleanup() {
  [[ -n "$RVIZ_PID" ]] && kill "$RVIZ_PID" 2>/dev/null || true
  [[ -n "$KEEP_ARMED_PID" ]] && kill "$KEEP_ARMED_PID" 2>/dev/null || true
  [[ -n "$WORLD_PID" ]] && kill "$WORLD_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

source /opt/ros/jazzy/setup.bash
source "$HOME/dave_ws/install/setup.bash" 2>/dev/null || true
source "$HOME/dave_ws_official/install/setup.bash" 2>/dev/null || true

echo "[DAVE] Starting the existing world..."
bash "$ROOT/start_dave_official.sh" "$@" &
WORLD_PID=$!

echo "[DAVE] Waiting for the vehicle odometry topic (up to 120 seconds)..."
ready=0
for _ in $(seq 1 120); do
  if ! kill -0 "$WORLD_PID" 2>/dev/null; then
    echo "[ERROR] The world launch process exited." >&2
    exit 1
  fi
  if ros2 topic list 2>/dev/null | grep -q '^/model/bluerov2_heavy_multibeam_sonar/odometry$'; then
    ready=1
    break
  fi
  sleep 1
done

if [[ "$ready" != 1 ]]; then
  echo "[ERROR] Vehicle odometry did not appear within 120 seconds; RViz was not started." >&2
  exit 1
fi

# 自动保持解锁：仿真慢时手动解锁很烦，这里挂一个后台守护，
# 发现 armed: false 就自动重新解锁。想关掉就 KEEP_ARMED=0 启动。
if [[ "${KEEP_ARMED:-1}" != "0" ]]; then
  echo "[DAVE] Starting the keep-armed watchdog (KEEP_ARMED=0 to disable)..."
  bash "$ROOT/keep_armed.sh" &
  KEEP_ARMED_PID=$!
else
  echo "[DAVE] keep-armed watchdog disabled (KEEP_ARMED=0)."
fi

echo "[DAVE] World is ready. Starting the existing RViz configuration..."
bash "$ROOT/open_dave_rviz.sh" &
RVIZ_PID=$!
wait "$RVIZ_PID"
