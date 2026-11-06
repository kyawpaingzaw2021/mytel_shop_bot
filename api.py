import glob
import hashlib
import hmac
import json
import logging
import os
import re
import urllib.parse
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import config, is_super_admin
from db.models.admin import Admin
from db.models.cashout import Cashout
from db.models.item import Item
from db.models.order import Order, OrderPhone
from db.models.topup import Topup
from db.models.tier import Tier
from db.models.user import User
from db.session import get_session
from services import audit as audit_svc
from services import cashout as cashout_svc
from services import item as item_svc
from services import order as order_svc
from services import settings as settings_svc
from services import topup as topup_svc
from services import user as user_svc
from services import wallet as wallet_svc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI()
UPLOAD_DIR = "webapp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def verify_telegram_data(init_data: str, bot_token: str) -> dict | None:
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data))
        if "hash" not in parsed: return None
        hash_val = parsed.pop("hash")
        dcs = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
        if calc != hash_val: return None
        return json.loads(parsed.get("user", "{}"))
    except Exception:
        return None


async def check_admin(init_data: str, session: AsyncSession) -> dict:
    tg_user = verify_telegram_data(init_data, config.BOT_TOKEN)
    if not tg_user: raise HTTPException(401, "Invalid data")
    tg_id = int(tg_user.get("id", 0))
    if is_super_admin(tg_id): return tg_user
    res = await session.execute(select(Admin).where(Admin.telegram_id == tg_id, Admin.is_active == True))
    if res.scalar_one_or_none(): return tg_user
    raise HTTPException(403, "Admin မဟုတ်ပါ")


async def send_tg(chat_id: int, text: str) -> None:
    if not chat_id: return
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
    except Exception: pass


async def send_tg_photo(chat_id: int, photo_path: str, caption: str) -> None:
    if not chat_id or not os.path.exists(photo_path): return
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendPhoto"
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            with open(photo_path, "rb") as f:
                await c.post(url, data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}, files={"photo": f})
    except Exception: pass


def _safe_slug(name: str, max_len: int = 40) -> str:
    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return clean[:max_len] or "unnamed"


# ═══════════════════════════════════════════════════════════════
# Init / Public
# ═══════════════════════════════════════════════════════════════
@app.post("/api/init")
async def init_app(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = verify_telegram_data(body.get("initData", ""), config.BOT_TOKEN)
    if not tg_user: raise HTTPException(401, "Invalid data")

    maint = await settings_svc.get(session, "maintenance", "off")
    support = await settings_svc.get(session, "support_contact", "@Admin")
    kpay = await settings_svc.get(session, "payment_kpay", "")
    wave = await settings_svc.get(session, "payment_wave", "")
    pay_name = await settings_svc.get(session, "payment_name", "")
    wait_time = await settings_svc.get(session, "wait_time", "၅ မိနစ်")

    tg_id = int(tg_user.get("id", 0))
    common = {"maintenance": maint, "support": support, "kpay": kpay,
              "wave": wave, "payment_name": pay_name, "wait_time": wait_time}

    if is_super_admin(tg_id):
        return {"role": "super_admin", "name": tg_user.get("first_name", "Admin"), "balance": 0, **common}

    res = await session.execute(select(Admin).where(Admin.telegram_id == tg_id, Admin.is_active == True))
    db_admin = res.scalar_one_or_none()
    if db_admin:
        return {"role": db_admin.role, "name": tg_user.get("first_name", "Admin"), "balance": 0, **common}

    user = await user_svc.get_or_create(session, tg_id, tg_user.get("username"), tg_user.get("first_name"))

    ref_id = body.get("ref")
    if ref_id and str(ref_id) != str(user.id) and not user.referred_by:
        try:
            referrer = await user_svc.get_by_id(session, int(ref_id))
            if referrer:
                user.referred_by = referrer.id
                await session.commit()
        except Exception as e:
            logger.error(f"Referral error: {e}")

    return {
        "role": user.role or "user", "name": user.full_name or "User",
        "balance": float(user.balance or 0), "default_phone": user.default_phone or "",
        "user_id": user.id, "is_banned": user.is_banned, **common,
    }


@app.get("/api/items")
async def get_items(session: AsyncSession = Depends(get_session)):
    items = await item_svc.list_active(session)
    return [{
        "id": it.id, "name": it.name, "price": float(it.user_price),
        "reseller_price": float(it.reseller_price) if it.reseller_price else None,
        "category": it.category, "subcategory": it.subcategory,
        "tutorial": it.tutorial_url, "form_type": it.form_type, "note": it.note or ""
    } for it in items]


@app.get("/api/category_images")
async def get_category_images():
    images = {}
    for fp in glob.glob(os.path.join(UPLOAD_DIR, "cat_*.png")):
        key = os.path.basename(fp).replace("cat_", "").replace(".png", "")
        images[key] = f"/uploads/{os.path.basename(fp)}"
    return images


# ═══════════════════════════════════════════════════════════════
# User - Balance / Topup / Order / History / Cashout
# ═══════════════════════════════════════════════════════════════
@app.post("/api/user/balance")
async def get_user_balance(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = verify_telegram_data(body.get("initData"), config.BOT_TOKEN)
    if not tg_user: raise HTTPException(401)
    user = await user_svc.get_by_telegram_id(session, int(tg_user["id"]))
    if not user: return {"balance": 0}
    return {"balance": float(user.balance or 0)}


@app.post("/api/user/topup")
async def user_topup(request: Request, amount: float = Form(...), sender_phone: str = Form(...),
                     file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    form = await request.form()
    tg_user = verify_telegram_data(form.get("initData"), config.BOT_TOKEN)
    if not tg_user: raise HTTPException(401)

    user = await user_svc.get_by_telegram_id(session, int(tg_user["id"]))
    if not user: raise HTTPException(404)

    topup_min = float(await settings_svc.get(session, "topup_min", 1000))
    topup_max = float(await settings_svc.get(session, "topup_max", 1000000))
    if amount < topup_min or amount > topup_max:
        raise HTTPException(400, f"ပမာဏ {int(topup_min):,} - {int(topup_max):,} အတွင်း ဖြစ်ရမည်")

    max_pending = int(await settings_svc.get(session, "max_pending_topups", 3))
    res = await session.execute(select(func.count()).select_from(Topup).where(Topup.user_id == user.id, Topup.status == "pending"))
    if res.scalar_one() >= max_pending:
        raise HTTPException(400, f"Pending topup {max_pending} ခုရှိနေပါပြီ။")

    contents = await file.read()
    ext = (file.filename or "png").split(".")[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        raise HTTPException(400, "ပုံဖိုင် type မမှန်ပါ")
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f: f.write(contents)

    await topup_svc.create_topup(session, user.id, Decimal(str(amount)), filename, sender_phone)
    await send_tg(user.telegram_id, f"💳 <b>Topup တင်ပြီးပါပြီ</b>\n\n💰 {int(amount):,} Ks\n⏳ Admin မှ စစ်ဆေးပါမည်။")
    await send_tg_photo(config.ADMIN_GROUP_ID, path, f"💳 <b>Topup အသစ်</b>\n\n👤 {user.full_name}\n💰 {int(amount):,} Ks\n📱 {sender_phone}")
    return {"status": "ok"}


@app.post("/api/order")
async def create_order(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = verify_telegram_data(body.get("initData"), config.BOT_TOKEN)
    if not tg_user: raise HTTPException(401, "Invalid data")
    if await settings_svc.get(session, "maintenance", "off") == "on": raise HTTPException(403, "ဆိုင်ပိတ်ထားပါသည်")

    user = await user_svc.get_by_telegram_id(session, int(tg_user["id"]))
    if not user: raise HTTPException(404, "User မတွေ့ပါ")
    if user.is_banned: raise HTTPException(403, "သင့်အကောင့်ကို ပိတ်ထားပါသည်။ Order တင်၍ မရပါ။")

    item = await item_svc.get_item(session, int(body.get("item_id", 0)))
    phone = (body.get("phone") or "").strip()
    address = (body.get("address") or "").strip()
    contact_phone = (body.get("contact_phone") or "").strip()
    game_id = (body.get("game_id") or "").strip()
    game_zone = (body.get("game_zone") or "").strip()
    game_name = (body.get("game_name") or "").strip()

    if not item: raise HTTPException(400, "Item မတွေ့ပါ")

    if item.form_type in ('MLBB', 'PUBG'):
        if not game_id: raise HTTPException(400, "Game ID ဖြည့်ပါ")
    elif item.form_type == 'sim':
        if not address or not contact_phone: raise HTTPException(400, "လိပ်စာနဲ့ ဖုန်းနံပါတ် ဖြည့်ပါ")
    else:
        if not re.match(r"^09\d{7,9}$", phone): raise HTTPException(400, "ဖုန်းနံပါတ် မမှန်ပါ")

    final_price = item.reseller_price if (user.role == "reseller" and item.reseller_price) else item.user_price

    try:
        order = await order_svc.create_order(
            session, user, item, 1, [phone or 'N/A'], final_price,
            address=address, contact_phone=contact_phone,
            game_id=game_id, game_zone=game_zone, game_name=game_name,
        )
    except ValueError as e:
        if "insufficient_balance" in str(e): raise HTTPException(400, "Balance မလုံလောက်ပါ")
        raise HTTPException(400, str(e))

    await send_tg(user.telegram_id, f"✅ <b>Order တင်ပြီးပါပြီ</b>\n\n📦 {item.name}\n💰 {int(order.total):,} Ks")

    game_info = ""
    if order.game_id:
        game_info = f"🎮 Name: {order.game_name or '-'}\n🎮 ID: {order.game_id}"
        if order.game_zone: game_info += f" (Zone: {order.game_zone})"
        game_info += "\n"
    phone_display = phone[:7] + "***" if phone and phone != 'N/A' else "-"
    await send_tg(config.ADMIN_GROUP_ID,
        f"🛒 <b>Order အသစ်</b>\n\n👤 {user.full_name}\n📦 {item.name}\n{game_info}📱 {phone_display}\n💰 {int(order.total):,} Ks")

    phones = await order_svc.list_phones(session, order.id)
    for p in phones:
        kb = {"inline_keyboard": [[
            {"text": "✅ Done", "callback_data": f"ph_done:{order.id}:{p.id}"},
            {"text": "❌ Fail", "callback_data": f"ph_fail:{order.id}:{p.id}"}
        ]]}
        url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(url, json={"chat_id": config.ADMIN_GROUP_ID,
                    "text": f"📱 <b>{order.order_code}</b> — {p.phone}",
                    "parse_mode": "HTML", "reply_markup": kb})
        except Exception: pass
    return {"status": "ok", "order_code": order.order_code}


@app.post("/api/user/history")
async def user_history(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = verify_telegram_data(body.get("initData"), config.BOT_TOKEN)
    if not tg_user: raise HTTPException(401)
    user = await user_svc.get_by_telegram_id(session, int(tg_user["id"]))
    if not user: return {"orders": [], "transactions": [], "topups": []}

    res_orders = await session.execute(select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc()).limit(20))
    orders = [{"code": o.order_code, "item": o.item_name, "price": float(o.total),
               "status": o.status, "date": o.created_at.strftime("%m-%d %H:%M")} for o in res_orders.scalars().all()]

    res_txs = await wallet_svc.list_transactions(session, user.id, limit=20)
    txs = [{"type": t.type, "amount": float(t.amount), "date": t.created_at.strftime("%m-%d %H:%M"), "note": t.note} for t in res_txs]

    res_topups = await session.execute(select(Topup).where(Topup.user_id == user.id).order_by(Topup.created_at.desc()).limit(20))
    topups = [{"amount": float(t.amount), "status": t.status, "date": t.created_at.strftime("%m-%d %H:%M")} for t in res_topups.scalars().all()]

    return {"orders": orders, "transactions": txs, "topups": topups}


@app.post("/api/user/cashout")
async def user_cashout(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = verify_telegram_data(body.get("initData"), config.BOT_TOKEN)
    if not tg_user: raise HTTPException(401)
    user = await user_svc.get_by_telegram_id(session, int(tg_user["id"]))
    if not user: raise HTTPException(404)

    amount = Decimal(str(body.get("amount", 0)))
    acc_name = body.get("account_name", "").strip()
    phone = body.get("phone", "").strip()
    min_cashout = Decimal(await settings_svc.get(session, "min_cashout", "1000"))

    if amount < min_cashout: raise HTTPException(400, f"အနည်းဆုံး {int(min_cashout):,} ကျပ် ထုတ်ရပါမည်")
    if not acc_name or not phone: raise HTTPException(400, "အကောင့်နာမည်နဲ့ ဖုန်းနံပါတ် ဖြည့်ပါ")

    try:
        cashout = await cashout_svc.create_cashout(session, user.id, amount, acc_name, phone)
        await send_tg(user.telegram_id, f"💸 <b>Cash Out တောင်းဆိုပြီးပါပြီ</b>\n\n💰 {int(amount):,} Ks\n⏳ Admin မှ စစ်ဆေးပါမည်။")
        await send_tg(config.ADMIN_GROUP_ID, f"💸 <b>Cash Out အသစ်</b>\n\n👤 {user.full_name}\n💰 {int(amount):,} Ks\n🏦 {acc_name}\n📱 {phone}")
        return {"status": "ok"}
    except ValueError as e:
        if "insufficient_balance" in str(e): raise HTTPException(400, "Balance မလုံလောက်ပါ")
        raise HTTPException(400, str(e))


# ═══════════════════════════════════════════════════════════════
# Admin - Dashboard / Orders / Topups / Items / Users / Settings
# ═══════════════════════════════════════════════════════════════
@app.post("/api/admin/dashboard")
async def admin_dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    await check_admin(body.get("initData"), session)

    res_o = await session.execute(select(func.count()).select_from(Order).where(Order.status.in_(["pending", "processing"])))
    res_t = await session.execute(select(func.count()).select_from(Topup).where(Topup.status == "pending"))
    res_u = await session.execute(select(func.count()).select_from(User))
    res_cash_in = await session.execute(select(func.coalesce(func.sum(Order.total), 0)).where(Order.status.in_(["completed", "partially_completed"])))
    res_cash_out = await session.execute(select(func.coalesce(func.sum(OrderPhone.price), 0)).where(OrderPhone.status.in_(["failed", "refunded"])))

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    res_today_sales = await session.execute(select(func.coalesce(func.sum(Order.total), 0)).where(Order.status.in_(["completed", "partially_completed"]), Order.created_at >= today_start))
    res_today_orders = await session.execute(select(func.count()).select_from(Order).where(Order.created_at >= today_start))
    maint = await settings_svc.get(session, "maintenance", "off")

    return {
        "pending_orders": res_o.scalar_one(), "pending_topups": res_t.scalar_one(),
        "total_users": res_u.scalar_one(), "maintenance": maint,
        "cash_in": float(res_cash_in.scalar_one()), "cash_out": float(res_cash_out.scalar_one()),
        "today_sales": float(res_today_sales.scalar_one()), "today_orders": res_today_orders.scalar_one(),
    }


@app.post("/api/admin/chart_data")
async def admin_chart_data(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    await check_admin(body.get("initData"), session)

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    labels, data = [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        next_day = day + timedelta(days=1)
        res = await session.execute(select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.status.in_(["completed", "partially_completed"]),
            Order.created_at >= day, Order.created_at < next_day))
        labels.append(day.strftime("%m-%d"))
        data.append(float(res.scalar_one()))
    return {"labels": labels, "data": data}


@app.post("/api/admin/orders")
async def admin_orders(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    await check_admin(body.get("initData"), session)
    status_filter = body.get("status", "all")
    search = (body.get("search") or "").strip()
    stmt = select(Order).order_by(Order.created_at.desc()).limit(50)
    if status_filter == "pending": stmt = stmt.where(Order.status.in_(["pending", "processing"]))
    elif status_filter == "completed": stmt = stmt.where(Order.status.in_(["completed", "partially_completed"]))
    if search: stmt = stmt.where(Order.order_code.ilike(f"%{search}%"))
    res = await session.execute(stmt)
    result = []
    for o in res.scalars().all():
        phones = await order_svc.list_phones(session, o.id)
        result.append({"id": o.id, "code": o.order_code, "item": o.item_name,
                       "price": float(o.total), "status": o.status,
                       "date": o.created_at.strftime("%m-%d %H:%M"),
                       "phones": [p.phone for p in phones]})
    return result


@app.post("/api/admin/order_action")
async def admin_order_action(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = await check_admin(body.get("initData"), session)
    try:
        order = await order_svc.get_order(session, int(body["id"]))
        if not order: raise HTTPException(404, "Order မတွေ့ပါ")
        action = body.get("action")
        reason = body.get("reason", "").strip()
        phones = await order_svc.list_phones(session, order.id)
        pending = [x for x in phones if x.status == "pending"]
        buyer = await user_svc.get_by_id(session, order.user_id)

        for p in pending:
            if action == "done":
                await order_svc.mark_phone_done(session, p.id, tg_user["id"])
                if buyer:
                    await send_tg(buyer.telegram_id, "✅ Data ဖြည့်ပြီးပါပြီ\n\n📱 " + str(p.phone) + "\n📦 " + str(order.item_name))
            elif action == "fail":
                await order_svc.mark_phone_failed(session, p.id, tg_user["id"])
                if buyer:
                    text = "❌ Data ဖြည့်မပေးနိုင်ပါ\n\n📱 " + str(p.phone) + "\n💰 Refund: " + str(int(p.price)) + " Ks"
                    if reason: text += "\n\n📝 အကြောင်းပြချက် - " + reason
                    await send_tg(buyer.telegram_id, text)
        await audit_svc.log(session, tg_user["id"], "order_" + str(action), target_type="order", target_id=order.id)
    except HTTPException: raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(400, "Error: " + str(e))
    return {"status": "ok"}


@app.post("/api/admin/topups")
async def admin_get_topups(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    await check_admin(body.get("initData"), session)
    status_filter = body.get("status", "pending")
    stmt = select(Topup).order_by(Topup.created_at.desc()).limit(50)
    if status_filter in ("pending", "approved", "rejected"): stmt = stmt.where(Topup.status == status_filter)
    res = await session.execute(stmt)
    result = []
    for t in res.scalars().all():
        u = await user_svc.get_by_id(session, t.user_id)
        result.append({"id": t.id, "amount": float(t.amount), "user": u.full_name if u else "Unknown",
                       "sender_phone": t.sender_phone or "", "status": t.status,
                       "ss_url": f"/uploads/{t.ss_file_id}", "date": t.created_at.strftime("%m-%d %H:%M")})
    return result


@app.post("/api/admin/topup_action")
async def admin_topup_action(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = await check_admin(body.get("initData"), session)
    try:
        topup_id = int(body["id"])
        action = body["action"]
        if action == "approve": ok, reason, topup = await topup_svc.approve(session, topup_id, tg_user["id"])
        else: ok, reason, topup = await topup_svc.reject(session, topup_id, tg_user["id"])
        if not ok: raise HTTPException(400, reason)
    except HTTPException: raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(400, "Error: " + str(e))
    return {"status": "ok"}


@app.post("/api/admin/cashouts")
async def admin_get_cashouts(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    await check_admin(body.get("initData"), session)
    res = await session.execute(select(Cashout).where(Cashout.status == "pending").order_by(Cashout.created_at.desc()))
    result = []
    for c in res.scalars().all():
        u = await user_svc.get_by_id(session, c.user_id)
        result.append({"id": c.id, "user": u.full_name if u else "Unknown", "amount": float(c.amount),
                       "account_name": c.account_name, "phone": c.phone, "status": c.status,
                       "date": c.created_at.strftime("%m-%d %H:%M")})
    return result


@app.post("/api/admin/cashout_action")
async def admin_cashout_action(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = await check_admin(body.get("initData"), session)
    cashout_id = int(body["id"])
    action = body["action"]
    if action == "approve": ok, reason, cashout = await cashout_svc.approve(session, cashout_id, tg_user["id"])
    else: ok, reason, cashout = await cashout_svc.reject(session, cashout_id, tg_user["id"])
    if not ok: raise HTTPException(400, reason)
    buyer = await user_svc.get_by_id(session, cashout.user_id)
    if buyer:
        if action == "approve":
            await send_tg(buyer.telegram_id, f"✅ <b>Cash Out အောင်မြင်ပါသည်</b>\n\n💰 {int(cashout.amount):,} Ks")
        else:
            await send_tg(buyer.telegram_id, f"❌ <b>Cash Out ငြင်းပယ်ခံရပါသည်</b>\n\n💰 {int(cashout.amount):,} Ks ကို ပြန်လည်ထည့်သွင်းပေးပြီးပါပြီ။")
    return {"status": "ok"}


@app.post("/api/admin/items/all")
async def admin_get_items(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    await check_admin(body.get("initData"), session)
    items = await item_svc.list_all(session)
    return [{"id": it.id, "name": it.name, "price": float(it.user_price),
             "reseller_price": float(it.reseller_price) if it.reseller_price else None,
             "cost_price": float(it.cost_price) if it.cost_price else None,
             "category": it.category, "subcategory": it.subcategory,
             "status": it.status, "tutorial": it.tutorial_url, "note": it.note or "",
             "form_type": it.form_type} for it in items]


@app.post("/api/admin/item/action")
async def admin_item_action(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = await check_admin(body.get("initData"), session)
    item = await item_svc.get_item(session, int(body["id"]))
    if not item: raise HTTPException(404, "Item မတွေ့ပါ")
    action = body.get("action")
    try:
        if action == "toggle": await item_svc.toggle_status(session, item)
        elif action == "delete": await item_svc.delete_item(session, item)
        elif action == "edit":
            r_price = None
            if body.get("reseller_price") and str(body["reseller_price"]) != "null":
                r_price = Decimal(str(body["reseller_price"]))
            c_price = None
            if body.get("cost_price") and str(body["cost_price"]).strip() != "":
                try: c_price = Decimal(str(body["cost_price"]))
                except: c_price = None
            await item_svc.update_item(session, item,
                user_price=Decimal(str(body["price"])), name=body.get("name"),
                reseller_price=r_price, cost_price=c_price,
                subcategory=body.get("subcategory"), category=body.get("category"),
                note=body.get("note") or None)
        await audit_svc.log(session, tg_user["id"], "item_" + str(action), target_type="item", target_id=item.id)
    except Exception as e:
        await session.rollback()
        raise HTTPException(400, "Error: " + str(e))
    return {"status": "ok"}


@app.post("/api/admin/item/add")
async def admin_add_item(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = await check_admin(body.get("initData"), session)
    name = (body.get("name") or "").strip()
    price = body.get("price")
    category = (body.get("category") or "").strip()
    if not name or not price or not category:
        raise HTTPException(400, "အမည်၊ ဈေးနှုန်းနှင့် အမျိုးအစား အားလုံး ဖြည့်ရပါမည်")
    try:
        r_price = Decimal(str(body["reseller_price"])) if body.get("reseller_price") and str(body["reseller_price"]) != "null" else None
        c_price = Decimal(str(body["cost_price"])) if body.get("cost_price") and str(body["cost_price"]).strip() != "" else None
        item = await item_svc.create_item(session, name=name, code=f"ITM{uuid.uuid4().hex[:6].upper()}",
            description=None, user_price=Decimal(str(price)), cost_price=c_price, category=category,
            subcategory=body.get("subcategory") or None, tutorial_url=body.get("tutorial") or None,
            note=body.get("note") or None, reseller_price=r_price, form_type=body.get("form_type", "phone"))
        await audit_svc.log(session, tg_user["id"], "item_add", target_type="item", target_id=item.id)
    except Exception as e:
        await session.rollback()
        raise HTTPException(400, "Item ထည့်၍ မရပါ: " + str(e))
    return {"status": "ok"}


@app.post("/api/admin/users")
async def admin_get_users(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    await check_admin(body.get("initData"), session)
    search = (body.get("search") or "").strip()
    stmt = select(User).order_by(User.created_at.desc()).limit(50)
    if search: stmt = stmt.where((User.full_name.ilike(f"%{search}%")) | (User.username.ilike(f"%{search}%")))
    res = await session.execute(stmt)
    return [{"id": u.id, "name": u.full_name or "Unknown", "username": u.username or "",
             "role": u.role, "balance": float(u.balance or 0),
             "is_banned": u.is_banned} for u in res.scalars().all()]


@app.post("/api/admin/user/history")
async def admin_user_history(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    await check_admin(body.get("initData"), session)
    user_id = int(body["user_id"])
    txs = await wallet_svc.list_transactions(session, user_id, limit=50)
    return [{"type": t.type, "amount": float(t.amount), "balance_after": float(t.balance_after or 0),
             "date": t.created_at.strftime("%m-%d %H:%M"), "note": t.note} for t in txs]


@app.post("/api/admin/user/action")
async def admin_user_action(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = await check_admin(body.get("initData"), session)
    user = await user_svc.get_by_id(session, int(body["id"]))
    if not user: raise HTTPException(404, "User မတွေ့ပါ")
    action = body.get("action")
    try:
        if action == "make_reseller":
            tier_res = await session.execute(select(Tier.id).limit(1))
            await user_svc.set_role(session, user, "reseller", tier_res.scalar_one_or_none())
        elif action == "remove_reseller": await user_svc.set_role(session, user, "user", None)
        elif action == "ban":
            await user_svc.set_banned(session, user, True)
            res = await session.execute(select(Order).where(Order.user_id == user.id, Order.status.in_(["pending", "processing"])))
            for o in res.scalars().all(): await order_svc.cancel_order(session, o.id, tg_user["id"])
        elif action == "unban": await user_svc.set_banned(session, user, False)
        elif action == "zero_balance":
            current_bal = float(user.balance or 0)
            if current_bal > 0:
                await wallet_svc.deduct_balance(session, user.id, Decimal(str(current_bal)),
                    ref_type="admin_zero", note="Admin: Balance သုည")
        elif action == "remove_balance":
            amt = Decimal(str(body.get("amount", 0)))
            if amt > 0:
                await wallet_svc.deduct_balance(session, user.id, amt,
                    ref_type="admin_remove", note="Admin: Balance ပြန်နုတ်")
        elif action == "adjust_balance":
            amt = Decimal(str(body["amount"]))
            if amt > 0: await wallet_svc.add_balance(session, user.id, amt, ref_type="manual")
            else: await wallet_svc.deduct_balance(session, user.id, abs(amt), ref_type="manual")
        else: raise HTTPException(400, f"Unknown action: {action}")
        await audit_svc.log(session, tg_user["id"], "user_" + str(action), target_type="user", target_id=user.id)
    except HTTPException: raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(400, "Error: " + str(e))
    return {"status": "ok"}


@app.post("/api/admin/settings/all")
async def admin_get_settings(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    await check_admin(body.get("initData"), session)
    keys = ["shop_name", "support_contact", "payment_kpay", "payment_wave", "payment_name",
            "topup_min", "topup_max", "max_pending_topups", "topup_max_file_mb", "auto_cancel_hours",
            "wait_time", "min_cashout"]
    out = {}
    for k in keys:
        v = await settings_svc.get(session, k, "")
        out[k] = v if v is not None and str(v) != "undefined" else ""
    return out


@app.post("/api/admin/settings/update")
async def admin_update_settings(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = await check_admin(body.get("initData"), session)
    for k, v in (body.get("settings") or {}).items():
        await settings_svc.update(session, k, v, tg_user["id"])
    await audit_svc.log(session, tg_user["id"], "settings_update", new_value=body.get("settings") or {})
    return {"status": "ok"}


@app.post("/api/admin/maintenance")
async def admin_maintenance(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = await check_admin(body.get("initData"), session)
    await settings_svc.update(session, "maintenance", body["status"], tg_user["id"])
    return {"status": "ok"}


@app.post("/api/admin/category_image")
async def upload_category_image(request: Request, session: AsyncSession = Depends(get_session)):
    try:
        form = await request.form()
        init_data = form.get("initData")
        if not init_data: raise HTTPException(400, "InitData မပါလာပါ")
        await check_admin(init_data, session)
        name = form.get("name")
        file = form.get("file")
        if not name or not file: raise HTTPException(400, "Category နာမည် သို့မဟုတ် ပုံ မပါလာပါ")
        safe = _safe_slug(name)
        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024: raise HTTPException(400, "ပုံဖိုင် 5 MB ထက် မကြီးရပါ")
        path = os.path.join(UPLOAD_DIR, f"cat_{safe}.png")
        with open(path, "wb") as f: f.write(contents)
        return {"status": "ok", "file": f"cat_{safe}.png"}
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(400, f"ပုံတင်၍ မရပါ: {str(e)}")


@app.post("/api/admin/upload_background")
async def upload_background(request: Request, file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    form = await request.form()
    await check_admin(form.get("initData"), session)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024: raise HTTPException(400, "ပုံဖိုင် 10 MB ထက် မကြီးရပါ")
    with open(os.path.join(UPLOAD_DIR, "bg.jpg"), "wb") as f: f.write(contents)
    return {"status": "ok"}


@app.post("/api/admin/broadcast")
async def admin_broadcast(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    await check_admin(body.get("initData"), session)
    msg = (body.get("message") or "").strip()
    if not msg: raise HTTPException(400, "စာသား မရှိပါ")
    res = await session.execute(select(User).where(User.is_banned == False))
    users = res.scalars().all()
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    sent = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for u in users:
            try:
                r = await client.post(url, json={"chat_id": u.telegram_id, "text": msg, "parse_mode": "HTML"})
                if r.status_code == 200: sent += 1
            except Exception: pass
    return {"status": "ok", "count": sent, "total": len(users)}


@app.post("/api/admin/audit")
async def admin_audit(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    await check_admin(body.get("initData"), session)
    limit = min(int(body.get("limit", 50)), 200)
    logs = await audit_svc.list_logs(session, limit=limit)
    return [{"id": l.id, "admin_id": l.admin_id, "action": l.action,
             "target_type": l.target_type, "target_id": l.target_id,
             "date": l.created_at.strftime("%m-%d %H:%M:%S")} for l in logs]


@app.post("/api/admin/admins/all")
async def get_admins(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = verify_telegram_data(body.get("initData"), config.BOT_TOKEN)
    if not tg_user or not is_super_admin(int(tg_user["id"])): raise HTTPException(403)
    res = await session.execute(select(Admin))
    return [{"id": a.id, "telegram_id": a.telegram_id, "role": a.role, "is_active": a.is_active} for a in res.scalars().all()]


@app.post("/api/admin/admins/add")
async def add_admin(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = verify_telegram_data(body.get("initData"), config.BOT_TOKEN)
    if not tg_user or not is_super_admin(int(tg_user["id"])): raise HTTPException(403)
    new_id = int(body.get("telegram_id", 0))
    if new_id <= 0: raise HTTPException(400, "Telegram ID မမှန်ပါ")
    role = body.get("role", "admin")
    if role not in ("admin", "super_admin"): raise HTTPException(400, "Role မမှန်ပါ")
    chk = await session.execute(select(Admin).where(Admin.telegram_id == new_id))
    if chk.scalar_one_or_none(): raise HTTPException(400, "Already exists")
    session.add(Admin(telegram_id=new_id, role=role, added_by=int(tg_user["id"]), is_active=True))
    await session.commit()
    return {"status": "ok"}


@app.post("/api/admin/admins/delete")
async def delete_admin(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = verify_telegram_data(body.get("initData"), config.BOT_TOKEN)
    if not tg_user or not is_super_admin(int(tg_user["id"])): raise HTTPException(403)
    res = await session.execute(select(Admin).where(Admin.id == int(body["id"])))
    admin = res.scalar_one_or_none()
    if admin:
        await session.delete(admin)
        await session.commit()
    return {"status": "ok"}


@app.post("/api/reports/daily")
async def report_daily(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = verify_telegram_data(body.get("initData"), config.BOT_TOKEN)
    if not tg_user or not is_super_admin(int(tg_user["id"])): raise HTTPException(403)
    date_str = body.get("date")
    if date_str:
        try: target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except: raise HTTPException(400, "ရက်စွဲ မမှန်ပါ")
    else: target_date = datetime.utcnow()
    start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    res = await session.execute(select(Order).where(Order.created_at >= start, Order.created_at < end, Order.status.in_(["completed", "partially_completed"])))
    orders = res.scalars().all()
    total_income = 0; total_cost = 0; total_profit = 0; breakdown = {}
    for o in orders:
        income = float(o.total)
        item = await item_svc.get_item(session, o.item_id)
        cost = float(item.cost_price) * o.qty if (item and item.cost_price) else 0
        profit = income - cost
        total_income += income; total_cost += cost; total_profit += profit
        if o.item_name not in breakdown: breakdown[o.item_name] = {"count": 0, "income": 0, "cost": 0, "profit": 0}
        breakdown[o.item_name]["count"] += o.qty
        breakdown[o.item_name]["income"] += income
        breakdown[o.item_name]["cost"] += cost
        breakdown[o.item_name]["profit"] += profit
    return {"date": start.strftime("%Y-%m-%d"), "total_orders": len(orders),
            "total_income": total_income, "total_cost": total_cost,
            "total_profit": total_profit, "breakdown": breakdown}


@app.post("/api/reports/monthly")
async def report_monthly(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json()
    tg_user = verify_telegram_data(body.get("initData"), config.BOT_TOKEN)
    if not tg_user or not is_super_admin(int(tg_user["id"])): raise HTTPException(403)
    month_str = body.get("month")
    if month_str:
        try: year, month = map(int, month_str.split("-"))
        except: raise HTTPException(400, "လ မမှန်ပါ")
    else:
        now = datetime.utcnow(); year, month = now.year, now.month
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    res = await session.execute(select(Order).where(Order.created_at >= start, Order.created_at < end, Order.status.in_(["completed", "partially_completed"])))
    orders = res.scalars().all()
    total_income = 0; total_cost = 0; total_profit = 0; breakdown = {}
    for o in orders:
        income = float(o.total)
        item = await item_svc.get_item(session, o.item_id)
        cost = float(item.cost_price) * o.qty if (item and item.cost_price) else 0
        profit = income - cost
        total_income += income; total_cost += cost; total_profit += profit
        if o.item_name not in breakdown: breakdown[o.item_name] = {"count": 0, "income": 0, "cost": 0, "profit": 0}
        breakdown[o.item_name]["count"] += o.qty
        breakdown[o.item_name]["income"] += income
        breakdown[o.item_name]["cost"] += cost
        breakdown[o.item_name]["profit"] += profit
    return {"month": f"{year}-{month:02d}", "total_orders": len(orders),
            "total_income": total_income, "total_cost": total_cost,
            "total_profit": total_profit, "breakdown": breakdown}


@app.get("/style.css")
def serve_css(): return FileResponse("webapp/style.css", media_type="text/css")

@app.get("/app.js")
def serve_js(): return FileResponse("webapp/app.js", media_type="application/javascript")

@app.get("/")
def serve_index(): return FileResponse("webapp/index.html", media_type="text/html")
