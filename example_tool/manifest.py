from tool_model import ParameterSpec, ToolSpec
from tool_success_handlers import show_default_success_message

from .tool import DEFAULT_TCL_SCRIPT, run_example_tool
from .tool_version import TOOL_VERSION

TOOL_SPEC = ToolSpec(
    key="example_template",
    name="示例工具",
    version=TOOL_VERSION,
    description=(
        "这是一个尽量简单的示例工具。"
        "它只收集少量参数，用来演示如何新增工具。"
    ),
    run_button_text="运行示例工具",
    parameters=(
        ParameterSpec(
            key="tool_name",
            label="示例名称",
            browse_mode="none",
            required=True,
            default_value="demo_example_tool",
            example_hint="这个字段仅用于演示如何为工具定义额外的专用输入。",
        ),
        ParameterSpec(
            key="note",
            label="示例备注",
            browse_mode="none",
            required=False,
            default_value="Use this entry as a simple reference when adding the next real tool.",
            example_hint="这个字段属于示例内容，真实工具通常可以更精简。",
        ),
    ),
    executor=run_example_tool,
    internal_parameters={"tcl_script": str(DEFAULT_TCL_SCRIPT)},
    success_handler=show_default_success_message,
)