我们的项目需要同时能在 Windows 和 Linux 上运行，所以请确保你的代码兼顾平台差异。

如果当前在linux上开发环境设置请参考以下步骤，先设置好环境：
source ~/miniconda3/bin/activate
conda activate pyside

我们的项目通过github actions进行持续集成测试，主要是为window平台用户打包成exe分发，任何修改要保证不会让打包失效。

如需访问icepak工具请先配置环境：
source /home/qqm/ansys-v221-env.sh