"""
TradeSnake API 主入口
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
