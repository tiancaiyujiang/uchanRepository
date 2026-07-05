"""PyInstaller 打包脚本。"""
import os
import shutil
import sys

import PyInstaller.__main__


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(root, "dist")
    build_dir = os.path.join(root, "build")

    # 清理旧构建
    for d in (dist_dir, build_dir):
        if os.path.exists(d):
            shutil.rmtree(d)

    args = [
        os.path.join(root, "main.py"),
        "--name", "CobolGenerater",
        "--onefile",
        "--windowed",
        "--add-data", f"{os.path.join(root, 'templates')}{os.pathsep}templates",
        "--icon", "NONE",
        "--distpath", dist_dir,
        "--workpath", build_dir,
        "--specpath", root,
    ]

    PyInstaller.__main__.run(args)
    print(f"\n打包完成，可执行文件位于：{os.path.join(dist_dir, 'CobolGenerater.exe')}")


if __name__ == "__main__":
    main()
