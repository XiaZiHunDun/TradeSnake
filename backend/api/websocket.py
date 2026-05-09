"""
WebSocket管理器 - TradeSnake v18.x

功能：
- WebSocket连接管理
- 实时预警推送
- 心跳检测
"""

# asyncio imported for type hints only
import json
from typing import List, Dict
from fastapi import WebSocket


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"WebSocket客户端连接，当前在线: {len(self.active_connections)}")

        # 发送欢迎消息
        await websocket.send_json({
            "type": "connected",
            "message": "已连接到预警推送服务",
            "online_count": len(self.active_connections)
        })

    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"WebSocket客户端断开，当前在线: {len(self.active_connections)}")

    async def broadcast(self, message: Dict):
        """广播消息到所有连接的客户端"""
        if not self.active_connections:
            return

        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"WebSocket发送失败: {e}")
                disconnected.append(connection)

        # 清理断开的连接
        for conn in disconnected:
            self.disconnect(conn)

    async def send_alert(self, alert: Dict):
        """发送预警到所有客户端"""
        await self.broadcast({
            "type": "alert",
            "data": alert
        })

    async def send_personal_message(self, websocket: WebSocket, message: Dict):
        """发送消息到特定客户端"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"WebSocket发送失败: {e}")

    def get_online_count(self) -> int:
        """获取在线连接数"""
        return len(self.active_connections)


# 全局WebSocket管理器
_ws_manager = None


def get_ws_manager() -> WebSocketManager:
    """获取WebSocket管理器单例"""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager


async def broadcast_alert(alert: Dict):
    """广播预警（供其他模块调用）"""
    manager = get_ws_manager()
    await manager.send_alert(alert)
