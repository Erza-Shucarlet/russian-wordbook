#!/bin/bash
# ============================================
#  小陈陈的俄语单词本 — 双击启动脚本
#  双击此文件即可启动服务并打开浏览器
# ============================================

cd "$(dirname "$0")"

echo "📖 小陈陈的俄语单词本"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 检查 Python
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "❌ 未找到 Python，请先安装 Python 3"
    echo "   下载地址: https://www.python.org/downloads/"
    read -p "按回车键退出..."
    exit 1
fi

echo "✅ Python: $($PYTHON --version)"

# 安装依赖
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    $PYTHON -m venv venv
fi

source venv/bin/activate

echo "📦 检查依赖..."
pip install -q -r requirements.txt

# 检查端口是否被占用
if lsof -i :8910 &> /dev/null; then
    echo "⚠️  端口 8910 已被占用，尝试关闭旧进程..."
    lsof -ti :8910 | xargs kill -9 2>/dev/null
    sleep 1
fi

echo "🚀 启动服务..."
echo "   浏览器将自动打开 http://127.0.0.1:8910"
echo "   按 Ctrl+C 停止服务"
echo ""

# 后台启动 Flask，然后打开浏览器
python app.py &
APP_PID=$!

sleep 2

# 打开浏览器
open http://127.0.0.1:8910

# 等待 Flask 进程
wait $APP_PID
