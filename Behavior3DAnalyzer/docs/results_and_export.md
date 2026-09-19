# 结果与导出

第四个 GUI 页面在完成 Cylinder 分析后显示左、右、双侧和总有效事件、使用比例与偏侧指数。点击导出会写入独立结果目录，且遇到同名文件会停止，不会覆盖已有结果。

## 导出内容

- `events_{trial_id}.csv`：有效事件的起止 frame/时间、分类、持续时间、爪坐标、距壁和质量标志；
- `event_audit_{trial_id}.csv`：候选段及其排除理由；
- `frame_quality_{trial_id}.csv`：逐帧坐标、径向距离、质量、rearing 和候选状态；
- `summary_{trial_id}.json`：统计、软件版本、预设版本及完整配置快照；
- `report_{trial_id}.xlsx`：摘要、可编辑柱状图、事件、审计和逐帧质量工作表；
- `report_{trial_id}.html`：浏览器可读摘要；
- `report_{trial_id}.pdf`：可分享的两页摘要报告；
- 两张 PNG：有效事件柱状图、事件时间轴图。

PDF 优先使用 `reportlab`；若它未安装，软件会自动改用已安装的 PySide6 Windows PDF 后端，因此不会阻断 Excel、HTML、PNG 和 PDF 的完整导出。CSV、JSON、Excel、HTML 和 PNG 不改写原始 CSV。

## 复核顺序

1. 先看 `summary_*.json` 中的参数和公式；
2. 再看 `events_*.csv` 与时间轴，确认每个有效事件；
3. 用 `event_audit_*.csv` 检查被排除的短段；
4. 用 `frame_quality_*.csv` 核查低质量、缺失、越界与 rearing 筛选；
5. 最后把 Excel/HTML/PDF 用于共享，不应取代对逐事件数据的审阅。
