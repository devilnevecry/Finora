"""Category API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.category_service import CategoryService

router = APIRouter()


def _service(session: AsyncSession = Depends(get_session)) -> CategoryService:
    return CategoryService(session)


@router.get("")
async def list_categories(
    service: CategoryService = Depends(_service),
    type: str | None = None,
    include_archived: bool = False,
):
    categories = await service.list(type=type, include_archived=include_archived)
    return JSONResponse(
        [
            {
                "id": c.id,
                "name": c.name,
                "type": c.type,
                "color": c.color,
                "icon": c.icon,
                "is_archived": c.is_archived,
                "created_at": c.created_at.isoformat(),
            }
            for c in categories
        ]
    )


@router.post("")
async def create_category(
    name: str = Form(...),
    type: str = Form(...),
    color: str | None = Form(None),
    icon: str | None = Form(None),
    service: CategoryService = Depends(_service),
):
    try:
        category = await service.create(name=name, type=type, color=color, icon=icon)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(
        {
            "id": category.id,
            "name": category.name,
            "type": category.type,
            "color": category.color,
            "icon": category.icon,
        },
        status_code=201,
    )


@router.get("/{category_id}")
async def get_category(category_id: int, service: CategoryService = Depends(_service)):
    category = await service.get(category_id)
    if category is None:
        return JSONResponse({"error": "category not found"}, status_code=404)
    return JSONResponse(
        {
            "id": category.id,
            "name": category.name,
            "type": category.type,
            "color": category.color,
            "icon": category.icon,
            "is_archived": category.is_archived,
        }
    )


@router.put("/{category_id}")
async def update_category(
    category_id: int,
    name: str | None = Form(None),
    type: str | None = Form(None),
    color: str | None = Form(None),
    icon: str | None = Form(None),
    is_archived: bool | None = Form(None),
    service: CategoryService = Depends(_service),
):
    try:
        category = await service.update(
            category_id, name=name, type=type, color=color, icon=icon, is_archived=is_archived
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if category is None:
        return JSONResponse({"error": "category not found"}, status_code=404)
    return JSONResponse({"id": category.id, "name": category.name})


@router.delete("/{category_id}")
async def delete_category(category_id: int, service: CategoryService = Depends(_service)):
    ok = await service.delete(category_id)
    if not ok:
        return JSONResponse({"error": "category not found"}, status_code=404)
    return JSONResponse({"ok": True})


@router.post("/{category_id}/archive")
async def archive_category(category_id: int, service: CategoryService = Depends(_service)):
    category = await service.archive(category_id)
    if category is None:
        return JSONResponse({"error": "category not found"}, status_code=404)
    return JSONResponse({"id": category.id, "is_archived": category.is_archived})
