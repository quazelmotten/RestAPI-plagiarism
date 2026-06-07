"""
Global router - composes all domain routers into a single API router.

Each domain (tasks, files, results) owns its own router with its endpoints.
This module simply combines them under the plagiarism prefix.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from assignments.router import (
    router as assignments_router,
)
from assignments.router import (
    subject_router as assignments_subject_router,
)
from auth.blacklist_service import blacklist_service
from auth.router import router as auth_router
from auth.service import AuthService, decode_token
from files.router import router as files_router
from results.router import router as results_router
from storage.router import router as storage_router
from tasks.router import router as tasks_router
from uploads.router import router as uploads_router

router = APIRouter()
logger = logging.getLogger(__name__)

router.include_router(auth_router)
router.include_router(tasks_router)
router.include_router(files_router)
router.include_router(results_router)
router.include_router(uploads_router)
router.include_router(assignments_router)
router.include_router(assignments_subject_router)
router.include_router(storage_router)


async def _authenticate_websocket(token: str, websocket: WebSocket) -> str | None:
    """Validate a WebSocket JWT and return the user_id, or close the socket and return None.

    Performs the same checks as the HTTP `get_current_user` dependency:
      * JWT signature + expiration
      * Token type is ``access``
      * JTI is not on the blacklist
      * Token session_version matches the user's current session_version
      * User actually exists
    """
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return None

    if payload.get("type") != "access":
        await websocket.close(code=4001, reason="Invalid token type")
        return None

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token payload")
        return None

    jti = payload.get("jti")
    if jti and await blacklist_service.is_token_blacklisted(jti):
        await websocket.close(code=4001, reason="Token revoked")
        return None

    user = await AuthService.get_user_by_id(user_id)
    if not user:
        await websocket.close(code=4001, reason="User not found")
        return None

    token_session_version = payload.get("sv", 0)
    if token_session_version < user.session_version:
        await websocket.close(code=4001, reason="Token superseded")
        return None

    return user_id


@router.websocket("/plagiarism/ws/tasks/{task_id}")
async def websocket_task_progress(
    websocket: WebSocket,
    task_id: str,
    token: str = Query(..., description="JWT access token for authentication"),
):
    """
    WebSocket endpoint for real-time task progress updates.

    Requires authentication via token query parameter.

    Connects to a specific task and receives progress events:
    - type: "progress"
    - task_id: string
    - status: string
    - processed_pairs: int
    - total_pairs: int
    - progress: float (0-1)
    - timestamp: float

    Clients should send periodic pings to keep connection alive.
    Connection auto-closes when task completes or on error.
    """
    user_id = await _authenticate_websocket(token, websocket)
    if user_id is None:
        return

    logger.info("WebSocket authenticated connection for task %s by user %s", task_id, user_id)

    manager = websocket.app.state.ws_manager
    await manager.connect(websocket, task_id)

    if websocket.client_state.name != "CONNECTED":
        return

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                logger.debug("Received WebSocket message for task %s: %s", task_id, data[:100])
            except TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning("WebSocket error for task %s: %s", task_id, e)
                break
    except Exception as e:
        logger.info("WebSocket connection ended for task %s: %s", task_id, e)
    finally:
        manager.disconnect(websocket, task_id)
