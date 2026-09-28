import logging
import random
import sqlite3
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
# {chat_id: {"creator_id": int, "creator_name": str, "bet": int, "message_id": int}}
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


def calculate_total_power(araki, gholami, pouya):
  # قدرت واحدها: اراکی = 44، غلامی = 60، پویا = 78
  return (araki * 44) + (gholami * 60) + (pouya * 78)


def calculate_total_soldiers(araki, gholami, pouya):
  # هر غلامی معادل 30 سرباز، هر پویا معادل 50 سرباز، هر اراکی 1 سرباز
  if user_id_is_owner(0):  # بررسی مالک در جای دیگر
    pass
  return araki + (gholami * 30) + (pouya * 50)


def is_owner(user_id):
  return user_id == OWNER_ID


# هندلر استارت در پی‌وی
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if update.effective_chat.type == "private":
    keyboard = [
        [
            InlineKeyboardButton(
                "➕ افزودن ربات به گروه",
                url=f"https://t.me/{context.bot.username}?startgroup=true",
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎮 **به بازی اراکی‌ها خوش آمدید!**\n\n"
        "برای شروع، لطفاً ربات را به گروه خود اضافه کرده و آن را **مدیر (Admin)** کنید تا دستورات بازی بهرانگیزش کار کنند.",
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

  # بررسی و ثبت کاربر
  user_data = get_user(user_id, username)
  # user_data: (user_id, username, araki, gholami, pouya, last_claim, last_spin)

  # ۱. دستور: اراکی (دریافت نیرو هر ۵ دقیقه)
  import time

  now = int(time.time())
  if text == "اراکی":
    if is_owner(user_id):
      update_user(user_id, user_data[2] + 1000, user_data[3], user_data[4])
      await update.message.reply_text(
          "👑 مالک بزرگ! 1000 نیروی اراکی به حساب شما واریز شد."
      )
      return

    last_claim = user_data[5]
    if now - last_claim < 300:  # 5 دقیقه
      remaining = 300 - (now - last_claim)
      mins = remaining // 60
      secs = remaining % 60
      await update.message.reply_text(
          f"⏳ باید صبر کنید! هر ۵ دقیقه یکبار می‌توانید نیرو بگیرید.\nزمان باقی‌مانده: {mins} دقیقه و {secs} ثانیه."
      )
      return

    # دریافت تصادفی نیرو (مثلاً بین 5 تا 15 نیرو)
    gained = random.randint(5, 15)
    cursor.execute(
        "UPDATE users SET araki = araki + ?, last_claim = ? WHERE user_id = ?",
        (gained, now, user_id),
    )
    conn.commit()
    await update.message.reply_text(
        f"🎉 مبارک باشه! {gained} نیروی اراکی جدید به ارتش شما اضافه شد."
    )

  # ۲. دستور: خرید نیرو
  elif text.startswith("خرید نیرو"):
    parts = text.split()
    if len(parts) < 3 or not parts[2].isdigit():
      await update.message.reply_text(
          "⚠️ فرمت اشتباه! لطفاً به این شکل استفاده کنید:\n`خرید نیرو 10`",
          parse_mode="Markdown",
      )
      return
    count = int(parts[2])
    # فرض بر این است که خرید نیرو رایگان یا با شرایط خاص است؛ اینجا مستقیماً اضافه می‌شود یا می‌توانید هزینه تعیین کنید
    update_user(user_id, user_data[2] + count, user_data[3], user_data[4])
    await update.message.reply_text(
        f"✅ تعداد {count} نیروی اراکی با موفقیت خریداری و به ارتش اضافه شد!"
    )

  # ۳. دستور: گردونه
  elif text == "گردونه":
    if now - user_data[6] < 60:  # محدودیت هر 1 دقیقه برای تست (یا قابل تنظیم)
      # برای راحتی تست محدودیت زمانی گردونه را برمیداریم یا کم می‌کنیم
      pass

    # شانس‌ها: 50 نیرو، 100 نیرو، 1 نیرو، 1000 نیرو، 5000 نیرو (1 درصد)
    rand_val = random.random() * 100  # بین 0 تا 100
    if rand_val <= 1:  # 1 درصد
      prize = 5000
      msg = "🌟 فوق‌العاده! برنده جایزه افسانه‌ای ۵۰۰۰ نیرویی شدید!"
    elif rand_val <= 10:  # 9 درصد
      prize = 1000
      msg = "🔥 عالی! ۱۰۰۰ نیرو برنده شدید!"
    elif rand_val <= 40:  # 30 درصد
      prize = 100
      msg = "✨ ۱۰۰ نیرو برنده شدید!"
    elif rand_val <= 85:  # 45 درصد
      prize = 50
      msg = "⭐ ۵۰ نیرو برنده شدید!"
    else:  # 15 درصد
      prize = 1
      msg = "💫 شانس با شما یار نبود، ۱ نیرو برنده شدید!"

    update_user(user_id, user_data[2] + prize, user_data[3], user_data[4])
    cursor.execute(
        "UPDATE users SET last_spin = ? WHERE user_id = ?", (now, user_id)
    )
    conn.commit()
    await update.message.reply_text(
        f"🎡 چرخش گردونه شانس:\n{msg}\n🎁 جایزه: {prize} نیروی اراکی!"
    )

  # ۴. دستور: تقویت نیرو (اراکی به غلامی)
  elif text == "تقویت نیرو":
    # برای تقویت به غلامی: 100 تا اراکی بده تا 1 غلامی بگیری
    if user_data[2] < 100:
      await update.message.reply_text(
          "⚠️ شما حداقل به 100 نیروی اراکی برای تبدیل به غلامی نیاز دارید!"
      )
      return

    new_araki = user_data[2] - 100
    new_gholami = user_data[3] + 1
    update_user(user_id, new_araki, new_gholami, user_data[4])
    await update.message.reply_text(
        "⚡ تقویت با موفقیت انجام شد!\n100 نیروی اراکی مصرف شد و **1 غلامی** به ارتش شما پیوست. (قدرت: 60)",
        parse_mode="Markdown",
    )

  # ۵. دستور: تقویت غلامی (غلامی به پویا)
  elif text == "تقویت غلامی":
    # برای تقویت به پویا: 30 تا غلامی بده تا 1 پویا بگیری
    if user_data[3] < 30:
      await update.message.reply_text(
          "⚠️ شما حداقل به 30 غلامی برای تبدیل به نیرو پویا نیاز دارید!"
      )
      return

    new_gholami = user_data[3] - 30
    new_pouya = user_data[4] + 1
    update_user(user_id, user_data[2], new_gholami, new_pouya)
    await update.message.reply_text(
        "🚀 تقویت فوق‌العاده انجام شد!\n30 غلامی مصرف شد و **1 نیروی پویا** به ارتش شما پیوست. (قدرت: 78)",
        parse_mode="Markdown",
    )

  # ۶. دستور: قدرت تیم (نمایش دکمه سبز قدرت تیم)
  elif text == "قدرت تیم":
    total_pow = calculate_total_power(user_data[2], user_data[3], user_data[4])
    if is_owner(user_id):
      total_pow = 9999999  # قدرت بی‌نهایت برای مالک

    keyboard = [[InlineKeyboardButton(f"🟢 قدرت تیم: {total_pow}", callback_data="team_power_info")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🛡️ آمار ارتش کاربر {user.first_name}:\n"
        f"🔸 اراکی: {user_data[2]}\n"
        f"🔹 غلامی: {user_data[3]}\n"
        f"🚀 پویا: {user_data[4]}",
        reply_markup=reply_markup,
    )

  # ۷. دستورات جنگ و حمله
  elif text.startswith("جنگ"):
    if update.effective_chat.type == "private":
      await update.message.reply_text("⚠️ این دستور فقط در گروه‌ها قابل استفاده است!")
      return

    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
      await update.message.reply_text(
          "⚠️ فرمت دستور جنگ اشتباه است. مثال: `جنگ 20`", parse_mode="Markdown"
      )
      return

    bet = int(parts[1])
    # بررسی موجودی سرباز کاربر (اراکی + غلامی معادل 30 + پویا معادل 50)
    total_soldiers = (
        user_data[2] + (user_data[3] * 30) + (user_data[4] * 50)
    )
    if not is_owner(user_id) and total_soldiers < bet:
      await update.message.reply_text(
          f"⚠️ شما به اندازه کافی نیرو ندارید! موجودی کل شما ({total_soldiers}) کمتر از مبلغ ورود به جنگ ({bet}) است."
      )
      return

    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("⚔️ ورود به جنگ", callback_data=f"join_war_{chat_id}")],
        [InlineKeyboardButton("❌ لغو بازی", callback_data=f"cancel_war_{chat_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_msg = await update.message.reply_text(
        f"⚔️ **درخواست جنگ جدید!**\n\n"
        f"👤 سازنده: {user.first_name}\n"
        f"💰 تعداد نیرو (ورودی): {bet}\n"
        f"🏆 جایزه برنده: {int(bet * 1.75)} اراکی!\n\n"
        f"برای ورود به جنگ روی دکمه زیر بزنید.",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

    active_wars[chat_id] = {
        "creator_id": user_id,
        "creator_name": user.first_name,
        "bet": bet,
        "message_id": sent_msg.message_id,
    }

  # ۸. دستور: انتقال نیرو (ریپلی روی پیام مخاطب)
  elif text.startswith("انتشار") or text.startswith("انتقال"):
    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
      await update.message.reply_text(
          "⚠️ فرمت انتقال اشتباه است. مثال: `انتشار 20` یا `انتقال 20` (باید روی پیام طرف مقابل ریپلی کنید)",
          parse_mode="Markdown",
      )
      return

    transfer_amount = int(parts[1])
    if not update.message.reply_to_message:
      await update.message.reply_text(
          "⚠️ برای انتقال نیرو باید روی پیام کاربر مورد نظر ریپلی کنید!"
      )
      return

    target_user = update.message.reply_to_message.from_user
    if target_user.id == user_id:
      await update.message.reply_text("⚠️ نمی‌توانید به خودتان نیرو منتقل کنید!")
      return

    target_data = get_user(target_user.id, target_user.username or target_user.first_name)

    # بررسی موجودی فرستنده (اگر مالک نباشد)
    if not is_owner(user_id):
      sender_total = user_data[2] + (user_data[3] * 30) + (user_data[4] * 50)
      if sender_total < transfer_amount:
        await update.message.reply_text("⚠️ شما به اندازه کافی نیرو برای انتقال ندارید!")
        return
        
      # کسر ساده از اراکی‌ها یا واحدهای فرستنده
      new_sender_araki = max(0, user_data[2] - transfer_amount)
      update_user(user_id, new_sender_araki, user_data[3], user_data[4])
    else:
      # مالک بی‌نهایت سرباز دارد
      pass

    # اضافه کردن به گیرنده
    update_user(target_user.id, target_data[2] + transfer_amount, target_data[3], target_data[4])

    # دریافت موجودی جدید
    updated_sender = get_user(user_id)
    updated_target = get_user(target_user.id)

    await update.message.reply_text(
        f"📤 **انتقال نیرو با موفقیت انجام شد!**\n\n"
        f"🔹 تعداد نیروهای انتقال‌یافته: {transfer_amount}\n"
        f"👤 فرستنده ({user.first_name}) - موجودی اراکی باقی‌مانده: {updated_sender[2]}\n"
        f"👤 گیرنده ({target_user.first_name}) - موجودی اراکی جدید: {updated_target[2]}",
        parse_mode="Markdown",
    )


# مدیریت کلیک دکمه‌های شیشه‌ای (ورود به جنگ، لغو بازی و غیره)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  data = query.data
  chat_id = query.message.chat_id
  user = query.from_user
  user_id = user.id

  if data.startswith("join_war_"):
    if chat_id not in active_wars:
      await query.edit_message_text("❌ این جنگ به پایان رسیده یا لغو شده است.")
      return

    war = active_wars[chat_id]
    if user_id == war["creator_id"]:
      await query.answer("شما سازنده این بازی هستید و نمی‌توانید حریف خود باشید!", show_alert=True)
      return

    bet = war["bet"]
    creator_id = war["creator_id"]

    # بررسی موجودی شرکت‌کننده
    joiner_data = get_user(user_id, user.username or user.first_name)
    joiner_total = joiner_data[2] + (joiner_data[3] * 30) + (joiner_data[4] * 50)
    if not is_owner(user_id) and joiner_total < bet:
      await query.answer("موجودی نیروهای شما برای ورود به این جنگ کافی نیست!", show_alert=True)
      return

    creator_data = get_user(creator_id)

    # کسر ورودی‌ها از هر دو بازیکن
    if not is_owner(creator_id):
      update_user(creator_id, max(0, creator_data[2] - bet), creator_data[3], creator_data[4])
    if not is_owner(user_id):
      update_user(user_id, max(0, joiner_data[2] - bet), joiner_data[3], joiner_data[4])

    # اعلام شانسی و غیرقابل پیش‌بینی برنده
    winner_id = random.choice([creator_id, user_id])
    loser_id = user_id if winner_id == creator_id else creator_id

    winner_data = get_user(winner_id)
    loser_data = get_user(loser_id)

    # جایزه برنده (35 تا اراکی یا بر اساس فرمول بت)
    prize = int(bet * 1.75)
    update_user(winner_id, winner_data[2] + prize + bet, winner_data[3], winner_data[4])

    winner_name = war["creator_name"] if winner_id == creator_id else user.first_name
    loser_name = user.first_name if winner_id == creator_id else war["creator_name"]

    # حذف جنگ از لیست فعال
    del active_wars[chat_id]

    await query.edit_message_text(
        f"⚔️ **نتیجه جنگ اعلام شد!**\n\n"
        f"🏆 **برنده:** {winner_name}\n"
        f"💀 **بازنده:** {loser_name}\n\n"
        f"🎁 جایزه دریافت شده توسط برنده: {prize} اراکی\n"
        f"📉 موجودی سرباز بازنده و برنده بررسی و اعمال شد.",
        parse_mode="Markdown",
    )

  elif data.startswith("cancel_war_"):
    if chat_id not in active_wars:
      await query.edit_message_text("❌ این بازی وجود ندارد.")
      return

    war = active_wars[chat_id]
    if user_id != war["creator_id"] and not is_owner(user_id):
      await query.answer("فقط سازنده بازی می‌تواند آن را لغو کند!", show_alert=True)
      return

    del active_wars[chat_id]
    await query.edit_message_text("🚫 بازی توسط سازنده لغو شد.")


def main():
  app = ApplicationBuilder().token(TOKEN).build()

  # ثبت هندلرها
  app.add_handler(MessageHandler(filters.COMMAND & filters.Regex("^/start$"), start_handler))
  app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
  app.add_handler(CallbackQueryHandler(button_handler))

  print("🤖 Bot is running and ready...")
  app.run_polling()


if __name__ == "__main__":
  main()
