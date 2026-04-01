"""
TradeSnake API 主入口
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from api.routes import router
from api.limits import limiter

app = FastAPI(
    title="TradeSnake API",
    description="股市贪吃蛇 - 战力值计算API",
    version="0.1.0"
)

# 添加速率限制
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS配置 - 从环境变量读取，允许配置多个来源
def get_cors_origins():
    """获取CORS允许的来源列表"""
    env_origins = os.environ.get("CORS_ORIGINS", "")
    if env_origins:
        return [origin.strip() for origin in env_origins.split(",") if origin.strip()]
    # 默认允许本地开发
    return ["http://localhost:5173", "http://localhost:5174"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


@app.get("/")
async def root():
    return {
        "name": "TradeSnake API",
        "version": "0.1.0",
        "description": "股市贪吃蛇 - 战力值计算API"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
