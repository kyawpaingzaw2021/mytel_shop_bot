from aiogram import Router, F
from aiogram.types import Message

from services import order as order_svc
from bot.keyboards.reply import main_menu

router = Router(name="user_history")


@router.message(F.text == "📜 History")
async def show_history(message: Message, session, user=None):
    if user is None:
        await message.answer("❌ Admin account အတွက် history မရှိပါ")
        return

    orders = await order_svc.list_user_orders(session, user.id, limit=10)
    if not orders:
        await message.answer("📜 Order history မရှိသေးပါ", reply_markup=main_menu())
        return

    status_icon = {
        "pending": "⏳",
        "processing": "🔄",
        "completed": "✅",
        "partially_completed": "⚠️",
        "cancelled": "❌",
    }

    lines = ["📜 Order History", ""]
    for o in orders:
        icon = status_icon.get(o.status, "•")
        lines.append(
            f"{icon} {o.order_code} — {o.item_name} × {o.qty}\n"
            f"   💰 {int(o.total):,} Ks | {o.created_at.strftime('%m-%d %H:%M')}"
        )

    await message.answer("\n".join(lines), reply_markup=main_menu())
