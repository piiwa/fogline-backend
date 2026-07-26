from fastapi import APIRouter

from app.core.security import create_access_token
from app.schemas.auth import DeviceAuthRequest, TokenResponse

router = APIRouter()


@router.post("/device", response_model=TokenResponse)
async def device_auth(payload: DeviceAuthRequest) -> TokenResponse:
    """
    Mock device auth: exchange a device id for a JWT whose subject scopes all
    exploration data. In production this endpoint would be real user auth — the
    subject then being the user id, shared across their devices (multi-device
    merge). The sync contract is identical.
    """
    return TokenResponse(access_token=create_access_token(subject=payload.device_id))
