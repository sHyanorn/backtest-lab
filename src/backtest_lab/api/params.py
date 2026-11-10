"""Strategy parameters checked against the strategy dataclass fields before any work."""

import dataclasses
import math
from collections.abc import Iterable, Mapping
from typing import Literal

from backtest_lab.strategies import STRATEGIES, Strategy
from backtest_lab.strategies.base import CATEGORICAL, SYMBOL
from backtest_lab.validation.search import Param, Params

type TypeName = Literal["str", "int", "float", "bool"]
type SymbolKind = Literal["ticker", "series"]
_TYPE_NAMES: dict[type, TypeName] = {str: "str", int: "int", float: "float", bool: "bool"}
# Numbers outside this range are rejected: no strategy needs them, and huge values
# overflow in pandas or in float conversion (D016).
NUMBER_LIMIT = 1_000_000


class ParamError(ValueError):
    """A request names an unknown strategy or parameter, or gives an invalid value."""


@dataclasses.dataclass(frozen=True)
class ParamSpec:
    name: str
    type: TypeName
    default: Param
    symbol: SymbolKind | None  # what a string parameter names
    categorical: bool  # a number whose order means nothing (D019)


def specs(strategy: str) -> list[ParamSpec]:
    if strategy not in STRATEGIES:
        raise ParamError(f"unknown strategy {strategy!r}; choose from {sorted(STRATEGIES)}")
    cls = STRATEGIES[strategy]
    assert dataclasses.is_dataclass(cls)
    return [
        ParamSpec(
            f.name,
            _TYPE_NAMES[f.type],
            f.default,
            f.metadata.get(SYMBOL),
            f.metadata.get(CATEGORICAL, False),
        )
        for f in dataclasses.fields(cls)
    ]


def check_value(spec: ParamSpec, value: Param) -> Param:
    """Return `value` if it has the field's type; an int is accepted for a float."""
    ok = {
        "str": isinstance(value, str),
        "bool": isinstance(value, bool),
        "int": isinstance(value, int) and not isinstance(value, bool),
        "float": isinstance(value, int | float) and not isinstance(value, bool),
    }[spec.type]
    if not ok or (isinstance(value, float) and not math.isfinite(value)):
        raise ParamError(f"parameter {spec.name!r} must be {spec.type}, got {value!r}")
    if spec.type in ("int", "float") and abs(value) > NUMBER_LIMIT:  # type: ignore[arg-type]
        raise ParamError(f"parameter {spec.name!r} must be within +/-{NUMBER_LIMIT}")
    return float(value) if spec.type == "float" else value


def check_params(strategy: str, params: Mapping[str, Param]) -> Params:
    by_name = {s.name: s for s in specs(strategy)}
    unknown = set(params) - set(by_name)
    if unknown:
        raise ParamError(f"{strategy} has no parameter {sorted(unknown)}; it takes {list(by_name)}")
    return {name: check_value(by_name[name], value) for name, value in params.items()}


def build(strategy: str, params: Params) -> Strategy:
    """The strategy instance; its own range checks raise ParamError."""
    try:
        return STRATEGIES[strategy](**params)
    except ValueError as exc:
        raise ParamError(f"{strategy} {params}: {exc}") from exc


def symbols(strategy: str, params: Iterable[Params], kind: SymbolKind) -> set[str]:
    """Tickers or macro series named by the parameters of that kind, defaults included."""
    named = [s for s in specs(strategy) if s.symbol == kind]
    return {str(p.get(s.name, s.default)) for p in params for s in named}
