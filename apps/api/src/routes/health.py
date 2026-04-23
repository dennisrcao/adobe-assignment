from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def health_check():
    return {
        "status": "healthy",
        "service": "creative-automation-api",
        "version": "0.1.0",
    }
