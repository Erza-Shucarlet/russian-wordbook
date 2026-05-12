#!/usr/bin/env python3
"""
小陈陈的俄语单词本 — PyInstaller 打包脚本
运行: python3 build.py
输出: dist/小陈陈的俄语单词本.app （可压缩发给别人，双击即用）
"""

import subprocess
import sys
import os
import venv

os.chdir(os.path.dirname(os.path.abspath(__file__)))

VENV_DIR = '.build_venv'

# 1. 创建打包用的虚拟环境
if not os.path.exists(VENV_DIR):
    print("📦 创建构建虚拟环境...")
    venv.create(VENV_DIR, with_pip=True)

# venv 中的 python 和 pip 路径
if sys.platform == 'win32':
    py = os.path.join(VENV_DIR, 'Scripts', 'python.exe')
else:
    py = os.path.join(VENV_DIR, 'bin', 'python')

# 2. 安装依赖
print("📦 安装构建依赖...")
subprocess.run([py, '-m', 'pip', 'install', '-q', 'pyinstaller', 'flask', 'requests'], check=True)

# 3. 清理旧构建
subprocess.run(['rm', '-rf', 'build', 'dist'], check=False)

# 4. 打包
print("🔨 开始打包 (约 1-2 分钟)...")
cmd = [
    py, '-m', 'PyInstaller',
    '--name', '小陈陈的俄语单词本',
    '--add-data', f'static:static',
    '--onedir',
    '--windowed',
    '--noconfirm',
    'app.py',
    '--exclude-module', 'tkinter',
]
subprocess.run(cmd, check=True)

# 5. 清理构建临时文件
subprocess.run(['rm', '-rf', 'build'], check=False)
print()
print("=" * 50)
print("✅ 打包完成！")
print(f"   App: {os.path.abspath('dist/小陈陈的俄语单词本.app')}")
print()
print("📤 发送给别人：")
print("   1. 右键 dist/小陈陈的俄语单词本.app → 压缩")
print("   2. 对方解压后双击 .app 即可使用")
print("   3. 首次启动自动在 ~/.russian-wordbook/ 创建数据库")
print("=" * 50)
