"""唯一 API 路由装配点；后续 Agent 路由在此注册。"""

from fastapi import APIRouter
from app.routers import applications, auth, companies, schedules, agent, profile, career, settings

api_router = APIRouter()
for router in (auth.router, applications.router, companies.router, schedules.router,
               agent.router, profile.router, career.router, settings.router):
    api_router.include_router(router)
