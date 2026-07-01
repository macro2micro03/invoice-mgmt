from fastapi import Header, HTTPException

from . import config


def verify_password(x_app_password: str = Header(default="")) -> None:
    if not config.APP_PASSWORD:
        return
    if x_app_password != config.APP_PASSWORD:
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")
