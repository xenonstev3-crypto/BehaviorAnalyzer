# Sticker Test Module

The Sticker Test module is a peer of Cylinder Test, not a later tab within its workflow.

## Entry and independent workflow

Start from the **experiment selection** screen and choose **Sticker Test**. Its four steps are independent of Cylinder Test:

1. **Import data** — choose one raw 3D wide-table CSV and a dedicated result folder.
2. **Coordinate preparation** — inspect and confirm coordinate units, frame rate, keypoints, and the upstream coordinate frame.
3. **Sticker analysis** — configure target, effectors, distance threshold, quality threshold, and sustained-contact rules.
4. **Results and export** — write figures and a 3D keypoint video.

The Sticker workflow never requests, infers, or reuses a cylinder center, radius, wall, or cylinder reconstruction. Contact is based on target–effector Euclidean distance, which is unchanged by a common rigid transformation. Where standardized orientation is needed for visual display, provide upstream-calibrated coordinates with real fixed references; the application must not invent an axis from animal positions.

## Analysis interpretation

The module reports sustained target-effector contact events and a **cessation candidate** based on a sustained post-peak decrease in interaction intensity. A cessation candidate is not direct evidence that the sticker detached. Review the source video or an independently measured sticker-state marker before interpreting it as removal time.

## Outputs

Within the result folder selected in the Sticker workflow:

- `analysis/events.csv`: included and excluded contact events;
- `analysis/frame_quality.csv`: per-frame distance, nearest effector, and quality flags;
- `analysis/summary.json`: configuration and summary metrics;
- `figures/figure1.png`, `.pdf`, `.svg`: distance and interaction-intensity plots;
- `video/keypoints_3d.mp4`: 3D keypoint animation with axes.

Existing output files are never overwritten.
