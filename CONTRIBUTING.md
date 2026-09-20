# Contributing

Thank you for improving Behavior3D Analyzer.

## Before opening a pull request

1. Keep the raw-input safety rule intact: source CSV files must never be overwritten.
2. Keep cylinder-specific rules inside `Behavior3DAnalyzer/experiments/cylinder/`, not in `core/`.
3. Add or update unit tests for behavioural logic and coordinate geometry.
4. Run the test suite from `Behavior3DAnalyzer/`:

   ```powershell
   python -m unittest discover -s tests -v
   ```

5. Do not commit real animal data, participant information, model weights, generated videos, or large analysis outputs.

## Design principles

- Do not infer environmental geometry from animal body positions.
- Prefer explanatory errors over silent fallback behaviour.
- Keep presets versioned and transparent; no single threshold set should be presented as a universal standard.
- Preserve auditability by saving configuration, transformations, quality control, and event-level outputs.
