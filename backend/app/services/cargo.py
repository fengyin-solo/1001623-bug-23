"""货邮装载业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "cargo"
REQUIRED_FIELDS = ["装载单号", "关联航班", "货邮重量"]
STATUS_ORDER = ["待装载", "装载中", "已完成", "已取消"]
ACTION_RULES = {"安排装载": "装载中", "确认完成": "已完成", "取消装载": "已取消"}
NEGATIVE_ACTIONS = []


class CargoService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        flight: str | None = None,
        weight: str | None = None,
        position: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, int, str | None]:
        """按条件过滤并分页。

        返回 (当前页数据, 过滤后总数, 实际页码, 提示语)。
        page、size 的合法性由接口层校验；这里只负责把超出末页的页码收敛到最后一页，
        保证页码、行数、合计三者口径一致。
        """
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("装载单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if flight:
            rows = [row for row in rows if flight in str(row.get("关联航班", ""))]
        if weight:
            rows = [row for row in rows if weight in str(row.get("货邮重量", ""))]
        if position:
            rows = [row for row in rows if position in str(row.get("装载位置", ""))]
        total = len(rows)
        last_page = max(1, (total + size - 1) // size)
        message = None
        if page > last_page:
            message = f"第 {page} 页超出范围，已为您跳到最后一页（第 {last_page} 页）"
            page = last_page
        start = (page - 1) * size
        return rows[start:start + size], total, page, message

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        """登记装载单：缺必填字段、装载单号重复都明确拦下并说明原因。"""
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        code = str(values.get("装载单号")).strip()
        rows = store.rows(MODULE)
        if any(str(row.get("装载单号", "")).strip() == code for row in rows):
            return None, f"装载单号 {code} 已存在，请勿重复登记"
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, None

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"装载单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于货邮装载可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"装载单已{action}"
