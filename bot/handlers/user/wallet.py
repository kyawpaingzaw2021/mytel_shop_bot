from decimal import Decimal

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards.reply import main_menu, cancel_menu
from bot.states.order import TopupFlow
from services import wallet as wallet_svc
from services import topup as topup_svc
from services import settings as settings_svc
from services import notification as notif

router = Router(name="user_wallet")


@router.message(F.text == "💰 Wallet")
async def show_wallet(message: Message, session, user=None):
    if user is None:
        await message.answer("❌ Admin account အတွက် wallet မရှိပါ")
        return

    balance = await wallet_svc.get_balance(session, user.id)
    txs = await wallet_svc.list_transactions(session, user.id, limit=5)

    lines = [
        "💰 Wallet",
        "",
        f"💵 လက်ရှိ Balance: {int(balance):,} Ks",
        "",
    ]
    if txs:
        lines.append("📜 နောက်ဆုံး ငွေလှုပ်ရှားမှု:")
        for tx in txs:
            sign = "+" if tx.amount > 0 else ""
            lines.append(
                f"• {tx.type}: {sign}{int(tx.amount):,} Ks "
                f"({tx.created_at.strftime('%m-%d %H:%M')})"
            )
    lines.append("")
    lines.append("💰 ငွေဖြည့်ရန် /topup ရိုက်ပါ")

    await message.answer("\n".join(lines), reply_markup=main_menu())


async def start_topup(message: Message, state: FSMContext, session, user):
    kpay = await settings_svc.get(session, "payment_kpay", "")
    wave = await settings_svc.get(session, "payment_wave", "")
    name = await settings_svc.get(session, "payment_name", "")
    min_amt = int(await settings_svc.get(session, "topup_min", 1000))

    lines = ["💰 ငွေဖြည့်ရန်", ""]
    if kpay:
        lines.append(f"💳 KPay — {kpay}")
    if wave:
        lines.append(f"💳 Wave — {wave}")
    if name:
        lines.append(f"👤 Name — {name}")
    lines.append("")
    lines.append(f"📝 အနည်းဆုံး {min_amt:,} Ks")
    lines.append("")
    lines.append("1️⃣ Amount ရိုက်ထည့်ပါ")
    lines.append("2️⃣ Screenshot ပို့ပါ")
    lines.append("")
    lines.append("💰 Amount ရိုက်ထည့်ပါ (Ks)")

    await state.set_state(TopupFlow.enter_amount)
    await message.answer("\n".join(lines), reply_markup=cancel_menu())


@router.message(F.text == "/topup")
async def cmd_topup(message: Message, state: FSMContext, session, user=None):
    if user is None:
        return
    await start_topup(message, state, session, user)


@router.message(TopupFlow.enter_amount)
async def enter_amount(message: Message, state: FSMContext, session):
    text = (message.text or "").strip()
    if text == "❌ ပယ်မယ်":
        await state.clear()
        await message.answer("ပယ်လိုက်ပါပြီ", reply_markup=main_menu())
        return

    try:
        amount = Decimal(text.replace(",", ""))
    except Exception:
        await message.answer("❌ Amount မှားနေပါတယ်")
        return

    min_amt = int(await settings_svc.get(session, "topup_min", 1000))
    max_amt = int(await settings_svc.get(session, "topup_max", 1000000))

    if amount < min_amt:
        await message.answer(f"❌ အနည်းဆုံး {min_amt:,} Ks")
        return
    if amount > max_amt:
        await message.answer(f"❌ အများဆုံး {max_amt:,} Ks")
        return

    await state.update_data(amount=str(amount))
    await state.set_state(TopupFlow.send_screenshot)
    await message.answer(
        f"💰 Amount: {int(amount):,} Ks\n\n"
        f"📸 ယခု Screenshot ပို့ပါ",
        reply_markup=cancel_menu(),
    )


@router.message(TopupFlow.send_screenshot, F.photo)
async def receive_screenshot(message: Message, state: FSMContext, session, user=None, bot=None):
    data = await state.get_data()
    amount = Decimal(data["amount"])
    file_id = message.photo[-1].file_id

    if await topup_svc.check_duplicate_ss(session, file_id):
        await message.answer("❌ ဒီ Screenshot ကို တင်ပြီးသားပါ")
        return

    topup = await topup_svc.create_topup(session, user.id, amount, file_id)
    await state.clear()

    await message.answer(
        f"✅ တင်ပြီးပါပြီ\n\n"
        f"🧾 Topup #{topup.id}\n"
        f"💰 {int(amount):,} Ks\n\n"
        f"⏳ Admin မှ စစ်ဆေးပေးပါမည်",
        reply_markup=main_menu(),
    )

    if bot:
        from bot.keyboards.inline import topup_actions_kb
        text = (
            f"🆕 Topup #{topup.id}\n\n"
            f"👤 {user.full_name or '-'} (ID: {user.telegram_id})\n"
            f"💰 Amount: {int(amount):,} Ks\n"
            f"🕐 {topup.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
        await notif.send_admin_group(
            bot, text, reply_markup=topup_actions_kb(topup.id)
        )
        await notif.send_admin_group(
            bot,
            f"📸 Topup #{topup.id} — Screenshot",
        )
        try:
            await bot.send_photo(
                chat_id=__import__("core.config", fromlist=["config"]).config.ADMIN_GROUP_ID,
                photo=file_id,
            )
        except Exception:
            pass


@router.message(TopupFlow.send_screenshot)
async def need_photo(message: Message):
    await message.answer("❌ Screenshot (photo) ပဲ ပို့ပါ")
