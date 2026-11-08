"""Execute notebooks/demo.ipynb and save its outputs, or check that they are current.

Run from the repository root:

    uv sync --group notebook
    uv run python notebooks/run.py           # execute and save
    uv run python notebooks/run.py --check   # execute and compare with the saved outputs

Only the outputs are compared, not execution counts or metadata, so a check does not
depend on the platform or the kernel version.
"""

import argparse
import copy
import sys
from pathlib import Path
from typing import Any

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "notebooks" / "demo.ipynb"
# Output fields that vary between runs or platforms
VOLATILE = ("execution_count", "metadata")


def outputs(nb: Any) -> list[list[dict[str, Any]]]:
    """The outputs of every code cell, without volatile fields."""
    return [
        [{k: v for k, v in out.items() if k not in VOLATILE} for out in cell.outputs]
        for cell in nb.cells
        if cell.cell_type == "code"
    ]


def execute(nb: Any) -> Any:
    executed = copy.deepcopy(nb)
    client = NotebookClient(
        executed,
        timeout=300,
        kernel_name="python3",
        record_timing=False,
        resources={"metadata": {"path": str(ROOT)}},
    )
    client.execute()
    # Keep the saved file free of environment details.
    executed.metadata.pop("language_info", None)
    executed.metadata.pop("widgets", None)
    return executed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if the outputs changed")
    args = parser.parse_args(argv)
    saved = nbformat.read(NOTEBOOK, as_version=4)  # type: ignore[no-untyped-call]
    executed = execute(saved)
    if args.check:
        if outputs(executed) != outputs(saved):
            print(f"{NOTEBOOK.name}: outputs differ; run python notebooks/run.py", file=sys.stderr)
            return 1
        print(f"{NOTEBOOK.name}: outputs are current")
        return 0
    nbformat.write(executed, NOTEBOOK)  # type: ignore[no-untyped-call]
    print(f"wrote {NOTEBOOK.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
