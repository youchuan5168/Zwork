# Zwork

Zwork 是个人求职工作台，用于管理投递进度、面试安排、简历和岗位资料。前端支持电脑与手机浏览器，业务数据保存在 MySQL 中。

## 主要功能

- **投递管理**：记录投递、跟进阶段、公司和后续安排，查看总览与统计。
- **简历中心**：管理简历版本、岗位说明和项目材料；对照岗位要求分析简历，并维护求职档案。
- **平台招聘**：打开招聘平台官网投递，也可粘贴岗位说明进入简历分析。
- **面试复盘**：记录面试经过和题目，按岗位整理回答。
- **Zwork 助手**：提供简报、面试准备、投递跟进等建议；涉及业务修改时需要用户确认。使用前须配置模型。

## 代码结构

```text
Zwork/
├─ start.py                 本地启动入口
├─ backend/
│  ├─ app/
│  │  ├─ routers/           HTTP 接口
│  │  ├─ services/          业务逻辑
│  │  ├─ repositories/      数据访问
│  │  ├─ agents/            助手运行、工具与模型适配
│  │  ├─ core/              配置、认证与中间件
│  │  ├─ db/                数据库连接
│  │  ├─ integrations/      外部服务集成
│  │  ├─ models.py          数据模型
│  │  └─ factory.py         FastAPI 应用装配
│  ├─ migrations/           Alembic 数据库迁移
│  └─ scripts/              运维与验证脚本
├─ frontend/
│  └─ src/
│     ├─ views/             页面
│     ├─ components/        通用组件
│     ├─ api/               后端接口调用
│     ├─ router/            页面路由
│     └─ stores/            前端状态
```

## 环境要求

- Python 3.12
- Node.js 18+
- MySQL 8+

## 本地运行

以下命令从项目根目录执行。

1. 安装后端依赖：

   ```powershell
   cd backend
   python -m pip install -r requirements.txt
   cd ..
   ```

2. 复制配置文件，填写 MySQL 连接信息，并将 `JWT_SECRET` 改为至少 32 位的随机密钥：

   ```powershell
   Copy-Item backend/.env.example backend/.env
   ```

   可用 `python -c "import secrets; print(secrets.token_urlsafe(48))"` 生成密钥。不要提交 `backend/.env`。
3. 构建前端：

   ```powershell
   cd frontend
   npm ci
   npm run build
   cd ..
   ```

4. 启动服务：

   ```powershell
   python start.py
   ```

   浏览器访问 [http://localhost:8000](http://localhost:8000)。首次运行可注册第一个账号；之后默认关闭注册。按 `Ctrl+C` 停止服务。

开发前端时，可在两个终端分别运行 `cd backend; python -m uvicorn app.main:app --reload --port 8000` 和 `cd frontend; npm run dev`，然后访问 [http://localhost:5173](http://localhost:5173)。

## 更新已有数据库

升级旧版本前先完成数据库备份，再在 `backend` 目录执行：

```powershell
python -m alembic upgrade head
```

旧数据库的首次迁移可能需要额外核对与标记步骤。设置页导出的 JSON 只包含部分业务记录；完整备份应包含 MySQL 数据库。

## 开发与文档

后端静态检查在 `backend` 目录运行：

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check app migrations
```

前端构建在 `frontend` 目录运行：`npm run build`。开发环境启动后，可访问 [API 文档](http://localhost:8000/docs)。

## 提交到 GitHub

当前目录首次提交时，先在 GitHub 创建一个**空仓库**（不要勾选自动生成 README、`.gitignore` 或许可证），然后在项目根目录执行：

```powershell
git init -b main
git add .
git status --short
git commit -m "Initial commit"
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

推送前核对 `git status --short`：`backend/.env`、`backups/`、`node_modules/`、`backend/.venv/` 和 `frontend/dist/` 都不应出现在待提交列表中。GitHub 认证按提示使用浏览器登录或凭据管理器，不要将令牌写进仓库。之后更新代码时，在根目录执行 `git add .`、`git commit -m "描述本次修改"`、`git push`。
