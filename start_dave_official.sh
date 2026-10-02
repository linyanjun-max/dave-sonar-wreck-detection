#!/usr/bin/env bash

# DAVE official teleoperation path for ROS 2 Jazzy + Gazebo Harmonic.
# This uses DAVE's built-in web joystick and ArduPilot/ArduSub backend.

source /opt/ros/jazzy/setup.bash
source "$HOME/dave_ws/install/setup.bash" 2>/dev/null || true
source "$HOME/dave_ws_official/install/setup.bash" 2>/dev/null || true

# CUDA / GPU：WSL2 下 CUDA 驱动库在 /usr/lib/wsl/lib。
# 不设这一行时，声呐插件的 CUDA 初始化会失败
# （日志：no CUDA-capable device is detected），整个仿真会卡住不步进。
# 交互式终端里能靠 ~/.bashrc 生效，但脚本方式启动时必须自己设。
export LD_LIBRARY_PATH="/usr/lib/wsl/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# Make the WSLg display explicit when this script is launched with bash.
export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/mnt/wslg/runtime-dir}"

# The WebSocket node and ArduSub are installed outside the ROS packages.
export PATH="$HOME/venv-ardupilot/bin:$HOME/ardupilot/build/sitl/bin:/opt/ros/jazzy/bin:$PATH"

# Official ArduPilot Gazebo plugin built against ROS Jazzy's Gazebo vendor
# libraries, plus the DAVE sonar plugins.
export GZ_SIM_SYSTEM_PLUGIN_PATH="$HOME/ardupilot_gazebo_ros_ws/install/ardupilot_gazebo/lib/ardupilot_gazebo:$HOME/dave_ws/install/multibeam_sonar_system/lib/multibeam_sonar_system:$HOME/dave_ws/install/multibeam_sonar/lib/multibeam_sonar"

# Keep the official Gazebo launch in the foreground. Do not press Ctrl+C
# until the Gazebo window is visible and you want to stop the simulation.
exec ros2 launch dave_demos dave_robot.launch.py \
  x:=15 \
  y:=2 \
  z:=-10 \
  namespace:=bluerov2_heavy_multibeam_sonar \
  world_name:=dave_ocean_waves_sonar_training \
  paused:=false \
  use_teleop:=true \
  use_web_joystick:=true \
  joystick_ws_port:=8765 \
  "$@"
