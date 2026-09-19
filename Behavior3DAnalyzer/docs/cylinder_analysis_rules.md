# Cylinder 事件规则与“文献常用预设”

本模块只读取 `*_reconstructed_x/y/z`。没有通过固定圆桶参考完成重建的 trial 会被拒绝；软件不会从原始动物坐标猜测圆桶位置。

“文献常用预设”是可追溯、可修改的起点，不是唯一国际标准。完整参数在 `presets/cylinder_literature_common_v1.json`；实际使用规则会写入 `summary_*.json`。

## 候选与有效事件

`radial_distance = sqrt(x² + y²)`，`wall_distance_signed = cylinder_radius - radial_distance`。候选帧必须同时通过坐标完整性、可选 likelihood/error、高度范围、距壁带和可选 rearing 条件。连续候选段还必须达到 `min_contact_frames` 才成为有效事件。短段保留在 `event_audit_*.csv`，而每帧的质量、径向距离、候选状态和原因保留在 `frame_quality_*.csv`。

左右事件在 `bilateral_window_frames` 内重叠或接近时合并为 `bilateral`；其余事件为 `left` 或 `right`。事件表包含起止 frame/时间、持续时间、爪坐标、距壁距离、质量标志和排除字段。

## 指标

默认双侧事件的 0.5 分配给每一侧：

```text
left_weighted  = left_events  + 0.5 * bilateral_events
right_weighted = right_events + 0.5 * bilateral_events
laterality_index = (right_weighted - left_weighted) / (right_weighted + left_weighted)
```

正值表示右侧加权使用更多，负值表示左侧更多。双侧权重可改，实际值随配置导出。

## 模拟验证

用 `sample_data/simulated_cylinder_events.csv` 和同名 metadata 重建后，以预设分析，预期得到 1 个双侧事件和 1 个左侧事件；末尾右侧两帧因不足 3 帧被排除。这是软件逻辑样例，不是生物学阈值依据。
