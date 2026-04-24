# Icepak Tool Launcher

This workspace provides a PySide6 launcher for Classic Icepak automation tools.

## Layout

- `icepak_csv_gui.py`: GUI entry point.
- `icepak_tool_model.py`: shared tool metadata models.
- `icepak_tool_registry.py`: shared settings plus automatic tool discovery.
- `block_dimensions_tool/`: real CSV export tool.
- `placeholder_tool/`: minimal example tool for future extensions.

## Tool Discovery Contract

Each tool must live in its own directory whose name ends with `_tool`.

Each tool directory must include:

- `__init__.py`
- `manifest.py`
- one or more implementation files such as `tool.py`
- any colocated Tcl scripts used by that tool

The launcher automatically scans the workspace root for directories matching `*_tool` and imports `<tool_dir>.manifest`.

`manifest.py` must expose a top-level variable named `TOOL_SPEC`.

## Minimal Tool Template

Directory example:

```text
my_new_tool/
  __init__.py
  manifest.py
  tool.py
  my_script.tcl
```

Example `__init__.py`:

```python
from .manifest import TOOL_SPEC
```

Example `manifest.py`:

```python
from icepak_tool_model import ParameterSpec, ToolSpec

from .tool import DEFAULT_TCL_SCRIPT, run_my_tool


TOOL_SPEC = ToolSpec(
    key="my_new_tool",
    name="My New Tool",
    description="Describe what the tool does.",
    run_button_text="Run My Tool",
    parameters=(
        ParameterSpec(
            key="output_path",
            label="Output File",
            browse_mode="save_file",
            required=True,
            file_filter="All Files (*)",
            default_output_name="my_tool_output.txt",
        ),
    ),
    executor=run_my_tool,
    internal_parameters={"tcl_script": str(DEFAULT_TCL_SCRIPT)},
)
```

Example `tool.py`:

```python
from pathlib import Path

DEFAULT_TCL_SCRIPT = Path(__file__).resolve().with_name("my_script.tcl")


def run_my_tool(parameters: dict[str, str], log=None) -> int:
    logger = log or print
    logger(f"Running with {parameters['output_path']}")
    return 0
```

## Shared Settings

These settings are provided globally by the launcher and do not need to be redefined in each tool:

- `env_script`
- `input_path`
- `icepak_bin`

Tool-specific `ParameterSpec` entries should only describe inputs unique to that tool.

## Notes

- If a tool needs a Tcl script but users should not edit it, keep it in `internal_parameters`.
- If a parameter is only for demonstration, set `is_example_parameter=True`.
- Keep tool code and Tcl scripts in the same directory so the tool is self-contained.