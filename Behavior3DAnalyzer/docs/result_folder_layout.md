# 结果目录结构

在 GUI 的“重建坐标系”页面选择一个**单独的空结果目录**后，Behavior3D Analyzer 只会在该目录内创建以下分类文件夹：

```text
你选择的结果目录/
├─ data/
│  ├─ coordinates.csv       # 重建后的坐标；原始 CSV 不会被改写
│  └─ transform.json        # 原始到新坐标系的变换与审计记录
├─ analysis/
│  ├─ events.csv            # 有效触壁事件
│  ├─ event_audit.csv       # 候选事件、排除原因与持续时间审计
│  ├─ frame_quality.csv     # 逐帧质量与候选触壁判定
│  └─ summary.json          # 分析摘要与完整规则配置
├─ reports/
│  ├─ report.xlsx
│  ├─ report.html
│  ├─ report.pdf
│  ├─ counts.png
│  └─ timeline.png
├─ figures/
│  ├─ figure1.png           # 600 dpi 位图
│  ├─ figure1.pdf           # 矢量图
│  └─ figure1.svg           # 可编辑矢量图
└─ video/
   └─ keypoints_3d.mp4      # 三维关键点动画
```

文件名刻意保持简短，因为每个结果目录仅应对应一个 trial。若同名结果已经存在，软件会停止并提示用户选择新的空目录；不会覆盖已有结果或原始数据。
