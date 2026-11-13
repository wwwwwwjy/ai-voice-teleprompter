#!/bin/bash
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$CURRENT_DIR"

# 激活虚拟环境
source venv312/bin/activate

# 全部输出到 Mac 本地 /tmp，避免覆盖 dist/win 等其他平台产物
rm -rf /tmp/ai_prompter_pyinstaller_work /tmp/ai_prompter_pyinstaller_dist

pyinstaller --clean \
  --workpath=/tmp/ai_prompter_pyinstaller_work \
  --distpath=/tmp/ai_prompter_pyinstaller_dist \
  AI语音提词器.spec

# 只更新 macOS 产物，保留 Windows 便携版
mkdir -p "$CURRENT_DIR/dist"
rm -rf "$CURRENT_DIR/dist/AI语音提词器" "$CURRENT_DIR/dist/AI语音提词器.app"
cp -R /tmp/ai_prompter_pyinstaller_dist/AI语音提词器 "$CURRENT_DIR/dist/AI语音提词器"
cp -R /tmp/ai_prompter_pyinstaller_dist/AI语音提词器.app "$CURRENT_DIR/dist/AI语音提词器.app"

echo "✅ 打包完成: $CURRENT_DIR/dist/AI语音提词器.app"
open "$CURRENT_DIR/dist/AI语音提词器.app"
