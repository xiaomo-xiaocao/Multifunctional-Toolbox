import asyncio
from fastapi import APIRouter, Request, File, UploadFile, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from io import BytesIO
from app import templates
from app.utils.image_utils import compress_image

router = APIRouter(prefix="/image", tags=["image"])


# 1. 修复：压缩工具页面
@router.get("/compress", response_class=HTMLResponse)
async def compress_page(request: Request):
    # 修复：将 request 改为第一个参数，解决新版 FastAPI 导致的 500 字典报错
    return templates.TemplateResponse(request, "image_compress.html")


# 2. 修复：图片压缩逻辑处理
@router.post("/compress")
async def compress_image_endpoint(
        file: UploadFile = File(...),
        quality: int = Form(85),
        max_width: int = Form(1920)
):
    contents = await file.read()

    # 修复：恢复被破坏的中文，并加上 utf-8 响应头彻底杜绝乱码
    if len(contents) > 10 * 1024 * 1024:
        return HTMLResponse(
            content="<div class='alert alert-danger'>文件过大，请上传小于10MB的图片</div>",
            headers={"Content-Type": "text/html; charset=utf-8"}
        )

    output_bytes = await asyncio.to_thread(compress_image, contents, quality, max_width)

    # 修复：恢复被破坏的中文，并加上 utf-8 响应头彻底杜绝乱码
    if output_bytes is None:
        return HTMLResponse(
            content="<div class='alert alert-danger'>压缩失败，请检查图片格式</div>",
            headers={"Content-Type": "text/html; charset=utf-8"}
        )

    return StreamingResponse(
        BytesIO(output_bytes),
        media_type="image/jpeg",
        headers={"Content-Disposition": "attachment; filename=compressed.jpg"}
    )
