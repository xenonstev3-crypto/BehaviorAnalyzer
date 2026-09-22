# Changelog

All notable changes to this project are documented in this file.

## 0.2.0 - Unreleased

### Added

- Independent Sticker Test workflow with auditable 3D contact-event analysis and cessation candidates.
- Sticker CSV/JSON outputs, 600 dpi PNG/PDF/SVG figures, and a 3D keypoint MP4 export.

### Changed

- The application now starts with an experiment-selection page. Cylinder Test and Sticker Test are peer workflows, each with its own import, coordinate preparation, analysis, and export pages.
- Sticker Test no longer appears as a fifth Cylinder tab and never uses cylinder geometry or inferred cylinder coordinates.

## 0.1.1 - 2026-09-20

### Added

- Public project documentation and an English repository landing page.
- Mouse cylinder-test workflow with coordinate reconstruction, event analysis, quality control, and auditable exports.
- PySide6 desktop workflow for import, reconstruction, analysis, and export.
- Publication-oriented static figures and optional 3D keypoint MP4 export.

### Notes

- This release is an early prototype for research use. It does not include video tracking, DeepLabCut inference, or camera triangulation.
