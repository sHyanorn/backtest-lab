# CLAUDE.md

This repository is a backtesting platform built to test whether a strategy is overfit. Its focus is statistical rigor, not returns.

## Read before starting

1. `docs/SPEC.md`
2. `docs/TASKS.md`: start from the first unchecked milestone
3. `docs/DECISIONS.md`
4. `docs/METHODS.md`: formulas and references for each statistical method; implementations must match it

## Directory structure

```
src/backtest_lab/
  data/        Data fetching, cleaning, storage
  engine/      Backtest engine
  strategies/  Example strategies
  validation/  Anti-overfitting methods
  api/         FastAPI service
tests/
web/           React + TypeScript dashboard
notebooks/     Demo Jupyter notebooks
```

## Working practices

- Write a plan before starting each milestone
- One commit per task, using Conventional Commits in English
- Check off tasks when done; record new decisions in DECISIONS.md
- Before implementing a statistical method, write its formula, intuition and source paper in METHODS.md
- Everything committed to GitHub (code, comments, docs, commit messages) is in English and concise: say what changed and why, not the step-by-step process. Commit messages use Conventional Commits with a short subject and at most a brief body.

## Common commands

```bash
uv sync
uv run pytest
uv run ruff check . && uv run mypy src
uv run python -m backtest_lab.data.update     # Update data
uv run uvicorn backtest_lab.api.main:app --host 127.0.0.1 --reload
cd web && npm run dev
```

## Hard rules

- No look-ahead bias: signals are generated after the close on day t and fill no earlier than day t+1. The engine enforces this, with dedicated tests
- Fix the random seed for every random process
- Statistical methods must have unit tests, validated against numerical examples from the papers or known results
- Transaction costs and slippage are on by default; zero-cost results must never be presented as the main conclusion
- Do not commit raw market data, only the fetch scripts; precomputed results for the demo may be committed
- Functions must have type annotations and pass mypy strict mode
