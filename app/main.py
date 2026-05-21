
import jwt
import hashlib
import httpx
import uuid
import csv
import json
import io
import yaml
from xml.dom.minidom import parseString
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from app import templates
from app.routers import image, text, code, spider
from urllib.parse import quote, unquote
from fastapi.responses import HTMLResponse
# from fastapi.responses import XMLResponse
import qrcode
from io import BytesIO
from fastapi.responses import StreamingResponse

load_dotenv()

app = FastAPI(title="My Toolbox", description="图片处理、文本转换、代码工具")

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 引入路由模块（url、json-format 等页面应该写在下面这些模块里，而不是本文件中）
app.include_router(image.router)
app.include_router(text.router)
app.include_router(code.router)
app.include_router(spider.router)

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request}
    )


@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/text/json-format")
async def json_format_page(request: Request):
    # 将 request 作为第一个参数传入
    return templates.TemplateResponse(request, "json_format.html",context={"request": request})

# URL 编码/解码工具页面
@app.get("/tool/url-codec", response_class=HTMLResponse)
async def url_codec_page(request: Request):
    # 修改这里：直接按照顺序传入 request 和模板名称即可，最简洁且不会出错
    return templates.TemplateResponse(request, "url_codec.html")

@app.post("/tool/url-encode", response_class=HTMLResponse)
async def url_encode(text: str = Form(...)):
    encoded = quote(text, safe='')
    return HTMLResponse(f"<div class='alert alert-success'><strong>编码结果：</strong><br>{encoded}</div>")

@app.post("/tool/url-decode", response_class=HTMLResponse)
async def url_decode(encoded: str = Form(...)):
    try:
        decoded = unquote(encoded)
        return HTMLResponse(f"<div class='alert alert-info'><strong>解码结果：</strong><br>{decoded}</div>")
    except Exception as e:
        return HTMLResponse(content=f"<div class='alert alert-danger'>JSON 解析错误: {e}</div>", media_type="text/html; charset=utf-8")

# @app.get("/sitemap.xml", response_class=XMLResponse)
# async def sitemap():
#     # 列出所有工具的 URL
#     urls = [
#         "/",
#         "/text/json-format",
#         "/image/compress",
#         "/code/base64",
#         "/tool/url-codec",
#     ]
#     # 可以动态获取更多工具页面（例如从数据库读取）
#     # 这里简单生成
#     sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
#     sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
#     for url in urls:
#         sitemap_xml += f"  <url>\n    <loc>https://yourdomain.com{url}</loc>\n    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>\n"
#     sitemap_xml += '</urlset>'
#     return XMLResponse(content=sitemap_xml)
#
# @app.get("/robots.txt")
# async def robots():
#     content = "User-agent: *\nSitemap: https://yourdomain.com/sitemap.xml"
#     return Response(content=content, media_type="text/plain")

@app.get("/tool/qrcode", response_class=HTMLResponse)
async def qrcode_page(request: Request):
    return templates.TemplateResponse(request, "qrcode.html", {"request": request})


import base64
import qrcode
from io import BytesIO
from fastapi import Form
from fastapi.responses import HTMLResponse


@app.post("/tool/qrcode/generate")
async def generate_qrcode(text: str = Form(...)):
    # 1. 如果用户没输入内容，返回红色的错误提示框
    if not text.strip():
        return HTMLResponse(
            content="<div class='alert alert-warning'>请输入文本或网址</div>",
            headers={"Content-Type": "text/html; charset=utf-8"}
        )

    # 2. 后端生成二维码图片并存入内存
    img = qrcode.make(text)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # 3. 关键：将二进制图片数据转换为 Base64 文本字符串
    base64_data = base64.b64encode(buf.getvalue()).decode('utf-8')

    # 4. 关键：直接组装成一个 <img> 标签 HTML 片段返回
    # 这样你的 htmx 接收到这段 HTML 后，就能在网页上完美把图片显示出来
    html_snippet = f"<img src='data:image/png;base64,{base64_data}' class='img-thumbnail shadow' style='max-width: 250px;' />"

    return HTMLResponse(
        content=html_snippet,
        headers={"Content-Type": "text/html; charset=utf-8"}
    )


@app.get("/tool/timestamp", response_class=HTMLResponse)
async def timestamp_page(request: Request):
    return templates.TemplateResponse(request, "timestamp.html", {"request": request})

@app.get("/tool/text-stats", response_class=HTMLResponse)
async def text_stats_page(request: Request):
    return templates.TemplateResponse(request, "text_stats.html", {"request": request})

@app.get("/tool/jwt-decode", response_class=HTMLResponse)
async def jwt_decode_page(request: Request):
    return templates.TemplateResponse(request, "jwt_decode.html", {"request": request})

@app.post("/tool/jwt-decode", response_class=HTMLResponse)
async def jwt_decode_action(token: str = Form(...)):
    try:
        # 只解码不验证签名（适合查看 payload）
        header = jwt.get_unverified_header(token)
        payload = jwt.decode(token, options={"verify_signature": False})
        import json
        result = f"<strong>Header:</strong><pre>{json.dumps(header, indent=2)}</pre><strong>Payload:</strong><pre>{json.dumps(payload, indent=2)}</pre>"
        return HTMLResponse(f"<div class='alert alert-info'>{result}</div>")
    except Exception as e:
        return HTMLResponse(f"<div class='alert alert-danger'>解码失败: {str(e)}</div>")

@app.get("/tool/hash", response_class=HTMLResponse)
async def hash_page(request: Request):
    return templates.TemplateResponse(request, "hash.html", {"request": request})

@app.post("/tool/hash", response_class=HTMLResponse)
async def hash_compute(text: str = Form(...), algo: str = Form(...)):
    encoded = text.encode('utf-8')
    if algo == 'md5':
        result = hashlib.md5(encoded).hexdigest()
    elif algo == 'sha1':
        result = hashlib.sha1(encoded).hexdigest()
    elif algo == 'sha256':
        result = hashlib.sha256(encoded).hexdigest()
    else:
        return HTMLResponse("<div class='alert alert-danger'>不支持的算法</div>")
    return HTMLResponse(f"<div class='alert alert-success'><strong>{algo.upper()} 结果：</strong><br>{result}</div>")

@app.get("/tool/password", response_class=HTMLResponse)
async def password_page(request: Request):
    return templates.TemplateResponse(request, "password.html", {"request": request})

# ========== 1. IP 地址查询 ==========

@app.get("/tool/ip", response_class=HTMLResponse)
async def ip_page(request: Request):
    return templates.TemplateResponse(request, "ip.html", {"request": request})

@app.get("/api/my-ip")
async def get_my_ip(request: Request):
    client_ip = request.client.host
    # 调用免费 IP 归属地 API（ip-api.com 不需要 key，限制 45次/分钟）
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"http://ip-api.com/json/{client_ip}?fields=status,message,country,regionName,city,isp,query")
            data = resp.json()
            if data.get('status') == 'success':
                return {
                    "ip": data['query'],
                    "country": data['country'],
                    "region": data['regionName'],
                    "city": data['city'],
                    "isp": data['isp']
                }
            else:
                return {"ip": client_ip, "error": data.get('message', '无法获取位置')}
        except Exception:
            return {"ip": client_ip, "error": "查询失败"}

# ========== 2. UUID 生成器 ==========

@app.get("/tool/uuid", response_class=HTMLResponse)
async def uuid_page(request: Request):
    return templates.TemplateResponse(request, "uuid.html", {"request": request})

@app.post("/tool/uuid/generate")
async def generate_uuid(count: int = Form(1)):
    if count < 1:
        count = 1
    if count > 20:
        count = 20
    uuids = [str(uuid.uuid4()) for _ in range(count)]
    return HTMLResponse("<br>".join(uuids))

# ========== 3. 进制转换器（纯前端，只需页面路由） ==========
@app.get("/tool/base-convert", response_class=HTMLResponse)
async def base_convert_page(request: Request):
    return templates.TemplateResponse(request, "base_convert.html", {"request": request})

# ========== 4. 文本对比 Diff（纯前端） ==========
@app.get("/tool/diff", response_class=HTMLResponse)
async def diff_page(request: Request):
    return templates.TemplateResponse(request, "diff.html", {"request": request})

# ========== 5. ROT13 编解码（纯前端） ==========
@app.get("/tool/rot13", response_class=HTMLResponse)
async def rot13_page(request: Request):
    return templates.TemplateResponse(request, "rot13.html", {"request": request})

# ========== 6. HTML 实体编解码（纯前端） ==========
@app.get("/tool/html-entity", response_class=HTMLResponse)
async def html_entity_page(request: Request):
    return templates.TemplateResponse(request, "html_entity.html", {"request": request})

# ========== 7. 图片转 Base64（纯前端） ==========
@app.get("/tool/image-to-base64", response_class=HTMLResponse)
async def image_to_base64_page(request: Request):
    return templates.TemplateResponse(request, "image_to_base64.html", {"request": request})

# ========== 8. 随机密码强度检测（纯前端，可集成到现有密码生成器，这里单独页面） ==========
@app.get("/tool/password-strength", response_class=HTMLResponse)
async def password_strength_page(request: Request):
    return templates.TemplateResponse(request, "password_strength.html", {"request": request})

# ========== 新增工具 ==========

@app.get("/tool/json-to-csv", response_class=HTMLResponse)
async def json_to_csv_page(request: Request):
    return templates.TemplateResponse(request, "json_to_csv.html", {"request": request})

@app.post("/api/json-to-csv")
async def json_to_csv_api(json_data: str = Form(...)):
    try:
        data = json.loads(json_data)
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            return {"error": "请输入JSON数组（例如 [{\"a\":1}, {\"a\":2}]）"}
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        return {"csv": output.getvalue()}
    except Exception as e:
        return {"error": str(e)}

@app.get("/tool/yaml-json", response_class=HTMLResponse)
async def yaml_json_page(request: Request):
    return templates.TemplateResponse(request, "yaml_json.html", {"request": request})

@app.post("/api/yaml-to-json")
async def yaml_to_json(yaml_text: str = Form(...)):
    try:
        data = yaml.safe_load(yaml_text)
        return {"json": json.dumps(data, indent=2, ensure_ascii=False)}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/json-to-yaml")
async def json_to_yaml(json_text: str = Form(...)):
    try:
        data = json.loads(json_text)
        yaml_str = yaml.dump(data, allow_unicode=True, sort_keys=False)
        return {"yaml": yaml_str}
    except Exception as e:
        return {"error": str(e)}

@app.get("/tool/xml-format", response_class=HTMLResponse)
async def xml_format_page(request: Request):
    return templates.TemplateResponse(request, "xml_format.html", {"request": request})

@app.post("/api/xml-format")
async def format_xml(xml_text: str = Form(...)):
    try:
        dom = parseString(xml_text)
        pretty_xml = dom.toprettyxml(indent="  ")
        # 去掉第一行 <?xml version...> 如果不需要可以保留
        return {"formatted": pretty_xml}
    except Exception as e:
        return {"error": str(e)}

# 纯前端工具只需页面路由
@app.get("/tool/url-parser", response_class=HTMLResponse)
async def url_parser_page(request: Request):
    return templates.TemplateResponse(request, "url_parser.html", {"request": request})

@app.get("/tool/color-converter", response_class=HTMLResponse)
async def color_converter_page(request: Request):
    return templates.TemplateResponse(request, "color_converter.html", {"request": request})

@app.get("/tool/regex-tester", response_class=HTMLResponse)
async def regex_tester_page(request: Request):
    return templates.TemplateResponse(request, "regex_tester.html", {"request": request})

