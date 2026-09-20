# Behavior3D Analyzer

Behavior3D Analyzer is an open-source, Windows-first desktop application for reproducible analysis of three-dimensional animal behaviour data. It is designed for researchers who receive frame-wise 3D coordinates from an upstream pose-estimation system and do not want to write code for routine analysis.

The current public prototype implements a complete mouse cylinder-test workflow. It deliberately does **not** perform video tracking, DeepLabCut inference, or camera triangulation. Its primary input is a validated wide-table CSV containing 3D coordinates.

## Scientific scope and limitation

Reliable cylinder-coordinate reconstruction requires a fixed reference to the cylinder. Body-point coordinates alone cannot determine the cylinder bottom centre, vertical direction, or in-plane X axis. The software never estimates the cylinder location from the animal's mean position.

Each trial must provide one of the following:

1. Direct metadata containing the bottom centre, a vertical reference, and an in-plane X reference;
2. Fixed environmental markers in the CSV, such as the bottom centre, top centre, and X-axis marker; or
3. At least three non-collinear known perimeter markers plus a non-parallel orientation reference.

If the geometry is incomplete, degenerate, or fails quality control, reconstruction stops with an explanatory error instead of producing a plausible-looking result.

## Current features

- Validates a documented wide-table CSV contract, including units, frame rate, required coordinates, and missing values.
- Reconstructs a right-handed cylinder coordinate system from direct metadata, stationary markers, or perimeter-point fitting.
- Preserves raw input data and writes a separate reconstructed CSV with a transformation audit record.
- Detects invalid geometry, inconsistent units, missing markers, and excessive marker drift.
- Analyses left, right, and bilateral wall-touch events using configurable cylinder geometry and quality rules.
- Exports event tables, frame-level quality records, JSON configuration, Excel, HTML, PDF, publication-oriented figures, and an optional 3D keypoint MP4.
- Provides a four-page PySide6 GUI for import, reconstruction, cylinder analysis, and export.

The default preset is named **Literature-common preset**. It is a transparent starting point, not a universal or international standard; all thresholds must be reviewed for the experimental protocol.

## Quick start

```powershell
git clone https://github.com/xenonstev3-crypto/BehaviorAnalyzer.git
cd BehaviorAnalyzer\Behavior3DAnalyzer
python -m pip install -r requirements.txt
python run_gui.py
```

Use the simulated CSV files in `Behavior3DAnalyzer/sample_data/` before analysing experimental data. In the GUI, choose a new, dedicated result directory for each trial. Outputs are organised as `data/`, `analysis/`, `reports/`, `figures/`, and `video/` and are never written over existing files.

## Input format

The preferred input is one trial per wide-table CSV with at least:

```text
trial_id, animal_id, frame, time_s, fps, coordinate_unit,
{point}_x, {point}_y, {point}_z
```

Optional `{point}_likelihood` and `{point}_error` columns are retained for quality control. Templates and full specifications are available in `Behavior3DAnalyzer/templates/` and `Behavior3DAnalyzer/docs/input_specification.md`.

## Testing

```powershell
cd Behavior3DAnalyzer
python -m unittest discover -s tests -v
```

## Project status

This is an early research-software prototype. The cylinder test is the only implemented experiment module. The plugin structure reserves space for future sticker-test and open-field modules, but they are not implemented yet.

## Documentation

- [Coordinate reconstruction mathematics](Behavior3DAnalyzer/docs/coordinate_reconstruction_math.md)
- [Cylinder analysis rules](Behavior3DAnalyzer/docs/cylinder_analysis_rules.md)
- [Result folder layout](Behavior3DAnalyzer/docs/result_folder_layout.md)
- [GUI usage guide](Behavior3DAnalyzer/docs/stage2_gui_usage.md)

## License

Released under the [MIT License](LICENSE).
