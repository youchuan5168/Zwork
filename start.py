# -*- coding: utf-8 -*-
"""Zwork - 一键启动脚本。

用法：在 backend 目录任意位置执行  python start.py
说明：以当前 Python 解释器启动 uvicorn，监听 0.0.0.0:8000，
      本机与同一 WiFi 下的手机均可访问。
"""
import os
import socket
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
os.chdir(BACKEND_DIR)  # 确保能导入 app 包、读取 .env 配置
sys.path.insert(0, BACKEND_DIR)


def lan_ip() -> str | None:
    """获取本机局域网 IP（用于手机访问提示），失败返回 None。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def main() -> None:
    try:
        ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        print("启动失败：当前 Python 缺少 IANA 时区数据，请安装后重新启动：")
        print(f'  "{sys.executable}" -m pip install tzdata')
        raise SystemExit(1) from None

    ip = lan_ip()
    print("=" * 56)
    print("  Zwork - 启动中...")
    print("=" * 56)
    print("  本机访问:   http://localhost:8000")
    if ip:
        print(f"  手机访问:   http://{ip}:8000  (手机需连接同一 WiFi)")
    print("  接口文档:   http://localhost:8000/docs")
    print("  按 Ctrl+C 停止服务")
    print("=" * 56)
    print()

    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
