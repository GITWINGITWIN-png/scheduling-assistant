"""The log page (W9 สิ่งที่เลขาทำ): what the secretary did, and undo."""

from fastapi import APIRouter, HTTPException, Query

from app.core import actions

router = APIRouter(prefix="/api/log", tags=["log"])


@router.get("")
def list_log(range: str = Query("today", pattern="^(today|7d|all)$"),
             group: str = Query("all", pattern="^(all|calendar|person|job)$")) -> dict:
    return {
        "items": actions.list_actions(range, group),
        "groups": [{"key": "all", "label": "ทุกชนิด"}] + [{"key": k, "label": v[0]} for k, v in actions.GROUPS.items()],
    }


@router.post("/{action_id}/undo")
async def undo(action_id: int) -> dict:
    try:
        a = await actions.undo(action_id)
    except actions.UndoError as exc:
        raise HTTPException(409, str(exc)) from exc
    return actions.as_dict(a)
