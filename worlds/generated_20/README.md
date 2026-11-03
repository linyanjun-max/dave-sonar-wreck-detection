# 生成世界合集（20 个）

这一目录是批量生成的海底世界：每个世界 = 一份 `NN.world` + 一份同名 `NN.truth.yaml` 真值。它们是同一条自动生成流程（沙丘地形分析 → 物体摆放 → 贴地计算 → 真值导出）的产物，用于给声呐识别提供多种场景，而不是靠手工改场景。

| 项目 | 值 |
|---|---|
| 世界数 | 20 |
| seed | 41001–41012、42001–42008，互不相同 |
| 每个世界的物体 | 4–6 个，**必有 1 艘沉船** |
| 非沉船模型 | 11 种：货箱、施工桶、55 加仑桶、电缆盘、飞行记录仪、带筋安全帽、标准安全帽、声呐浮标、鱼雷、未爆弹 |
| 地形 | Fuel `hmoyen/sand_heightmap`（500×500 m，z −16.0…+9.0），静态、不含 `<heightmap>` |
| 摆放区域 | 60×60 m 三套区域轮换，方位 ±180° 全向散开 |
| 物体间距 | OBB 不重叠，最近间距 ≥ 1.5 m |
| 贴地 | `z = 足印内地形最高点 + 2 cm − 模型 AABB 最低点` |
| 机器人 | **不含**。建议出生点在真值文件的 `rig` 段 |
| 声呐 | 世界声明了 `multibeam_sonar_system` 插件，但本批世界未写入声呐平台 |

## 索引

"物体"列括号内是 `model://` 目录名。

| # | seed | 物体数 | 物体 |
|---|---|---:|---|
| 01 | 41001 | 5 | 沉船(sunken_ship_distorted)、货箱(large_crate)、油桶(construction_barrel)、未爆弹(unexploded_ordnance_a)、安全帽(hardhat_standard) |
| 02 | 41002 | 4 | 沉船(sunken_ship_distorted)、货箱(large_crate)、油桶(construction_barrel)、电缆盘(cable_spool) |
| 03 | 41003 | 6 | 沉船(sunken_ship_distorted)、油桶(drum_55gal)、安全帽(hardhat_ribbed)、飞行记录仪(flight_data_recorder)、未爆弹(unexploded_ordnance_a)、安全帽(hardhat_standard) |
| 04 | 41004 | 5 | 沉船(sunken_ship_distorted)、声呐浮标(sonobuoy)、电缆盘(cable_spool)、货箱(large_crate)、飞行记录仪(flight_data_recorder) |
| 05 | 41005 | 4 | 沉船(sunken_ship_distorted)、安全帽(hardhat_ribbed)、鱼雷(torpedo_mk48)、安全帽(hardhat_standard) |
| 06 | 41006 | 6 | 沉船(sunken_ship_distorted)、货箱(large_crate)、飞行记录仪(flight_data_recorder)、油桶(drum_55gal)、安全帽(hardhat_standard)、未爆弹(unexploded_ordnance_a) |
| 07 | 41007 | 5 | 沉船(sunken_ship_distorted)、油桶(construction_barrel)、货箱(large_crate)、鱼雷(torpedo_mk48)、电缆盘(cable_spool) |
| 08 | 41008 | 4 | 沉船(sunken_ship_distorted)、安全帽(hardhat_ribbed)、声呐浮标(sonobuoy)、电缆盘(cable_spool) |
| 09 | 41009 | 6 | 沉船(sunken_ship_distorted)、油桶(drum_55gal)、电缆盘(cable_spool)、货箱(large_crate)、安全帽(hardhat_ribbed)、未爆弹(unexploded_ordnance_a) |
| 10 | 41010 | 5 | 沉船(sunken_ship_distorted)、油桶(construction_barrel)、安全帽(hardhat_standard)、声呐浮标(sonobuoy)、油桶(drum_55gal) |
| 11 | 41011 | 4 | 沉船(sunken_ship_distorted)、鱼雷(torpedo_mk48)、飞行记录仪(flight_data_recorder)、电缆盘(cable_spool) |
| 12 | 41012 | 6 | 沉船(sunken_ship_distorted)、鱼雷(torpedo_mk48)、安全帽(hardhat_ribbed)、声呐浮标(sonobuoy)、电缆盘(cable_spool)、油桶(drum_55gal) |
| 13 | 42001 | 5 | 沉船(sunken_ship_distorted)、未爆弹(unexploded_ordnance_a)、声呐浮标(sonobuoy)、安全帽(hardhat_standard)、鱼雷(torpedo_mk48) |
| 14 | 42002 | 4 | 沉船(sunken_ship_distorted)、安全帽(hardhat_ribbed)、飞行记录仪(flight_data_recorder)、未爆弹(unexploded_ordnance_a) |
| 15 | 42003 | 6 | 沉船(sunken_ship_distorted)、飞行记录仪(flight_data_recorder)、安全帽(hardhat_standard)、安全帽(hardhat_ribbed)、声呐浮标(sonobuoy)、货箱(large_crate) |
| 16 | 42004 | 5 | 沉船(sunken_ship_distorted)、鱼雷(torpedo_mk48)、油桶(construction_barrel)、油桶(drum_55gal)、安全帽(hardhat_standard) |
| 17 | 42005 | 4 | 沉船(sunken_ship_distorted)、电缆盘(cable_spool)、油桶(construction_barrel)、声呐浮标(sonobuoy) |
| 18 | 42006 | 6 | 沉船(sunken_ship_distorted)、未爆弹(unexploded_ordnance_a)、飞行记录仪(flight_data_recorder)、电缆盘(cable_spool)、油桶(drum_55gal)、鱼雷(torpedo_mk48) |
| 19 | 42007 | 5 | 沉船(sunken_ship_distorted)、油桶(drum_55gal)、安全帽(hardhat_standard)、电缆盘(cable_spool)、货箱(large_crate) |
| 20 | 42008 | 4 | 沉船(sunken_ship_distorted)、飞行记录仪(flight_data_recorder)、声呐浮标(sonobuoy)、未爆弹(unexploded_ordnance_a) |

## 真值文件

`NN.truth.yaml` 与 `NN.world` 一一对应，包含：

- `terrain`：地形模型名、来源 DAE、位姿；
- `rig`：建议的机器人出生点 `x/y/z/yaw`、离底高度，以及该点地形统计；
- `placement`：本次生成用的区域、最大起伏、最大坡度、留白、最小间距、方位与距离限制；
- `objects[]`：每个物体的 `class`、`label`、位姿、AABB、OBB、离出生点距离与方位，以及物体足印内的地形统计。

语义标签（`gz-sim-label-system`）与类别的对应关系：

| label | 类别 | 模型 |
|---:|---|---|
| 1 | 沉船 | `sunken_ship_distorted` |
| 3 | 油桶 | `construction_barrel`、`drum_55gal` |
| 4 | 货箱 | `large_crate` |
| 5 | 电缆盘 | `cable_spool` |
| 7 | 未爆弹 | `unexploded_ordnance_a` |
| 8 | 鱼雷 | `torpedo_mk48` |
| 9 | 安全帽 | `hardhat_standard`、`hardhat_ribbed` |
| 11 | 声呐浮标 | `sonobuoy` |
| 12 | 飞行记录仪 | `flight_data_recorder` |

## 运行

这些世界用 `model://` 引用外部模型，模型必须能被 Gazebo 找到，否则会以 `Unable to find uri[...]` 加载失败：

```bash
# 需要: Fuel 上的 hmoyen/sand_heightmap + 上表中的目标模型（首次运行需联网）
# 以及 multibeam_sonar_system 插件
export GZ_SIM_RESOURCE_PATH="$HOME/.gz/fuel:$GZ_SIM_RESOURCE_PATH"
gz sim -r worlds/generated_20/world_01.world
```

世界本身不含机器人。要驾驶或采集声呐，请按真值文件 `rig` 段的位姿生成 BlueROV2（自带多波束声呐），或改为固定声呐平台。

## 已知限制

- 物体只做偏航（yaw）旋转，不倾斜，也不做物理下沉；世界里的物体都是静态的。
- 生成时要求物体足印内起伏 ≤ 0.5 m、坡度 ≤ 25°，因此本批 20 个世界都落在沙丘地图 `x ≈ +10…+30 m` 的平坦盆地，`truth.yaml` 中 `relief` 均为 0。想要有起伏的场景需要放宽这两个阈值。
- 物理步长 1 ms（为声呐距离分辨率设），比 DAVE 官方海洋世界的 4 ms 更耗算力；再叠加机器人 + ArduSub 时实时因子会明显下降。
- 目标库只有 11 种非沉船模型，类别多样性远少于真实海底。
- 这些世界不包含训练数据与标注，声呐图像需要自行采集后再标注。
