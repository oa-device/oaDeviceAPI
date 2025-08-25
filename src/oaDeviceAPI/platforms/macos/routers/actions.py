from fastapi import APIRouter, HTTPException, status

from ..services.actions import ActionsService

router = APIRouter(prefix="/actions", tags=["actions"])

actions_service = ActionsService()


@router.post("/reboot")
async def reboot_device():
    """Reboot the macOS device."""
    try:
        result = await actions_service.reboot_device()
        return {"status": "success", "message": "Reboot initiated", "details": result}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reboot device: {str(e)}",
        )


@router.post("/restart-tracker")
async def restart_tracker():
    """Restart the tracker service on macOS."""
    try:
        result = await actions_service.restart_tracker()
        return {
            "status": "success",
            "message": "Tracker restart initiated",
            "details": result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart tracker: {str(e)}",
        )
