# 一期宽表 CSV 与 metadata 输入规格

## 首先：何时不能重建

动物身体点本身不包含圆桶的固定空间信息。没有底面圆心、竖直方向和底面 X 参考时，软件必须停止，不能用动物平均位置推测圆心，也不能猜测圆桶方向。

每个 CSV 只含一个 trial。必需列为：`trial_id`、`animal_id`、`frame`、`time_s`、`fps`、`coordinate_unit`。每个点都用 `{point_name}_x`、`{point_name}_y`、`{point_name}_z` 三列表示；可附加 `{point_name}_likelihood` 与 `{point_name}_error`，转换时原样保留。

`coordinate_unit` 必须在同一 trial 内完全一致，例如 `mm`。`fps` 必须为正且全 trial 一致。`frame` 和 `time_s` 必须按时间排序且不能缺失。模板见 `templates/wide_table_template.csv`。

## 圆桶参考的三种方式

### A. 最推荐：metadata 直接提供

在 JSON/YAML 的 `coordinate_reference` 中提供：

- `bottom_center_raw`：桶底圆心 `[x,y,z]`；
- `vertical_reference_raw`（向量）或 `top_center_raw`（点）；
- `x_reference_raw`（向量或底面固定点），及其是否为点的布尔字段；
- `flip_x`、`flip_y`（可选，默认为否）；
- 圆桶 `radius`、`height`、单位与点名映射。

### B. CSV 内的固定环境标记

推荐点名：`cylinder_bottom_center`、`cylinder_top_center`、`x_axis_marker`。它们可每帧重复，但必须实际为固定环境点。session-level 转换取每个标记的完整坐标中位数，并报告最大漂移；超过用户声明的容许漂移即失败。frame-level 转换尚未实现，后续仅在用户确认固定标记质量良好时增加。

### C. 多个底面圆周点

至少三个不共线、已知位于底面圆周的固定标记，外加一个用于确定底面正 X 的固定方向点。平面法向量正负存在二义性，因此还必须提供明确的 `vertical_reference_raw` 来指定 +Z。程序报告平面拟合残差、圆拟合残差与拟合半径；任一门槛不通过即停止。

## 缺失值与质量列

坐标变换不插值、不填补、也不制造缺失值。若任一原始点某帧 XYZ 为 NaN，该点对应的重建 XYZ 仍为 NaN；其他点及 likelihood/error 等列保留。Cylinder 事件层将在下一阶段定义怎样处理质量与缺失。

## 模拟样例

`sample_data/simulated_cylinder_trial.csv` 与其 JSON metadata 可用于导入验证。它使用毫米，底面圆心原始坐标为 `[10,-5,3]`，桶顶为 `[10,-5,303]`。该样例不是生物学数据，也不包含触壁结论。
