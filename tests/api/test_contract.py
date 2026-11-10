"""The dashboard's hand-written API types (web/src/sweep) against the models they mirror."""

import re
from pathlib import Path
from typing import get_args

from pydantic import BaseModel

from backtest_lab.api import main, schemas
from backtest_lab.api.params import SymbolKind, TypeName

WEB = Path(__file__).parents[2] / "web" / "src" / "sweep"
API_TS = (WEB / "api.ts").read_text(encoding="utf-8")


def ts_fields(interface: str) -> dict[str, str]:
    """Name and declared type of each field of an interface in api.ts."""
    match = re.search(rf"export interface {interface} \{{\n(.*?)\n\}}", API_TS, re.DOTALL)
    assert match, interface
    return dict(re.findall(r"^  (\w+)\??: (.+)$", match.group(1), re.MULTILINE))


def literals(ts_type: str) -> set[str]:
    return set(re.findall(r"'(\w+)'", ts_type))


def required(model: type[BaseModel]) -> set[str]:
    return {name for name, field in model.model_fields.items() if field.is_required()}


def test_sweep_request_sends_only_fields_the_api_accepts() -> None:
    # Requests reject unknown fields, so a renamed field would be a 422 for every sweep.
    sent = ts_fields("SweepRequest")
    assert required(schemas.SweepRequest) <= set(sent) <= set(schemas.SweepRequest.model_fields)
    assert set(re.findall(r"(\w+): number", sent["costs"])) == set(schemas.CostsIn.model_fields)


def test_response_types_read_only_fields_the_api_returns() -> None:
    status = ts_fields("SweepStatus")
    assert set(status) <= set(schemas.SweepStatus.model_fields)
    annotation = schemas.SweepStatus.model_fields["status"].annotation
    assert literals(status["status"]) == set(get_args(annotation))
    assert set(ts_fields("StrategyInfo")) == set(schemas.StrategyInfo.model_fields)
    param = ts_fields("ParamInfo")
    assert set(param) == set(schemas.ParamInfo.model_fields)
    assert literals(param["type"]) == set(get_args(TypeName.__value__))
    assert literals(param["symbol"]) == set(get_args(SymbolKind.__value__))


def test_the_form_and_the_api_share_the_trial_limit() -> None:
    form = (WEB / "form.ts").read_text(encoding="utf-8")
    assert f"export const MAX_TRIALS = {main.MAX_TRIALS} " in form
