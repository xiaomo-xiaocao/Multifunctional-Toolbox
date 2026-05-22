import datetime
import asyncpg
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from passlib.hash import bcrypt
from app import templates
from app.main import db_pool   # 需要在 main.py 中导出 db_pool

router = APIRouter(prefix="/skill", tags=["skill"])

def hash_password(password: str) -> str:
    return bcrypt.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.verify(password, hashed)

def get_current_user(request: Request):
    return request.session.get("user_id")

# ---------- 页面 ----------
@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "skill_register.html", {"request": request})

@router.post("/register")
async def register(request: Request, username: str = Form(...), password: str = Form(...)):
    async with db_pool.acquire() as conn:
        try:
            hashed = hash_password(password)
            await conn.execute("INSERT INTO users (username, password_hash) VALUES ($1, $2)", username, hashed)
            user = await conn.fetchrow("SELECT id FROM users WHERE username = $1", username)
            request.session["user_id"] = user["id"]
            return RedirectResponse(url="/skill/workshop", status_code=303)
        except asyncpg.UniqueViolationError:
            return templates.TemplateResponse(request, "skill_register.html", {"request": request, "error": "用户名已存在"})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "skill_login.html", {"request": request})

@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id, password_hash FROM users WHERE username = $1", username)
        if not user or not verify_password(password, user["password_hash"]):
            return templates.TemplateResponse(request, "skill_login.html", {"request": request, "error": "用户名或密码错误"})
        request.session["user_id"] = user["id"]
        return RedirectResponse(url="/skill/workshop", status_code=303)

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/skill/login")

# ---------- 技能工坊主页 ----------
@router.get("/workshop", response_class=HTMLResponse)
async def workshop(request: Request):
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/skill/login")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT s.id, s.name, s.icon, s.attr_name, s.base_exp_req, s.level_multiplier,
                   COALESCE(us.level, 1) as level,
                   COALESCE(us.exp, 0) as exp,
                   us.last_checkin
            FROM skills s
            LEFT JOIN user_skills us ON s.id = us.skill_id AND us.user_id = $1
            ORDER BY s.id
        """, user_id)

        skills_data = []
        today = datetime.date.today()
        for row in rows:
            level = row["level"]
            exp = row["exp"]
            base = row["base_exp_req"]
            mult = row["level_multiplier"]

            # 计算当前等级所需总经验（从0级开始）
            total_exp_needed_for_level = base + (level - 1) * mult
            exp_for_next_level = base + level * mult
            exp_progress = exp - total_exp_needed_for_level
            percent = (exp_progress / (exp_for_next_level - total_exp_needed_for_level)) * 100 if exp_for_next_level > total_exp_needed_for_level else 0
            percent = min(max(percent, 0), 100)

            # 属性值 = 等级 * 10
            attr_value = level * 10

            can_checkin = row["last_checkin"] != today if row["last_checkin"] else True

            skills_data.append({
                "id": row["id"],
                "name": row["name"],
                "icon": row["icon"],
                "attr_name": row["attr_name"],
                "attr_value": attr_value,
                "level": level,
                "exp": exp_progress,
                "exp_needed": exp_for_next_level - total_exp_needed_for_level,
                "progress": int(percent),
                "can_checkin": can_checkin
            })

    return templates.TemplateResponse(request, "skill_workshop.html", {"request": request, "skills": skills_data})

# ---------- 打卡 API ----------
@router.post("/checkin/{skill_id}")
async def checkin(request: Request, skill_id: int):
    user_id = get_current_user(request)
    if not user_id:
        return HTMLResponse("请先登录", status_code=401)

    today = datetime.date.today()
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            # 检查是否已打卡
            last = await conn.fetchval("SELECT last_checkin FROM user_skills WHERE user_id=$1 AND skill_id=$2", user_id, skill_id)
            if last == today:
                return HTMLResponse("<div class='alert alert-warning'>今天已经打卡过了！</div>")

            # 获取技能配置
            skill = await conn.fetchrow("SELECT base_exp_req, level_multiplier FROM skills WHERE id=$1", skill_id)
            if not skill:
                return HTMLResponse("技能不存在", status_code=404)

            # 获取当前进度
            us = await conn.fetchrow("SELECT level, exp FROM user_skills WHERE user_id=$1 AND skill_id=$2", user_id, skill_id)
            if not us:
                level = 1
                exp = 0
            else:
                level = us["level"]
                exp = us["exp"]

            # 增加经验 10
            exp += 10
            base = skill["base_exp_req"]
            mult = skill["level_multiplier"]
            new_level = level
            # 计算升级
            while True:
                threshold = base + (new_level - 1) * mult
                if exp >= threshold:
                    exp -= threshold
                    new_level += 1
                else:
                    break

            # 更新数据库
            if not us:
                await conn.execute("""
                    INSERT INTO user_skills (user_id, skill_id, level, exp, last_checkin)
                    VALUES ($1, $2, $3, $4, $5)
                """, user_id, skill_id, new_level, exp, today)
            else:
                await conn.execute("""
                    UPDATE user_skills SET level=$1, exp=$2, last_checkin=$3
                    WHERE user_id=$4 AND skill_id=$5
                """, new_level, exp, today, user_id, skill_id)

            # 重新获取该技能的所有数据（用于刷新卡片）
            new_row = await conn.fetchrow("""
                SELECT s.id, s.name, s.icon, s.attr_name, s.base_exp_req, s.level_multiplier,
                       COALESCE(us.level, 1) as level,
                       COALESCE(us.exp, 0) as exp
                FROM skills s
                LEFT JOIN user_skills us ON s.id = us.skill_id AND us.user_id = $1
                WHERE s.id = $2
            """, user_id, skill_id)

            # 计算新的进度和属性值
            level = new_row["level"]
            exp_val = new_row["exp"]
            base = new_row["base_exp_req"]
            mult = new_row["level_multiplier"]
            total_exp_needed = base + (level - 1) * mult
            exp_for_next = base + level * mult
            exp_progress = exp_val - total_exp_needed
            percent = (exp_progress / (exp_for_next - total_exp_needed)) * 100 if exp_for_next > total_exp_needed else 0
            percent = min(max(percent, 0), 100)
            attr_value = level * 10

            # 生成卡片 HTML（注意使用 hx-post 保持交互）
            card_html = f"""
            <div class="col-md-4" id="skill-{skill_id}">
                <div class="card mb-3">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <h5>{new_row['icon']} {new_row['name']}</h5>
                            <span class="badge bg-primary">Lv.{level}</span>
                        </div>
                        <div class="progress mb-2">
                            <div class="progress-bar" role="progressbar" style="width: {percent}%"></div>
                        </div>
                        <p>{new_row['attr_name']}: {attr_value}</p>
                        <p>经验: {exp_progress} / {exp_for_next - total_exp_needed}</p>
                        <button hx-post="/skill/checkin/{skill_id}" hx-target="#skill-{skill_id}" hx-swap="outerHTML" class="btn btn-sm btn-success">✨ 打卡 +10</button>
                    </div>
                </div>
            </div>
            """
            return HTMLResponse(card_html)