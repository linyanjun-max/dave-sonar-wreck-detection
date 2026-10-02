#!/usr/bin/env bash
# =============================================================================
# keep_armed.sh —— 持续保持潜水器解锁（后台守护）
#
#   为什么要它：
#     ArduSub **未解锁时推进器完全不响应**（/mavros/rc/out 恒为 1500）。
#     而仿真慢的时候，解锁指令发出后要十几秒状态位才会变 true，
#     手动解锁一次很容易读到旧值，误以为"推杆没反应"。
#     这个脚本在后台盯着 /mavros/state，一旦发现 armed: false 就重新解锁。
#
#   用法：
#     bash keep_armed.sh                          # 前台运行，Ctrl+C 退出
#     KEEP_ARMED=0 bash start_dave_and_rviz.sh    # 这一次启动不要自动解锁
#     pkill -f keep_armed.sh                      # 只关掉自动解锁
#
#   可调环境变量：
#     KEEP_ARMED_INTERVAL   检查间隔秒数（默认 5）
#     KEEP_ARMED_COOLDOWN   两次解锁尝试之间的最小间隔秒数（默认 25）
# =============================================================================
# 注意：这里**不要**用 set -u。
# ROS 的 setup.bash 会引用未定义的变量（如 AMENT_TRACE_SETUP_FILES），
# 开了 set -u 会让 source 直接失败、脚本秒退。
set +u

source /opt/ros/jazzy/setup.bash
# shellcheck disable=SC1090
source "$HOME/dave_ws_official/install/setup.bash" 2>/dev/null

INTERVAL="${KEEP_ARMED_INTERVAL:-5}"
COOLDOWN="${KEEP_ARMED_COOLDOWN:-25}"

log() { echo "[keep_armed $(date +%T)] $*"; }

trap 'log "已退出"; exit 0' INT TERM

log "已启动：持续保持解锁（检查间隔 ${INTERVAL}s，重试间隔 ${COOLDOWN}s）"
log "关闭方法：用 KEEP_ARMED=0 启动，或执行 pkill -f keep_armed.sh"

last_attempt=0
armed_reported=0        # 0 = 当前认为未解锁, 1 = 当前认为已解锁（只在变化时打印）

while true; do
  sleep "$INTERVAL"

  out="$(timeout 20 ros2 topic echo /mavros/state --once 2>/dev/null || true)"
  if [ -z "$out" ]; then
    continue            # MAVROS 还没起来，或者 /mavros/state 还没数据
  fi

  connected="$(printf '%s\n' "$out" | grep -m1 '^connected:' | awk '{print $2}')"
  armed="$(printf '%s\n' "$out" | grep -m1 '^armed:'     | awk '{print $2}')"
  mode="$(printf '%s\n' "$out" | grep -m1 '^mode:'      | awk '{print $2}')"

  # --- 已经解锁：什么都不做 ---
  if [ "${armed:-false}" = "true" ]; then
    if [ "$armed_reported" != 1 ]; then
      log "已解锁（mode=${mode:-?}），继续监视中"
      armed_reported=1
    fi
    continue
  fi

  # --- 还没连上飞控：等 ---
  if [ "${connected:-false}" != "true" ]; then
    if [ "$armed_reported" != 0 ]; then
      log "MAVROS 未连接，等待中..."
      armed_reported=0
    fi
    continue
  fi

  # --- 连着但未解锁：按冷却时间重试解锁 ---
  now="$(date +%s)"
  if [ "$((now - last_attempt))" -lt "$COOLDOWN" ]; then
    continue
  fi
  last_attempt="$now"
  armed_reported=0

  log "检测到未解锁（mode=${mode:-?}），发送解锁指令..."
  timeout 25 ros2 service call /mavros/cmd/arming \
    mavros_msgs/srv/CommandBool '{value: true}' >/dev/null 2>&1 || true
done