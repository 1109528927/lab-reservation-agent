from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


def success_response(message: str = "success", data=None):
    """
    统一成功响应。
    - code 固定 200（不自定义）
    - message / data 由调用方传入（自定义）
    - jsonable_encoder：把 Pydantic / ORM / datetime 等转成 JSON 能认的格式
    """
    content = {
        "code": 200,
        "message": message,
        "data": data,
    }
    return JSONResponse(content=jsonable_encoder(content))