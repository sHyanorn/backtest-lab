"""Strategy parameters checked against the strategy dataclass fields before any work."""

import dataclasses
import math
from collections.abc import Iterable, Mapping
from typing import Literal

from backtest_lab.strategies import STRATEGIES, Strategy
from backtest_lab.validation.search import Params, ParamValue

type TypeName = Literal["str", "int", "float", "bool"]
_TYPE_NAMES: dict[type, TypeName] = {str: "str", int: "int", float: "float", bool: "bool"}


class ParamError(ValueError):
    """A request names an unknown strategy or parameter, or gives an invalid value."""


@dataclasses.dataclass(frozen=True)
class ParamSpec:
    name: str
    type: TypeName
    default: ParamValue


def specs(strategy: str) -> list[ParamSpec]:
    if strategy not in STRATEGIES:
        raise ParamError(f"unknown strategy {strategy!r}; choose from {sorted(STRATEGIES)}")
    cls = STRATEGIES[strategy]
    assert dataclasses.is_dataclass(cls)
    return [ParamSpec(f.name, _TYPE_NAMES[f.type], f.default) for f in dataclasses.fields(cls)]


def check_value(spec: ParamSpec, value: ParamValue) -> ParamValue:
    """Return `value` if it has the field's type; an int is accepted for a float."""
    ok = {
        "str": isinstance(value, str),
        "bool": isinstance(value, bool),
        "int": isinstance(value, int) and not isinstance(value, bool),
        "float": isinstance(value, int | float) and not isinstance(value, bool),
    }[spec.type]
    if not ok or (isinstance(value, float) and not math.isfinite(value)):
        raise ParamError(f"parameter {spec.name!r} must be {spec.type}, got {value!r}")
    return float(value) if spec.type == "float" else value


def check_params(strategy: str, params: Mapping[str, ParamValue]) -> Params:
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


def symbols(strategy: str, params: Iterable[Params]) -> set[str]:
    """Tickers and macro series named by the string parameters, defaults included."""
    names = [s for s in specs(strategy) if s.type == "str"]
    out: set[str] = set()
    for p in params:
        out.update(str(p.get(s.name, s.default)) for s in names)
    return out
