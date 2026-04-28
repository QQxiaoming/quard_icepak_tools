from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


ToolParameters = dict[str, str]


@dataclass(frozen=True)
class ProgressUpdate:
    mode: str
    value: int = 0
    maximum: int = 100
    message: str = ""


@dataclass(frozen=True)
class TableData:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    default_export_name: str = "export.csv"


@dataclass(frozen=True)
class ToolExecutionResult:
    exit_code: int
    table_data: TableData | None = None
    report_text: str | None = None


ToolProgressCallback = Callable[[ProgressUpdate], None]
ToolExecutor = Callable[
    [ToolParameters, Callable[[str], None] | None, ToolProgressCallback | None],
    ToolExecutionResult,
]
ToolSuccessHandler = Callable[[Any, ToolExecutionResult, ToolParameters], None]


@dataclass(frozen=True)
class ParameterSpec:
    key: str
    label: str
    browse_mode: str
    value_type: str = "text"
    editor_kind: str = "default"
    required: bool = False
    file_filter: str = "All Files (*)"
    default_value: str = ""
    default_output_name: str = ""
    example_hint: str = ""
    choices: tuple[tuple[str, str], ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    single_step: float | None = None
    decimals: int = 6


@dataclass(frozen=True)
class ToolSpec:
    key: str
    name: str
    version: str
    description: str
    run_button_text: str
    parameters: tuple[ParameterSpec, ...]
    executor: ToolExecutor
    internal_parameters: ToolParameters = field(default_factory=dict)
    success_handler: ToolSuccessHandler | None = None
    source_path: str = ""
    is_builtin: bool = True

    @property
    def identifier(self) -> str:
        return f"{self.key}@{self.version}"

    def parameter(self, key: str) -> ParameterSpec | None:
        for parameter in self.parameters:
            if parameter.key == key:
                return parameter
        return None


def build_output_path(input_path: str, output_name: str) -> str:
    candidate = Path(input_path).expanduser()
    base_dir = candidate.parent if candidate.suffix else candidate
    return str(base_dir / output_name)