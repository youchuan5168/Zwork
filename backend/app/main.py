"""兼容启动命令：uvicorn app.main:app。"""

from app.factory import create_app

app = create_app()
