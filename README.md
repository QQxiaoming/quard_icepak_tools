# Icepak 工具启动器

作者本人只是一个程序员，并不懂流体仿真，但是我老婆是个CFD工程师，因为她工作中经常需要重复性批量处理模型或仿真参数、枚举分析结果，手动修改非常麻烦且易错，所以我就开发了这款自动化工具管理器，将她常用的操作收集为一个个子工具，然后统一在一个界面里管理和运行，里面的任务控制流都是她多年从业的实际经验总结设计的，虽然目前工具数量还不多，但后续会持续增加。这个工具作为送给她的礼物。

这是一个基于 PySide6 的 Classic Icepak （不限于，也可以支持其他Ansys模块）工具管理启动器，用来统一管理和运行一组可扩展的 Icepak 自动化工具。

当前工具以“每个工具一个目录”的方式组织，主界面负责公共配置、自动发现和执行，具体业务逻辑、Tcl 脚本、结果对话框都放在各自工具目录内。

## 当前目录结构

- `quard_icepak_tools.py`：主界面入口。
- `run_quard_icepak_tools.sh`：Linux 下的启动脚本，会激活 `pyside` Conda 环境后启动 GUI。
- `tool_model.py`：工具元数据、参数模型、执行结果模型。
- `tool_registry.py`：公共参数定义与工具自动发现。
- `icepak_runtime.py`：Classic Icepak 工程路径、可执行文件和批处理命令的公共解析逻辑。
- `tool_success_handlers.py`：通用成功提示逻辑。
- `block_dimensions_tool/`：Block 尺寸统计工具。
- `paired_block_stack_tool/`：配对 Hexa Block 厚度调整工具。
- `placeholder_tool/`：新增工具时可参考的模板示例。
- `test/`：示例工程与测试数据。

## 如何启动

Linux 下可直接执行：

```bash
./run_quard_icepak_tools.sh
```

这个脚本当前会执行以下流程：

1. `source ~/miniconda3/bin/activate`
2. `conda activate pyside`
3. 运行 `python quard_icepak_tools.py`

如果你的环境与这里不同，可以按自己的 Python / PySide6 环境调整启动脚本。

## 主界面中的公共配置

以下参数由启动器统一提供，工具本身不需要重复定义：

- `env_script`：Ansys 环境脚本。
- `env_script`：Ansys 环境脚本，可选。
- `input_path`：测试用例路径，可以是 `.wbpj` 或可定位到 `IcepakProj` 的目录。

工具自己的 `ParameterSpec` 只需要描述该工具独有的输入项。

## 当前已实现工具

### 1. Block 尺寸统计工具

目录：`block_dimensions_tool/`

功能：

- 加载 Classic Icepak 工程。
- 枚举各个 `block` 的尺寸与包围盒坐标。
- 在独立结果对话框中显示表格。
- 支持表头排序。
- 支持手动导出 CSV。

### 2. 配对 Hexa Block 厚度调整工具

目录：`paired_block_stack_tool/`

功能：

- 枚举所有 `hexa block`。
- 支持设置厚度堆叠方向：`x / y / z`，默认 `z`。
- 在预检阶段自动寻找与当前 block 相邻、且截面范围完全一致的配对 block。
- 若预检成功，会在表格中把配对行高亮显示。
- 支持沿厚度方向正向或反向调整厚度，并让配对 block 反向变化。
- 调整后保持两个 block 仍然相邻，且总厚度不变。

约束：

- 当前仅支持 `hexa` 形体。
- 如果没有唯一相邻配对对象，或截面范围不一致，会直接报错，不允许调整。

### 3. 模板工具示例

目录：`placeholder_tool/`

作用：

- 演示如何增加一个新工具。
- 演示如何定义工具专用参数。
- 演示如何配置工具自己的执行逻辑与成功反馈。

## 工具自动发现约定

每个工具必须放在一个以 `_tool` 结尾的目录中。

每个工具目录至少应包含：

- `__init__.py`
- `manifest.py`
- 一个或多个实现文件，例如 `tool.py`
- 该工具使用的 Tcl 脚本

主程序会自动扫描工作区根目录下所有匹配 `*_tool` 的目录，并导入 `<tool_dir>.manifest`。

`manifest.py` 必须暴露名为 `TOOL_SPEC` 的顶层变量。

## 新增工具的最小模板

目录示例：

```text
my_new_tool/
  __init__.py
  manifest.py
  tool.py
  my_script.tcl
```

`__init__.py` 示例：

```python
from .manifest import TOOL_SPEC
```

`manifest.py` 示例：

```python
from tool_model import ParameterSpec, ToolSpec

from .tool import DEFAULT_TCL_SCRIPT, run_my_tool


TOOL_SPEC = ToolSpec(
    key="my_new_tool",
    name="我的新工具",
    description="描述这个工具的用途。",
    run_button_text="运行工具",
    parameters=(
        ParameterSpec(
            key="output_path",
            label="输出文件",
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

`tool.py` 示例：

```python
from pathlib import Path

from tool_model import ToolExecutionResult


DEFAULT_TCL_SCRIPT = Path(__file__).resolve().with_name("my_script.tcl")


def run_my_tool(parameters: dict[str, str], log=None) -> ToolExecutionResult:
    logger = log or print
    logger(f"运行参数：{parameters}")
    return ToolExecutionResult(exit_code=0)
```

## 开发建议

- 如果 Tcl 脚本不希望在主界面暴露，放到 `internal_parameters` 中。
- 尽量把工具逻辑、结果对话框和 Tcl 脚本都放在同一个工具目录中，保持工具自包含。
- 主界面应尽量保持通用，不在主界面中写工具专用分支。
- 如果工具需要展示结果弹窗，优先在工具目录内实现自己的成功处理逻辑。

## GitHub Actions 打包 Windows EXE

仓库已包含用于 Windows 分发的 GitHub Actions 工作流：

- 工作流文件：`.github/workflows/build-windows-exe.yml`
- PyInstaller 配置：`quard_icepak_tools.spec`

触发方式：

```text
1. 在 GitHub Actions 页面手动运行 Build Windows EXE
2. 或推送形如 v1.0.0 的 tag 自动触发
```

工作流会在 `windows-latest` 环境中：

1. 安装 Python 3.11
2. 安装 `PyInstaller` 和 `PySide6`
3. 构建 `dist/quard_icepak_tools.exe`
4. 上传构建产物 `quard_icepak_tools-windows`

这个 spec 会额外收集：

- 所有 `*_tool` 动态导入模块
- 每个工具目录内的 `.tcl` 脚本文件

这样可以避免因为 PyInstaller 静态分析不到动态发现逻辑而漏打包。