from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from app import templates
from app.utils.text_utils import base64_encode, base64_decode

router = APIRouter(prefix="/code", tags=["code"])

# 1. 修复：Base64 工具页面传参
@router.get("/base64", response_class=HTMLResponse)
async def base64_page(request: Request):
    # 修复：request 改为第一参数，适配新版 FastAPI/Starlette
    return templates.TemplateResponse(request, "base64.html")

# 2. 修复：编码响应文本及字符集
@router.post("/base64/encode", response_class=HTMLResponse)
async def base64_encode_action(text: str = Form(...)):
    result = base64_encode(text)
    # 修复：恢复中文“编码结果：”，并显式指定 utf-8 响应头
    return HTMLResponse(
        content=f"<div class='alert alert-success'><strong>编码结果：</strong><br>{result}</div>",
        headers={"Content-Type": "text/html; charset=utf-8"}
    )

# 3. 修复：解码响应文本及字符集
@router.post("/base64/decode", response_class=HTMLResponse)
async def base64_decode_action(encoded: str = Form(...)):
    result = base64_decode(encoded)
    # 修复：恢复中文“解码结果：”，并显式指定 utf-8 响应头
    return HTMLResponse(
        content=f"<div class='alert alert-info'><strong>解码结果：</strong><br>{result}</div>",
        headers={"Content-Type": "text/html; charset=utf-8"}
    )
