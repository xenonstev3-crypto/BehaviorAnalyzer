# Behavior3D Analyzer

开源、Windows 优先、面向非程序员的三维行为数据分析工具。第一期目标是小鼠 cylinder test；本仓库现已完成一期原型：导入、坐标重建、Cylinder 事件分析及结果导出四页 GUI。

## 重要科学限制

仅有动物身体点的三维坐标，且没有圆桶的固定空间参考信息时，无法可靠推断圆桶底面圆心、竖直方向或底面 X/Y 方向。因此不能科学完成坐标重定位。本软件不会用动物平均位置作为圆心，也不会猜测圆桶位置。

每个 trial 必须提供以下之一：

1. 元数据中的底面圆心、竖直参考和底面 X 参考；
2. CSV 内（或 session 元数据内）的固定环境标记；
3. 至少三个不共线的已知底面圆周固定点，以及一个不与竖直平行的方向参考。

## 当前能做什么

- 验证规范宽表 CSV 的基本列、单位、帧率和坐标完整性；
- 以 metadata、固定标记点或底面圆周点建立右手圆桶坐标系；
- 将每个身体点转到新坐标系，并生成可审计的变换记录；
- 检测退化几何、缺列、单位冲突及固定标记过度漂移；
- 运行合成数据单元测试；
- 通过 PySide6 GUI 导入、预览、验证并导出重建坐标。
- 按可修改的“文献常用预设”生成左、右、双侧触壁事件及质量审计。
- 导出 CSV、Excel、JSON、HTML、PDF、事件统计图和时间轴图。

详细使用与数学说明见 [docs/](docs/)。Cylinder 规则、指标和模拟验证见 [docs/cylinder_analysis_rules.md](docs/cylinder_analysis_rules.md)。

结果文件与复核顺序见 [docs/results_and_export.md](docs/results_and_export.md)。

## 启动 GUI

```powershell
python run_gui.py
```

使用步骤见 [docs/stage2_gui_usage.md](docs/stage2_gui_usage.md)。请先用 `sample_data/` 中的模拟 CSV 和 metadata 验证流程，再导入真实数据。

## 不覆盖原始数据

`write_reconstruction_outputs` 会拒绝将重建 CSV 写到输入 CSV 的同一路径。建议每次输出到新的结果目录。原始 CSV 仅以只读方式加载。

## 运行测试

已安装 Python、NumPy 和 pandas 后，在仓库根目录执行：

```powershell
python -m unittest discover -s tests -v
```

本阶段不要求安装任何新依赖。
