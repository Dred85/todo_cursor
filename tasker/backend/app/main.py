from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.parsing.parser import parse_task_text
from app.schemas.task import CreateTaskRequest, ErrorResponse, TaskResponse, UpdateTaskRequest
from app.services.errors import TaskPermissionError, TaskValidationError
from app.services.tasks import TaskService, TaskSource
from app.storage.sqlite import SqliteTaskRepository, init_sqlite

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    
    app = FastAPI(title="Tasker API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    db_path = os.getenv("TASKER_DB_PATH", "/data/tasker.sqlite3")
    init_sqlite(db_path)
    repo = SqliteTaskRepository(db_path)
    service = TaskService(repo)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.post("/api/task", response_model=TaskResponse, responses={400: {"model": ErrorResponse}})
    def create_task(req: CreateTaskRequest):
        try:
            # По умолчанию используем UTC+3 (Москва), если не указано
            tz = req.timezone or "Europe/Moscow"
            parsed = parse_task_text(req.text, timezone=tz)
            if parsed.parsing_errors:
                error_msg = "\n".join(parsed.parsing_errors)
                logger.warning(f"Parsing error: {error_msg}")
                raise HTTPException(status_code=400, detail=error_msg)

            src = TaskSource.webapp if req.source == "webapp" else TaskSource.telegram_chat
            res = service.create_task(user_id=req.user_id, title=parsed.title, due_at=parsed.due_at, source=src)
            
            return TaskResponse(
                task_id=res.task.id,
                title=res.task.title,
                due_at=res.task.due_at.isoformat() if res.task.due_at else None,
                status=res.task.status,
            )
        except HTTPException:
            raise
        except TaskValidationError as e:
            logger.error(f"Validation error: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except TaskPermissionError as e:
            logger.error(f"Permission error: {e}")
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            logger.exception(f"Unexpected error creating task: {e}")
            raise HTTPException(status_code=500, detail=f"Произошла ошибка: {str(e)}")

    @app.get("/api/tasks")
    def list_tasks(user_id: int, limit: int = 50):
        tasks = repo.list_tasks(user_id=user_id, limit=limit)
        return [
            {
                "task_id": t.id,
                "title": t.title,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "status": t.status,
                "source": t.source,
            }
            for t in tasks
        ]

    @app.put("/api/tasks/{task_id}", response_model=TaskResponse)
    def update_task(task_id: int, user_id: int, req: UpdateTaskRequest):
        try:
            due_at_dt = None
            if req.due_at:
                try:
                    due_at_dt = datetime.fromisoformat(req.due_at.replace("Z", "+00:00"))
                    if due_at_dt.tzinfo is None:
                        due_at_dt = due_at_dt.replace(tzinfo=timezone.utc)
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

            updated = service.update_task(
                task_id=task_id,
                user_id=user_id,
                title=req.title,
                due_at=due_at_dt,
                status=req.status,
            )
            
            return TaskResponse(
                task_id=updated.id,
                title=updated.title,
                due_at=updated.due_at.isoformat() if updated.due_at else None,
                status=updated.status,
            )
        except HTTPException:
            raise
        except TaskValidationError as e:
            logger.error(f"Validation error: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except TaskPermissionError as e:
            logger.error(f"Permission error: {e}")
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            logger.exception(f"Unexpected error updating task: {e}")
            raise HTTPException(status_code=500, detail=f"Произошла ошибка: {str(e)}")

    @app.delete("/api/tasks/{task_id}")
    def delete_task(task_id: int, user_id: int):
        try:
            service.delete_task(task_id=task_id, user_id=user_id)
            return {"ok": True, "message": "Задача удалена"}
        except HTTPException:
            raise
        except TaskPermissionError as e:
            logger.error(f"Permission error: {e}")
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            logger.exception(f"Unexpected error deleting task: {e}")
            raise HTTPException(status_code=500, detail=f"Произошла ошибка: {str(e)}")

    return app

app = create_app()


