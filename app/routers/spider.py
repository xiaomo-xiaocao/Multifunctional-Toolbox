import json
import ipaddress
import httpx
from urllib.parse import urlparse, quote, unquote
from bs4 import BeautifulSoup
from lxml import html, etree
from lxml.cssselect import CSSSelector
from lxml.etree import XPathEvalError
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from app import templates

# router = APIRouter(prefix="/tool", tags=["spider"])
# 页面路由（带 /tool 前缀）
page_router = APIRouter(prefix="/tool", tags=["spider"])
# API 路由（无前缀）
api_router = APIRouter(tags=["spider-api"])

# ---------- 辅助函数：验证 URL 安全 ----------
def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        host = parsed.hostname
        if host is None:
            return False
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_multicast:
            return False
    except Exception:
        return False
    return True


# ================= 1. User-Agent 生成器（纯前端） =================
@page_router.get("/user-agent", response_class=HTMLResponse)
async def user_agent_page(request: Request):
    return templates.TemplateResponse(request, "user_agent.html", {"request": request})


# ================= 2. 网页元信息提取器 =================
@page_router.get("/page-meta", response_class=HTMLResponse)
async def page_meta_page(request: Request):
    return templates.TemplateResponse(request, "page_meta.html", {"request": request})

@api_router.post("/api/fetch-meta")
async def fetch_meta(url: str = Form(...)):
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    if not is_safe_url(url):
        return {"error": "不支持的 URL 或内网地址"}
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else ''
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            description = desc_tag.get('content', '').strip() if desc_tag else ''
            keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
            keywords = keywords_tag.get('content', '').strip() if keywords_tag else ''
            return {"title": title, "description": description, "keywords": keywords, "url": str(resp.url)}
        except Exception as e:
            return {"error": f"请求失败: {str(e)}"}


# ================= 3. Robots.txt 检测工具 =================
@page_router.get("/robots-txt", response_class=HTMLResponse)
async def robots_txt_page(request: Request):
    return templates.TemplateResponse(request, "robots_txt.html", {"request": request})

@api_router.post("/api/robots-txt")
async def check_robots(url: str = Form(...)):
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    if not is_safe_url(url):
        return {"error": "不支持的 URL 或内网地址"}
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        try:
            resp = await client.get(robots_url)
            if resp.status_code == 200:
                content = resp.text[:5000]
                return {"status": "存在", "content": content, "url": robots_url}
            else:
                return {"status": f"不存在 (HTTP {resp.status_code})", "content": ""}
        except Exception as e:
            return {"status": "请求失败", "error": str(e)}


# ================= 4. 响应头分析器 =================
@page_router.get("/headers", response_class=HTMLResponse)
async def headers_page(request: Request):
    return templates.TemplateResponse(request, "headers.html", {"request": request})

@api_router.post("/api/fetch-headers")
async def fetch_headers(url: str = Form(...)):
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    if not is_safe_url(url):
        return {"error": "不支持的 URL 或内网地址"}
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        try:
            # 先尝试 HEAD 请求
            resp = await client.head(url)
            if resp.status_code >= 400:
                # 部分服务器不支持 HEAD，回退到 GET
                resp = await client.get(url)
            headers = dict(resp.headers)
            return {"headers": headers, "status_code": resp.status_code, "url": str(resp.url)}
        except Exception as e:
            return {"error": f"请求失败: {str(e)}"}


# ================= 5. XPath 测试器 =================
@page_router.get("/xpath-tester", response_class=HTMLResponse)
async def xpath_tester_page(request: Request):
    return templates.TemplateResponse(request, "xpath_tester.html", {"request": request})

@api_router.post("/api/xpath-test")
async def xpath_test(html_content: str = Form(...), xpath_expr: str = Form(...)):
    if len(html_content) > 50000:
        return {"error": "HTML 内容过长，请限制在 50000 字符以内"}
    if len(xpath_expr) > 500:
        return {"error": "XPath 表达式过长"}
    try:
        parser = html.HTMLParser(encoding='utf-8')
        tree = html.fromstring(html_content, parser=parser)
        elements = tree.xpath(xpath_expr)
        results = []
        for el in elements[:50]:  # 最多50个结果
            if isinstance(el, str):
                results.append(el)
            elif isinstance(el, (etree._Element, html.HtmlElement)):
                results.append(etree.tostring(el, encoding='unicode', method='html'))
            else:
                results.append(str(el))
        truncated = len(elements) > 50
        return {"results": results, "count": len(elements), "truncated": truncated}
    except XPathEvalError as e:
        return {"error": f"XPath 语法错误: {str(e)}"}
    except Exception as e:
        return {"error": f"解析失败: {str(e)}"}


# ================= 6. CSS 选择器测试器 =================
@page_router.get("/css-tester", response_class=HTMLResponse)
async def css_tester_page(request: Request):
    return templates.TemplateResponse(request, "css_tester.html", {"request": request})

@api_router.post("/api/css-test")
async def css_test(html_content: str = Form(...), css_selector: str = Form(...)):
    if len(html_content) > 50000:
        return {"error": "HTML 内容过长"}
    if len(css_selector) > 500:
        return {"error": "选择器过长"}
    try:
        parser = html.HTMLParser(encoding='utf-8')
        tree = html.fromstring(html_content, parser=parser)
        selector = CSSSelector(css_selector)
        elements = selector(tree)
        results = []
        for el in elements[:50]:
            results.append(etree.tostring(el, encoding='unicode', method='html'))
        truncated = len(elements) > 50
        return {"results": results, "count": len(elements), "truncated": truncated}
    except Exception as e:
        return {"error": f"解析失败: {str(e)}"}


# ================= 7. HTTP 状态码查询工具 =================
HTTP_STATUSES = {
    200: "OK - 请求成功",
    201: "Created - 资源已创建",
    301: "Moved Permanently - 永久重定向",
    302: "Found - 临时重定向",
    400: "Bad Request - 请求语法错误",
    401: "Unauthorized - 未授权",
    403: "Forbidden - 禁止访问",
    404: "Not Found - 资源不存在",
    500: "Internal Server Error - 服务器内部错误",
}

@page_router.get("/http-status", response_class=HTMLResponse)
async def http_status_page(request: Request):
    return templates.TemplateResponse(request, "http_status.html", {"request": request})

@api_router.post("/api/http-status")
async def http_status_query(code: int = Form(...)):
    status_text = HTTP_STATUSES.get(code, "未知状态码")
    return {"code": code, "text": status_text, "known": code in HTTP_STATUSES}


# ================= 8. Cookie 工具（只读） =================
@page_router.get("/cookie-tool", response_class=HTMLResponse)
async def cookie_tool_page(request: Request):
    return templates.TemplateResponse(request, "cookie_tool.html", {"request": request})

@page_router.get("/api/show-cookies")
async def show_cookies(request: Request):
    cookies = dict(request.cookies)
    return {"cookies": cookies}