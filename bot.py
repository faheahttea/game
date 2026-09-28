import logging
import random
import sqlite3
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# تنظیمات لاگینگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# اطلاعات پایه‌ای
TOKEN = "8559844059:AAHzw5hpToGqME76APSQvjfV0AbThOm277s"
OWNER_ID = 8854073031

# اتصال به دیتابیس SQLite
conn = sqlite3.connect("araki_game.db", check_same_thread=False)
cursor = conn.cursor()

# ایجاد جدول کاربران
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    araki INTEGER DEFAULT 0,
    gholami INTEGER DEFAULT 0,
    pouya INTEGER DEFAULT 0,
    last_claim INTEGER DEFAULT 0,
    last_spin INTEGER DEFAULT 0
)
"""
)
conn.commit()

# جدول مدیریت جنگ‌های فعال در گروه‌ها
active_wars = {}


def get_user(user_id, username=""):
  cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
  row = cursor.fetchone()
  if not row:
    cursor.execute(
        "INSERT INTO users (user_id, username, araki) VALUES (?, ?, ?)",
        (user_id, username, 0),
    )
    conn.commit()
    return (user_id, username, 0, 0, 0, 0, 0)
  return row


def update_user(user_id, araki, gholami, pouya):
  cursor.execute(
      "UPDATE users SET araki = ?, gholami = ?, pouya = ? WHERE user_id = ?",
      (araki, gholami, pouya, user_id),
  )
  conn.commit()


def calculate_total_power(user_id, araki, gholami, pouya):
  if user_id == OWNER_ID:
    return 9999999
  # قدرت واحدها: اراکی = 44، غلامی = 60، پویا = 80
  return (araki * 44) + (gholami * 60) + (pouya * 80)


def calculate_total_soldiers(user_id, araki, gholami, pouya):
  if user_id == OWNER_ID:
    return 999999999
  return araki + (gholami * 30) + (pouya * 50)


# ۱. تغییر استارت در پی‌وی (فقط دکمه افزودن به گروه)
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if update.effective_chat.type == "private":
    keyboard = [
        [
            InlineKeyboardButton(
                "➕ افزودن ربات به گروه و مدیریت",
                url=f"https://t.me/{context.bot.username}?startgroup=true",
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎮 **به بازی اراکی‌ها خوش آمدید!**\n\n"
        "برای شروع، لطفاً روی دکمه زیر کلیک کرده و ربات را به گروه خود اضافه کنید.",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


# دستورات اصلی متنی (بدون اسلش)
async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if not update.message or not update.message.text:
    return

  text = update.message.text.strip()
  user = update.effective_user
  user_id = user.id
  username = user.username or user.first_name

  user_data = get_user(user_id, username)
  now = int(time.time())

  # ۲. دستور راهنما
  if text in ["راهنما", "دستورات", "help"]:
    await update.message.reply_text(
        "📖 **راهنمای جامع بازی اراکی‌ها:**\n\n"
        "🔹 `اراکی` - دریافت نیروی رایگان (هر ۵ دقیقه)\n"
        "🔹 `موجودی` - نمایش تعداد دقیق سربازان و واحدها\n"
        "🔹 `قدرت` - نمایش قدرت کل ارتش\n"
        "🔹 `گردونه` - شانس امتحان کردن و گرفتن جایزه\n"
        "🔹 `تقویت نیرو` - تبدیل ۱۰۰ اراکی به ۱ غلامی (قدرت ۶۰)\n"
        "🔹 `تقویت غلامی` - تبدیل ۳۰ غلامی به ۱ پویا (قدرت ۸۰)\n"
        "🔹 `خرید نیرو [تعداد]` - خرید اراکی\n"
        "🔹 `جنگ [مبلغ]` - ایجاد مسابقه جنگی در گروه\n"
        "🔹 `حمله` - حمله با تمام نیرو به مخاطب (ریپلی روی پیام فرد مورد نظر)\n"
        "🔹 `انتقال [تعداد]` - هدیه نیرو به دیگران (ریپلی روی پیام فرد)",
        parse_mode="Markdown",
    )

  # ۳. دستور موجودی
  elif text == "موجودی":
    await update.message.reply_text(
        f"📊 **موجودی ارتش {user.first_name}:**\n\n"
        f"🔸 اراکی‌ها: {user_data[2]}\n"
        f"🔹 غلامی‌ها: {user_data[3]}\n"
        f"🚀 پویایی‌ها: {user_data[4]}\n"
        f"👥 مجموع سربازان جنگی: {calculate_total_soldiers(user_id, user_data[2], user_data[3], user_data[4])}",
        parse_mode="Markdown",
    )

  # ۴. دستور قدرت
  elif text == "قدرت":
    total_pow = calculate_total_power(user_id, user_data[2], user_data[3], user_data[4])
    keyboard = [[InlineKeyboardButton(f"🟢 قدرت کل ارتش: {total_pow}", callback_data="none")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🛡️ **جزئیات قدرت ارتش {user.first_name}:**\n"
        f"🔸 هر اراکی: 44 واحد\n"
        f"🔹 هر غلامی: 60 واحد\n"
        f"🚀 هر پویا: 80 واحد\n\n"
        f"✨ قدرت کلی شما: **{total_pow}**",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  # ۵. دستور اراکی
  elif text == "اراکی":
    if user_id == OWNER_ID:
      update_user(user_id, user_data[2] + 1000, user_data[3], user_data[4])
      await update.message.reply_text("👑 مالک بزرگ! 1000 نیروی اراکی به حساب شما اضافه شد.")
      return

    last_claim = user_data[5]
    if now - last_claim < 300:
      remaining = 300 - (now - last_claim)
      mins = remaining // 60
      secs = remaining % 60
      await update.message.reply_text(
          f"⏳ باید صبر کنید! هر ۵ دقیقه یکبار می‌توانید نیرو بگیرید.\nزمان باقی‌مانده: {mins} دقیقه و {secs} ثانیه."
      )
      return

    gained = random.randint(5, 15)
    cursor.execute(
        "UPDATE users SET araki = araki + ?, last_claim = ? WHERE user_id = ?",
        (gained, now, user_id),
    )
    conn.commit()
    await update.message.reply_text(
        f"به بازی اراکی ها خوش امدید! 🎉\n{gained} نیروی اراکی به ارتش شما اضافه شد."
    )

  # خرید نیرو
  elif text.startswith("خرید نیرو"):
    parts = text.split()
    if len(parts) < 3 or not parts[2].isdigit():
      await update.message.reply_text(
          "⚠️ فرمت اشتباه! مثال: `خرید نیرو 50`", parse_mode="Markdown"
      )
      return
    count = int(parts[2])
    update_user(user_id, user_data[2] + count, user_data[3], user_data[4])
    await update.message.reply_text(f"✅ تعداد {count} نیروی اراکی خریداری شد!")

  # گردونه
  elif text == "گردونه":
    rand_val = random.random() * 100
    if rand_val <= 1:
      prize = 5000
      msg = "🌟 فوق‌العاده کمیاب! ۵۰۰۰ نیرویی (۱٪)!"
    elif rand_val <= 10:
      prize = 1000
      msg = "🔥 عالی! ۱۰۰۰ نیرو برنده شدید!"
    elif rand_val <= 40:
      prize = 100
      msg = "✨ ۱۰۰ نیرو برنده شدید!"
    elif rand_val <= 85:
      prize = 50
      msg = "⭐ ۵۰ نیرو برنده شدید!"
    else:
      prize = 1
      msg = "💫 شانس یار نبود، ۱ نیرو!"

    update_user(user_id, user_data[2] + prize, user_data[3], user_data[4])
    cursor.execute(
        "UPDATE users SET last_spin = ? WHERE user_id = ?", (now, user_id)
    )
    conn.commit()
    await update.message.reply_text(
        f"🎡 **گردونه شانس:**\n{msg}\n🎁 پاداش: {prize} اراکی",
        parse_mode="Markdown",
    )

  # ۶. تقویت نیرو (۱۰۰ اراکی -> ۱ غلامی)
  elif text == "تقویت نیرو":
    if user_id != OWNER_ID and user_data[2] < 100:
      await update.message.reply_text("⚠️ کمبود نیرو! حداقل به 100 نیروی اراکی نیاز دارید.")
      return

    if user_id != OWNER_ID:
      update_user(user_id, user_data[2] - 100, user_data[3] + 1, user_data[4])
    else:
      update_user(user_id, user_data[2], user_data[3] + 1, user_data[4])

    await update.message.reply_text(
        "⚡ تقویت انجام شد!\n100 اراکی مصرف شد و **1 غلامی** (قدرت: 60) اضافه شد.",
        parse_mode="Markdown",
    )

  # ۷. تقویت غلامی (۳۰ غلامی -> ۱ پویا - همراه با کسر ۳۰ غلامی)
  elif text == "تقویت غلامی":
    if user_id != OWNER_ID and user_data[3] < 30:
      await update.message.reply_text("⚠️ کمبود نیرو! حداقل به 30 غلامی نیاز دارید.")
      return

    if user_id != OWNER_ID:
      update_user(user_id, user_data[2], user_data[3] - 30, user_data[4] + 1)
    else:
      update_user(user_id, user_data[2], user_data[3], user_data[4] + 1)

    await update.message.reply_text(
        "🚀 تقویت نسخه ۲ انجام شد!\n30 غلامی کسر شد و **1 نیروی پویا** (قدرت: 80) اضافه شد.",
        parse_mode="Markdown",
    )

  # ۸. دستور جنگ با جوایز پله‌ای خواسته شده
  elif text.startswith("جنگ"):
    if update.effective_chat.type == "private":
      await update.message.reply_text("⚠️ دستور جنگ فقط در گروه‌ها قابل اجراست!")
      return

    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
      await update.message.reply_text("⚠️ فرمت اشتباه. مثال: `جنگ 20`", parse_mode="Markdown")
      return

    bet = int(parts[1])
    total_soliders = calculate_total_soldiers(user_id, user_data[2], user_data[3], user_data[4])
    
    # پیام کمبود نیرو در صورت نداشتن موجودی کافی برای بازی
    if user_id != OWNER_ID and total_soliders < bet:
      await update.message.reply_text(f"⚠️ موجودی شما برای این بازی کافی نیست! موجودی فعلی: {total_soliders}")
      return

    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("⚔️ ورودی به بازی", callback_data=f"join_war_{chat_id}_{bet}")],
        [InlineKeyboardButton("❌ لغو بازی", callback_data=f"cancel_war_{chat_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # تعیین جایزه پله‌ای خواسته شده
    if bet <= 10:
      prize = 18
    elif bet <= 20:
      prize = 38
    elif bet <= 30:
      prize = 58
    elif bet <= 40:
      prize = 78
    else:
      prize = int(bet * 1.98) # تا 1000 و بیشتر مقادیر تصاعدی

    sent_msg = await update.message.reply_text(
        f"⚔️ **درخواست جنگ جدید!**\n\n"
        f"👤 سازنده بازی: {user.first_name}\n"
        f"🎯 تعداد نیرو (ورودی): {bet}\n"
        f"🏆 جایزه برنده: {prize} اراکی به همراه بازگشت ورودی‌ها\n\n"
        f"برای ورود روی دکمه زیر کلیک کنید:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

    active_wars[chat_id] = {
        "creator_id": user_id,
        "creator_name": user.first_name,
        "bet": bet,
        "prize": prize,
        "message_id": sent_msg.message_id,
    }

  # ۹. دستور حمله با تمام نیرو (بر اساس قدرت و واحدهای تقویت‌شده + تلفات شانسی + گرفتن ۱/۳ نیرو)
  elif text == "حمله":
    if update.effective_chat.type == "private":
      await update.message.reply_text("⚠️ دستور حمله فقط در داخل گروه‌ها قابل اجراست!")
      return

    if not update.message.reply_to_message:
      await update.message.reply_text("⚠️ برای حمله باید روی پیام کاربر مورد نظر ریپلی کنید!")
      return

    target_user = update.message.reply_to_message.from_user
    if target_user.id == user_id:
      await update.message.reply_text("⚠️ نمی‌توانید به خودتان حمله کنید!")
      return

    attacker_data = user_data
    target_data = get_user(target_user.id, target_user.username or target_user.first_name)

    attacker_power = calculate_total_power(user_id, attacker_data[2], attacker_data[3], attacker_data[4])
    target_power = calculate_total_power(target_user.id, target_data[2], target_data[3], target_data[4])

    if attacker_power <= 0:
      await update.message.reply_text("⚠️ شما هیچ نیرویی برای حمله ندارید!")
      return

    # مقایسه قدرت‌ها برای تعیین برنده حمله
    if attacker_power >= target_power:
      winner_id, loser_id = user_id, target_user.id
      winner_name, loser_name = user.first_name, target_user.first_name
      winner_data, loser_data = attacker_data, target_data
    else:
      winner_id, loser_id = target_user.id, user_id
      winner_name, loser_name = target_user.first_name, user.first_name
      winner_data, loser_data = target_data, attacker_data

    # برنده 1/3 نیروهای بازنده را می‌گیرد
    loot_araki = int(loser_data[2] * 0.33)
    loot_gholami = int(loser_data[3] * 0.33)
    loot_pouya = int(loser_data[4] * 0.33)

    # تلفات شانسی حمله برای مهاجم/برنده
    casualty_loss = random.randint(1, 5)

    # بروزرسانی دیتابیس برنده و بازنده
    if user_id != OWNER_ID and target_user.id != OWNER_ID:
      update_user(loser_id, max(0, loser_data[2] - loot_araki), max(0, loser_data[3] - loot_gholami), max(0, loser_data[4] - loot_pouya))
      update_user(winner_id, winner_data[2] + loot_araki - casualty_loss, winner_data[3] + loot_gholami, winner_data[4] + loot_pouya)

    up_attacker = get_user(user_id)
    up_target = get_user(target_user.id)

    await update.message.reply_text(
        f"⚔️ **جنگ و حمله تمام‌عیار به پایان رسید!**\n\n"
        f"🏆 **پیروز میدان:** {winner_name}\n"
        f"💀 **شکست‌خورده:** {loser_name}\n\n"
        f"🎁 غنائم جنگی به سرقت رفته: {loot_araki} اراکی، {loot_gholami} غلامی\n"
        f"💥 تلفات تصادفی درگیری: {casualty_loss} نیرو\n\n"
        f"📊 **موجودی جدید دو طرف:**\n"
        f"👤 {user.first_name} ➔ اراکی: {up_attacker[2]} | غلامی: {up_attacker[3]}\n"
        f"👤 {target_user.first_name} ➔ اراکی: {up_target[2]} | غلامی: {up_target[3]}",
        parse_mode="Markdown",
    )

  # ۱۰. دستور انتقال نیرو
  elif text.startswith("انتقال") or text.startswith("انتشار"):
    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
      await update.message.reply_text("⚠️ فرمت اشتباه! مثال: `انتقال 20`", parse_mode="Markdown")
      return

    transfer_amount = int(parts[1])
    if not update.message.reply_to_message:
      await update.message.reply_text("⚠️ باید روی پیام کاربر ریپلی کنید!")
      return

    target_user = update.message.reply_to_message.from_user
    if target_user.id == user_id:
      await update.message.reply_text("⚠️ نمی‌توانید به خودتان نیرو انتقال دهید!")
      return

    target_data = get_user(target_user.id, target_user.username or target_user.first_name)

    if user_id != OWNER_ID:
      sender_total = calculate_total_soldiers(user_id, user_data[2], user_data[3], user_data[4])
      if sender_total < transfer_amount:
        await update.message.reply_text("⚠️ موجودی سربازهای شما برای این انتقال کافی نیست!")
        return
      update_user(user_id, max(0, user_data[2] - transfer_amount), user_data[3], user_data[4])

    update_user(target_user.id, target_data[2] + transfer_amount, target_data[3], target_data[4])

    updated_sender = get_user(user_id)
    updated_target = get_user(target_user.id)

    await update.message.reply_text(
        f"📤 **انتقال نیرو انجام شد!**\n\n"
        f"🔹 تعداد انتقال: {transfer_amount}\n"
        f"👤 فرستنده ({user.first_name}) - موجودی باقی‌مانده: {updated_sender[2]}\n"
        f"👤 گیرنده ({target_user.first_name}) - موجودی جدید: {updated_target[2]}",
        parse_mode="Markdown",
    )


# مدیریت دکمه‌های شیشه‌ای جنگ با نمایش کامل موجودی جدید دو طرف
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  data = query.data
  chat_id = query.message.chat_id
  user = query.from_user
  user_id = user.id

  if data.startswith("join_war_"):
    parts = data.split("_")
    bet = int(parts[3]) if len(parts) > 3 else 20

    if chat_id not in active_wars:
      await query.edit_message_text("❌ این بازی به اتمام رسیده یا منقضی شده است.")
      return

    war = active_wars[chat_id]
    if user_id == war["creator_id"]:
      await query.answer("شما سازنده این بازی هستید!", show_alert=True)
      return

    creator_id = war["creator_id"]
    prize = war["prize"]

    joiner_data = get_user(user_id, user.username or user.first_name)
    joiner_total = calculate_total_soldiers(user_id, joiner_data[2], joiner_data[3], joiner_data[4])
    
    if user_id != OWNER_ID and joiner_total < bet:
      await query.answer("موجودی شما برای این بازی کافی نیست!", show_alert=True)
      return

    creator_data = get_user(creator_id)

    if creator_id != OWNER_ID:
      update_user(creator_id, max(0, creator_data[2] - bet), creator_data[3], creator_data[4])
    if user_id != OWNER_ID:
      update_user(user_id, max(0, joiner_data[2] - bet), joiner_data[3], joiner_data[4])

    winner_id = random.choice([creator_id, user_id])
    loser_id = user_id if winner_id == creator_id else creator_id

    winner_data = get_user(winner_id)
    update_user(winner_id, winner_data[2] + bet + prize, winner_data[3], winner_data[4])

    winner_name = war["creator_name"] if winner_id == creator_id else user.first_name
    loser_name = user.first_name if winner_id == creator_id else war["creator_name"]

    del active_wars[chat_id]

    # گرفتن موجودی به‌روز شده برای نمایش در انتهای پیام جنگ
    c_final = get_user(creator_id)
    j_final = get_user(user_id)

    await query.edit_message_text(
        f"⚔️ **نتیجه جنگ اعلام شد!**\n\n"
        f"🏆 **برنده:** {winner_name}\n"
        f"💀 **بازنده:** {loser_name}\n\n"
        f"🎁 پاداش برنده: {prize} اراکی به همراه بازگشت ورودی‌ها\n"
        f"📊 موجودی سربازان دو طرف بروزرسانی شد.\n\n"
        f"🔹 موجودی جدید سازنده ({war['creator_name']}): {c_final[2]} اراکی\n"
        f"🔹 موجودی جدید شرکت‌کننده ({user.first_name}): {j_final[2]} اراکی",
        parse_mode="Markdown",
    )

  elif data.startswith("cancel_war_"):
    if chat_id not in active_wars:
      await query.edit_message_text("❌ بازی وجود ندارد.")
      return

    war = active_wars[chat_id]
    if user_id != war["creator_id"] and user_id != OWNER_ID:
      await query.answer("فقط سازنده بازی می‌تواند آن را لغو کند!", show_alert=True)
      return

    del active_wars[chat_id]
    await query.edit_message_text("🚫 بازی توسط سازنده لغو شد.")


def main():
  app = ApplicationBuilder().token(TOKEN).build()

  app.add_handler(MessageHandler(filters.COMMAND & filters.Regex("^/start$"), start_handler))
  app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
  app.add_handler(CallbackQueryHandler(button_handler))

  print("🤖 Bot is running and ready...")
  app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
  main()
