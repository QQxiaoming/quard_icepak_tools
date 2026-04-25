from tool_model import ParameterSpec, ToolSpec

from .result_dialog import show_paired_block_dz_result
from .tool import DEFAULT_LIST_TCL_SCRIPT, list_block_dimensions


def execute_paired_block_dz(parameters: dict[str, str], log=None):
    return list_block_dimensions(
        input_path=parameters["input_path"],
        icepak_bin=parameters.get("icepak_bin") or None,
        env_script=parameters.get("env_script") or None,
        tcl_script=parameters.get("tcl_script") or None,
        log=log,
    )


TOOL_SPEC = ToolSpec(
    key="paired_block_thickness_adjustment",
    name="配对 Hexa Block 厚度调整工具",
    description=(
        "枚举所有 hexa block，选择一个块后在独立对话框中按厚度堆叠方向的正向或反向调整厚度，"
        "并让相邻且截面范围完全一致的另一个 hexa block 做反向变化。"
    ),
    run_button_text="枚举并调整",
    parameters=(
        ParameterSpec(
            key="stack_axis",
            label="厚度堆叠方向 (x / y / z)",
            browse_mode="none",
            required=False,
            default_value="z",
        ),
    ),
    executor=execute_paired_block_dz,
    internal_parameters={"tcl_script": str(DEFAULT_LIST_TCL_SCRIPT)},
    success_handler=show_paired_block_dz_result,
)