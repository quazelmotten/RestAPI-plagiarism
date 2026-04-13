"""
Global router - composes all domain routers into a single API router.

Each domain (tasks, files, results) owns its own router with its endpoints.
This module simply combines them under the plagiarism prefix.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)


# Import and include domain routers
from assignments.router import (
    router as assignments_router,
    subject_router as assignments_subject_router,
)  # noqa: E402
from auth.router import router as auth_router
from files.router import router as files_router
from results.router import router as results_router
from tasks.router import router as tasks_router

router.include_router(auth_router)
router.include_router(tasks_router)
router.include_router(files_router)
router.include_router(results_router)
router.include_router(assignments_router)
router.include_router(assignments_subject_router)


# WebSocket endpoint lives at the global level since it crosses domains
@router.websocket("/plagiarism/ws/tasks/{task_id}")
async def websocket_task_progress(
    websocket: WebSocket,
    task_id: str,
):
    """
    WebSocket endpoint for real-time task progress updates.

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
    logger.info("WebSocket connection attempt for task %s", task_id)

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
