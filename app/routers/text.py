from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from app import templates
import json

router = APIRouter(prefix="/text", tags=["text"])

# 这是应该在 app/routers/text.py 里修改后的样子：
@router.get("/json-format")  # 注意这里通常是 router.get 并且不需要带前缀 /text
async def json_format_page(request: Request):
    return templates.TemplateResponse(request, "json_format.html")


@router.post("/json-format", response_class=HTMLResponse)
async def json_format_action(raw_json: str = Form(...)):
    try:
        # 1. 尝试解析并重新美化 JSON
        parsed = json.loads(raw_json)
        formatted = json.dumps(parsed, indent=4, ensure_ascii=False)  # ensure_ascii=False 保证中文不变成 \u4e09

        # 2. 成功时，返回带有 <pre> 标签的 HTML 片段
        return HTMLResponse(
            content=f"<pre class='bg-light p-3 border rounded'><code>{formatted}</code></pre>",
            headers={"Content-Type": "text/html; charset=utf-8"}  # 显式指定 utf-8 彻底解决乱码
        )
    except json.JSONDecodeError as e:
        # 3. 失败时，捕获异常，返回友好的中文错误提示，同样指定 utf-8
        error_msg = f"JSON 解析错误: {str(e)}"
        return HTMLResponse(
            content=f"<div class='alert alert-danger'><strong>错误：</strong>{error_msg}</div>",
            headers={"Content-Type": "text/html; charset=utf-8"}  # 防止中文变成“瑙ｆ瀽閿欒”
        )
