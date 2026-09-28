"""货邮装载接口：维护装载单，覆盖安排装载、确认完成、取消装载等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.cargo import CargoService

router = APIRouter(prefix="/api/cargo", tags=["货邮装载"])

service = CargoService()

LIST_FIELDS = ["装载单号", "关联航班", "货邮重量", "装载位置", "装载车辆", "作业人员", "完成时刻", "装载状态"]
STATUSES = ["待装载", "装载中", "已完成", "已取消"]
MAX_PAGE_SIZE = 200


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按装载单号检索"),
    flight: str | None = Query(default=None, description="按关联航班检索"),
    weight: str | None = Query(default=None, description="按货邮重量检索"),
    location: str | None = Query(default=None, description="按装载位置检索"),
    status: str | None = Query(default=None, description="待装载、装载中、已完成、已取消"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按条件过滤货邮装载列表；页码或每页条数不合法直接判失败，超范围页码落到最后一页。"""
    if page < 1:
        raise HTTPException(status_code=400, detail="页码必须是不小于 1 的正整数，请重新输入")
    if size < 1:
        raise HTTPException(status_code=400, detail="每页条数必须是不小于 1 的正整数，请重新输入")
    if size > MAX_PAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"每页最多 {MAX_PAGE_SIZE} 条，请缩小分页范围")
    items, total, current_page = service.list_entries(
        keyword=keyword,
        flight=flight,
        weight=weight,
        location=location,
        status=status,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=current_page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出货邮装载清单：返回当前过滤条件下的全量数据。"""
    items, total, _ = service.list_entries(page=1, size=10000)
    return {"module": "cargo", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条装载单明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"装载单 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条装载单，缺字段或装载单号重复时说明原因而不是静默丢弃。"""
    entry, message = service.create_entry(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message="装载单已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条装载单执行安排装载、确认完成、取消装载；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
