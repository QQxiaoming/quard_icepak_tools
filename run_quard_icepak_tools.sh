#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"

source ~/miniconda3/bin/activate
conda activate pyside

cd "$script_dir"
exec python quard_icepak_tools.py