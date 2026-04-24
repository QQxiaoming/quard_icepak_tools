from tool_model import ParameterSpec, ToolSpec
from tool_success_handlers import show_default_success_message

from .tool import DEFAULT_TCL_SCRIPT, run_placeholder_tool


TOOL_SPEC = ToolSpec(
    key="placeholder_template",
    name="模板工具示例",
    description=(
        "这是一个用于演示扩展方式的示例工具。"
        "它会收集少量参数并生成一个模板报告文件。"
    ),
    run_button_text="运行模板工具",
    parameters=(
        ParameterSpec(
            key="tool_name",
            label="模板名称",
            browse_mode="none",
            required=True,
            default_value="demo_template_tool",
            is_example_parameter=True,
            example_hint="这个字段仅用于演示如何为工具定义额外的专用输入。",
        ),
        ParameterSpec(
            key="note",
            label="模板备注",
            browse_mode="none",
            required=False,
            default_value="Use this entry as a reference when adding the next real tool.",
            is_example_parameter=True,
            example_hint="这个字段属于模板示例内容，真实工具通常不需要。",
        ),
    ),
    executor=run_placeholder_tool,
    internal_parameters={"tcl_script": str(DEFAULT_TCL_SCRIPT)},
    success_handler=show_default_success_message,
)