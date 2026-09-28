import logging
import os
import random
import sqlite3
import time
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
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
PORT = int(os.environ.get("PORT", 8080))

# راه‌اندازی Flask برای دریافت وب‌هوک
app_flask = Flask(__name__)

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
  return (araki * 44) + (gholami * 60) + (pouya * 78)


def calculate_total_soldiers(user_id, araki, gholami, pouya):
  if user_id == OWNER_ID:
    return 999999999
  return araki + (gholami * 30) + (pouya * 50)


# هندلر استارت در پی‌وی
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
        "برای شروع، لطفاً ربات را به گروه خود اضافه کرده و آن را **مدیر (Admin)** کنید.\n"
        "سپس در گروه با دستورات بازی (بدون اسلش) مثل `اراکی`، `گردونه`، `جنگ 20` و... بازی کنید.",
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

  # ۱. دستور: اراکی
  if text == "اراکی":
    if user_id == OWNER_ID:
      update_user(user_id, user_data[2] + 1000, user_data[3], user_data[4])
      await update.message.reply_text(
          "👑 مالک بزرگ! 1000 نیروی اراکی به حساب شما اضافه شد."
      )
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

  # ۲. دستور: خرید نیرو
  elif text.startswith("خرید نیرو"):
    parts = text.split()
    if len(parts) < 3 or not parts[2].isdigit():
      await update.message.reply_text(
          "⚠️ فرمت اشتباه! مثال: `خرید نیرو 50`", parse_mode="Markdown"
      )
      return
    count = int(parts[2])
    update_user(user_id, user_data[2] + count, user_data[3], user_data[4])
    await update.message.reply_text(
        f"✅ تعداد {count} نیروی اراکی خریداری شد!"
    )

  # ۳. دستور: گردونه
  elif text == "گردونه":
    rand_val = random.random() * 100
    if rand_val <= 1:
      prize = 5000
      msg = "🌟 فوق‌العاده کمیاب! برنده جایزه افسانه‌ای ۵۰۰۰ نیرویی شدید (۱٪)!"
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
      msg = "💫 شانس با شما یار نبود، ۱ نیرو برنده شدید!"

    update_user(user_id, user_data[2] + prize, user_data[3], user_data[4])
    cursor.execute(
        "UPDATE users SET last_spin = ? WHERE user_id = ?", (now, user_id)
    )
    conn.commit()
    await update.message.reply_text(
        f"🎡 **گردونه شانس اراکی‌ها:**\n{msg}\n🎁 پاداش: {prize} اراکی",
        parse_mode="Markdown",
    )

  # ۴. دستور: تقویت نیرو (تبدیل ۱۰۰ اراکی به ۱ غلامی)
  elif text == "تقویت نیرو":
    if user_id != OWNER_ID and user_data[2] < 100:
      await update.message.reply_text(
          "⚠️ برای تقویت نیرو به غلامی، حداقل به 100 نیروی اراکی نیاز دارید!"
      )
      return

    if user_id != OWNER_ID:
      update_user(user_id, user_data[2] - 100, user_data[3] + 1, user_data[4])
    else:
      update_user(user_id, user_data[2], user_data[3] + 1, user_data[4])

    await update.message.reply_text(
        "⚡ تقویت انجام شد!\n100 نیروی اراکی مصرف شد و **1 غلامی** (قدرت: 60) اضافه شد.",
        parse_mode="Markdown",
    )

  # ۵. دستور: تقویت غلامی (تبدیل ۳۰ غلامی به ۱ پویا)
  elif text == "تقویت غلامی":
    if user_id != OWNER_ID and user_data[3] < 30:
      await update.message.reply_text(
          "⚠️ برای تقویت غلامی به پویا، حداقل به 30 غلامی نیاز دارید!"
      )
      return

    if user_id != OWNER_ID:
      update_user(user_id, user_data[2], user_data[3] - 30, user_data[4] + 1)
    else:
      update_user(user_id, user_data[2], user_data[3], user_data[4] + 1)

    await update.message.reply_text(
        "🚀 تقویت نسخه ۲ انجام شد!\n30 غلامی مصرف شد و **1 نیروی پویا** (قدرت: 78) اضافه شد.",
        parse_mode="Markdown",
    )

  # ۶. دستور: قدرت تیم
  elif text == "قدرت تیم":
    total_pow = calculate_total_power(user_id, user_data[2], user_data[3], user_data[4])
    keyboard = [[InlineKeyboardButton(f"🟢 قدرت تیم: {total_pow}", callback_data="none")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🛡️ **وضعیت ارتش {user.first_name}:**\n"
        f"🔸 اراکی‌ها: {user_data[2]}\n"
        f"🔹 غلامی‌ها: {user_data[3]}\n"
        f"🚀 پویایی‌ها: {user_data[4]}",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

  # ۷. دستور: جنگ
  elif text.startswith("جنگ"):
    if update.effective_chat.type == "private":
      await update.message.reply_text("⚠️ دستور جنگ فقط در داخل گروه‌ها قابل اجراست!")
      return

    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
      await update.message.reply_text(
          "⚠️ فرمت دستور جنگ اشتباه است. مثال: `جنگ 20`", parse_mode="Markdown"
      )
      return

    bet = int(parts[1])
    total_soliders = calculate_total_soldiers(user_id, user_data[2], user_data[3], user_data[4])
    if user_id != OWNER_ID and total_soliders < bet:
      await update.message.reply_text(
          f"⚠️ نیروی شما کافی نیست! موجودی کل شما ({total_soliders}) کمتر از مبلغ ورودی ({bet}) است."
      )
      return

    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("⚔️ ورود به بازی", callback_data=f"join_war_{chat_id}")],
        [InlineKeyboardButton("❌ لغو بازی", callback_data=f"cancel_war_{chat_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_msg = await update.message.reply_text(
        f"⚔️ **درخواست جنگ جدید!**\n\n"
        f"👤 سازنده بازی: {user.first_name}\n"
        f"🎯 تعداد نیرو (ورودی): {bet}\n"
        f"🏆 جایزه برنده: 35 اراکی\n\n"
        f"برای ورود روی دکمه زیر کلیک کنید:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

    active_wars[chat_id] = {
        "creator_id": user_id,
        "creator_name": user.first_name,
        "bet": bet,
        "message_id": sent_msg.message_id,
    }

  # ۸. دستور: انتقال نیرو
  elif text.startswith("انتقال") or text.startswith("انتشار"):
    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
      await update.message.reply_text(
          "⚠️ فرمت اشتباه! مثال: `انتقال 20` (روی پیام طرف مقابل ریپلی کنید)",
          parse_mode="Markdown",
      )
      return

    transfer_amount = int(parts[1])
    if not update.message.reply_to_message:
      await update.message.reply_text(
          "⚠️ برای انتقال نیرو حتماً باید روی پیام کاربر مورد نظر ریپلی کنید!"
      )
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
        f"📤 **انتقال نیرو با موفقیت انجام شد!**\n\n"
        f"🔹 تعداد انتقال‌یافته: {transfer_amount}\n"
        f"👤 فرستنده ({user.first_name}) - باقی‌مانده: {updated_sender[2]}\n"
        f"👤 گیرنده ({target_user.first_name}) - موجودی جدید: {updated_target[2]}",
        parse_mode="Markdown",
    )


# مدیریت دکمه‌های شیشه‌ای
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  data = query.data
  chat_id = query.message.chat_id
  user = query.from_user
  user_id = user.id

  if data.startswith("join_war_"):
    if chat_id not in active_wars:
      await query.edit_message_text("❌ این بازی به اتمام رسیده یا منقضی شده است.")
      return

    war = active_wars[chat_id]
    if user_id == war["creator_id"]:
      await query.answer("شما سازنده این بازی هستید!", show_alert=True)
      return

    bet = war["bet"]
    creator_id = war["creator_id"]

    joiner_data = get_user(user_id, user.username or user.first_name)
    joiner_total = calculate_total_soldiers(user_id, joiner_data[2], joiner_data[3], joiner_data[4])
    if user_id != OWNER_ID and joiner_total < bet:
      await query.answer("موجودی شما کافی نیست!", show_alert=True)
      return

    creator_data = get_user(creator_id)

    if creator_id != OWNER_ID:
      update_user(creator_id, max(0, creator_data[2] - bet), creator_data[3], creator_data[4])
    if user_id != OWNER_ID:
      update_user(user_id, max(0, joiner_data[2] - bet), joiner_data[3], joiner_data[4])

    winner_id = random.choice([creator_id, user_id])
    loser_id = user_id if winner_id == creator_id else creator_id

    winner_data = get_user(winner_id)
    prize = 35
    update_user(winner_id, winner_data[2] + bet + prize, winner_data[3], winner_data[4])

    winner_name = war["creator_name"] if winner_id == creator_id else user.first_name
    loser_name = user.first_name if winner_id == creator_id else war["creator_name"]

    del active_wars[chat_id]

    await query.edit_message_text(
        f"⚔️ **نتیجه جنگ اعلام شد!**\n\n"
        f"🏆 **برنده:** {winner_name}\n"
        f"💀 **بازنده:** {loser_name}\n\n"
        f"🎁 پاداش برنده: {prize} اراکی",
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


# راه‌اندازی اپلیکیشن تلگرام و اتصال به فلاسک
application = Application.builder().token(TOKEN).build()
application.add_handler(MessageHandler(filters.COMMAND & filters.Regex("^/start$"), start_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
application.add_handler(CallbackQueryHandler(button_handler))


@app_flask.route("/", methods=["POST"])
def webhook():
  """دریافت آپدیت‌ها از تلگرام و ارسال به ربات"""
  if request.headers.get("content-type") == "application/json":
    json_string = request.get_data().decode("utf-8")
    update = Update.de_json(json_string, application.bot)
    application.update_queue.put_nowait(update)
    return "ok"
  return "ok"


@app_flask.route("/", methods=["GET"])
def index():
  return "Bot is running on Webhook!"


async def main():
  await application.initialize()
  await application.start()
  # اجرای سرور فلاسک روی پورت رایلی
  app_flask.run(host="0.0.0.0", port=PORT)


if __name__ == "__main__":
  import asyncio

  asyncio.run(main())
