# Technical Decisions

## D001 Python for the engine, React for the dashboard
- Date: 2026-11-04
- Rationale: Python has a mature data and statistics ecosystem; the dashboard reuses front-end skills

## D002 Precomputed results for the public demo
- Date: 2026-11-04
- Rationale: GitHub Pages is free and stable, and visitors see results as soon as they open the page; avoids exposing a public server to abuse

## D003 Raw data is not committed
- Date: 2026-11-04
- Rationale: Data source terms usually prohibit redistribution; keeps the repository lightweight

## D004 Vectorized engine first
- Date: 2026-11-04
- Rationale: Parameter search needs a large number of backtests, and vectorization is much faster; an event-driven version is an optional point of comparison
