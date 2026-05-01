#!/bin/bash
# LinkedIn 智能投递助手 — 一键安装脚本
set -e

echo "=== LinkedIn 智能投递助手 安装向导 ==="
echo ""

# 1. Install Python dependencies
echo "[1/4] 安装 Python 依赖..."
cd "$(dirname "$0")/../backend"
pip install -e .[dev]
echo "✓ Python 依赖安装完成"
echo ""

# 2. Install Playwright browsers
echo "[2/4] 安装 Playwright 浏览器（Chromium）..."
playwright install chromium
echo "✓ 浏览器安装完成"
echo ""

# 3. Create data directories
echo "[3/4] 创建数据目录..."
mkdir -p data/db data/resumes data/config
echo "✓ 数据目录已就绪"
echo ""

# 4. Print API key
echo "[4/4] 获取 API Key..."
API_KEY_FILE="data/config/api_key.txt"
if [ -f "$API_KEY_FILE" ]; then
    API_KEY=$(cat "$API_KEY_FILE")
    echo "✓ API Key: $API_KEY"
else
    echo "  （首次启动后端时自动生成，请运行后端后查看）"
fi
echo ""

echo "=== 安装完成！==="
echo ""
echo "启动步骤："
echo "  1. 启动后端： cd backend && python -m uvicorn app.main:app --reload --port 8899"
echo "  2. 启动 Chrome： bash scripts/start-chrome-debug.sh"
echo "  3. 加载扩展： Chrome → chrome://extensions → 开发者模式 → 加载已解压的扩展 → 选择 chrome-extension 目录"
echo "  4. 在扩展设置页填入 API Key"
echo "  5. 配置表单答案（个人信息）和筛选条件"
echo "  6. 点击扩展弹窗 → 开始自动投递"
