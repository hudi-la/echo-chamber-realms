#!/bin/zsh
# Local visual sample only: no model, microphone or puppet hardware.
preview_root="${0:A:h:h}"
preview_python="$HOME/.cache/echo-chamber/venv/bin/python"
if [[ ! -x "$preview_python" ]]; then preview_python=python3; fi
"$preview_python" "$preview_root/scripts/build_thought_preview.py" || exit 1
print '展厅预览：http://127.0.0.1:8878/#exhibition'
print '保持此窗口打开；按 Ctrl-C 停止。若提示端口已使用，直接打开上述地址。'
"$preview_python" -m http.server 8878 --bind 127.0.0.1 --directory "$preview_root/artifacts/thought-field-preview"
