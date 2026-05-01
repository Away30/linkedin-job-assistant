#!/bin/bash
# 启动带远程调试端口的 Chrome
# 用法: bash scripts/start-chrome-debug.sh
#
# 启动后，LinkedIn 智能投递助手会自动连接到这个 Chrome 实例
# 你只需要在这个 Chrome 中正常登录 LinkedIn 即可

CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# 如果 Chrome 不在默认位置，尝试其他路径
if [ ! -f "$CHROME_PATH" ]; then
    # 尝试通过 mdfind 查找
    CHROME_PATH=$(mdfind "kMDItemFSName == 'Google Chrome'" 2>/dev/null | head -1)
fi

if [ -z "$CHROME_PATH" ] || [ ! -f "$CHROME_PATH" ]; then
    echo "错误：找不到 Google Chrome"
    echo "请确保 Chrome 已安装，或手动运行："
    echo '  /path/to/Google\ Chrome --remote-debugging-port=9222'
    exit 1
fi

echo "正在启动 Chrome（远程调试端口 9222）..."
echo "请在 Chrome 中登录 LinkedIn 后，使用扩展开始自动投递"
echo ""
echo "提示：按 Ctrl+C 不会关闭 Chrome，只会停止调试端口"
echo ""

"$CHROME_PATH" \
    --remote-debugging-port=9222 \
    --user-data-dir="$HOME/.chrome-debug-profile" \
    "$@"
