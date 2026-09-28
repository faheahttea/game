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


def calculate_total_power(user_id, araki, gholami, pouya):
  if user_id == OWNER_ID:
    return 9999999  # قدرت بی‌نهایت برای مالک
  # قدرت واحدها: اراکی = 44، غلامی = 60، پویا = 80
  return (araki * 44) + (gholami * 60) + (pouya * 80)


def calculate_total_soldiers(user_id, araki, gholami, pouya):
  if user_id == OWNER_ID:
    return 999999999  # سرباز بی‌نهایت برای مالک
  # هر غلامی معادل 30 سرباز، هر پویا معادل 50 سرباز، هر اراکی 1 سرباز
  return araki + (gholami * 30) + (pouya * 50)


# محاسبه جایزه بازی بر اساس مبلغ ورودی
def get_war_prize(bet):
  if bet <= 10:
    return 18
  elif bet <= 20:
    return 38
  elif bet <= 30:
    return 58
  elif bet <= 40:
    return 78
  elif bet >= 1000:
    return 1980
  else:
    return int(bet * 1.9 + 8)


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
        "برای شروع، ربات را به گروه خود اضافه کرده و از دستورات بازی لذت ببرید.",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


# دستور راهنما بصورت دکمه‌ای و دسته‌بندی‌شده
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if update.effective_chat.type == "private":
    return
  
  keyboard = [
      [
          InlineKeyboardButton("⚔️ بخش نبرد و جنگ", callback_data="help_war"),
          InlineKeyboardButton("🛡️ ارتش و نیروها", callback_data="help_army")
      ],
      [
          InlineKeyboardButton("⚡ تقویت و ارتقا", callback_data="help_upgrade"),
          InlineKeyboardButton("🎡 شانس و گردونه", callback_data="help_spin")
      ]
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)
  await update.message.reply_text(
      "📖 **منوی راهنمای جامع بازی اراکی‌ها**\n\n"
      "لطفاً یکی از بخش‌های زیر را انتخاب کنید تا دستورات مربوط به آن نمایش داده شود:",
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

  # دستور راهنما
  if text in ["راهنما", "دستورات", "help"]:
    await help_handler(update, context)
    return

  # دستور موجودی
  if text == "موجودی":
    total_soliders = calculate_total_soldiers(user_id, user_data[2], user_data[3], user_data[4])
    total_pow = calculate_total_power(user_id, user_data[2], user_data[3], user_data[4])
    await update.message.reply_text(
        f"📊 **موجودی ارتش {user.first_name}:**\n\n"
        f"🔸 اراکی‌ها: {user_data[2]}\n"
        f"🔹 غلامی‌ها: {user_data[3]}\n"
        f"🚀 پویایی‌ها: {user_data[4]}\n\n"
        f"👥 کل سربازها: {total_soliders}\n"
        f"⚡ قدرت کل ارتش: {total_pow}",
        parse_mode="Markdown",
    )
    return

  # دستور قدرت
  if text == "قدرت":
    total_pow = calculate_total_power(user_id, user_data[2], user_data[3], user_data[4])
    keyboard = [[InlineKeyboardButton(f"🟢 قدرت تیم: {total_pow}", callback_data="none")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🛡️ **جزئیات قدرت ارتش {user.first_name}:**\n\n"
        f"🔸 اراکی (قدرت 44): {user_data[2]}\n"
        f"🔹 غلامی (قدرت 60): {user_data[3]}\n"
        f"🚀 پویا (قدرت 80): {user_data[4]}\n\n"
        f"⚡ **مجموع قدرت:** {total_pow}",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return

  # ۱. دستور: اراکی (دریافت نیروی شانسی از 1 تا 5000 هر ۵ دقیقه)
  if text == "اراکی":
    if user_id == OWNER_ID:
      update_user(user_id, user_data[2] + 10000, user_data[3], user_data[4])
      await update.message.reply_text("👑 مالک بزرگ! نیروی ویژه به حساب شما اضافه شد.")
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

    gained = random.randint(1, 5000)
    cursor.execute(
        "UPDATE users SET araki = araki + ?, last_claim = ? WHERE user_id = ?",
        (gained, now, user_id),
    )
    conn.commit()
    await update.message.reply_text(
        f"🎉 شانس ارتش شما چرخید!\nتعداد **{gained}** نیروی اراکی به ارتش شما اضافه شد."
    )

  # ۲. دستور: گردونه (کسر 100 نیرو و شانس‌های جدید)
  elif text == "گردونه":
    spin_cost = 100
    if user_id != OWNER_ID and user_data[2] < spin_cost:
      await update.message.reply_text(
          f"⚠️ موجودی شما برای این بازی کافی نیست! (گردونه نیازمند {spin_cost} نیروی اراکی است)"
      )
      return

    if user_id != OWNER_ID:
      update_user(user_id, user_data[2] - spin_cost, user_data[3], user_data[4])
      user_data = get_user(user_id)

    # شانس‌های گردونه:
    # 0.0000000000001% -> 100000
    # 1% -> 5000
    # 25% -> 1000
    # 50% -> 500 / 100 / 50 / 1 (بقیه بازه‌ها)
    rand_val = random.random() * 100
    if rand_val <= 0.0000000000001:
      prize = 100000
      msg = "💎 فوق اسطوره‌ای! جایزه باورنکردنی ۱۰۰,۰۰۰ نیرویی برنده شدید!"
    elif rand_val <= 1.0:
      prize = 5000
      msg = "🌟 افسانه‌ای! ۵۰۰۰ نیرو برنده شدید!"
    elif rand_val <= 26.0:
      prize = 1000
      msg = "🔥 عالی! ۱۰۰۰ نیرو برنده شدید!"
    elif rand_val <= 76.0:
      prize = random.choice([500, 100, 50])
      msg = f"✨ تبریک! {prize} نیرو برنده شدید!"
    else:
      prize = 1
      msg = "💫 شانس با شما یار نبود، ۱ نیرو برنده شدید!"

    update_user(user_id, user_data[2] + prize, user_data[3], user_data[4])
    cursor.execute(
        "UPDATE users SET last_spin = ? WHERE user_id = ?", (now, user_id)
    )
    conn.commit()
    await update.message.reply_text(
        f"🎡 **گردونه شانس اراکی‌ها (هزینه: ۱۰۰ نیرو):**\n{msg}\n🎁 پاداش خالص: {prize} اراکی",
        parse_mode="Markdown",
    )

  # ۳. دستور: تقویت نیرو (با پشتیبانی از تعداد مثل "تقویت نیرو 10")
  elif text.startswith("تقویت نیرو"):
    parts = text.split()
    count = 1
    if len(parts) >= 3 and parts[2].isdigit():
      count = int(parts[2])

    cost = count * 100
    if user_id != OWNER_ID and user_data[2] < cost:
      await update.message.reply_text(
          f"⚠️ موجودی شما برای این بازی کافی نیست! (حداقل به {cost} نیروی اراکی نیاز دارید)"
      )
      return

    if user_id != OWNER_ID:
      new_araki = user_data[2] - cost
      new_gholami = user_data[3] + count
      update_user(user_id, new_araki, new_gholami, user_data[4])
    else:
      update_user(user_id, user_data[2], user_data[3] + count, user_data[4])

    await update.message.reply_text(
        f"⚡ تقویت انجام شد!\n{cost} نیروی اراکی مصرف شد و **{count} غلامی** (قدرت: 60) به ارتش اضافه شد.",
        parse_mode="Markdown",
    )

  # ۴. دستور: تقویت غلامی (تبدیل ۳۰ غلامی به ۱ پویا با پشتیبانی از تعداد و کسر دقیق)
  elif text.startswith("تقویت غلامی"):
    parts = text.split()
    count = 1
    if len(parts) >= 2 and parts[2].isdigit():
      count = int(parts[2])

    cost_gholami = count * 30
    if user_id != OWNER_ID and user_data[3] < cost_gholami:
      await update.message.reply_text(
          f"⚠️ موجودی شما برای این بازی کافی نیست! (به {cost_gholami} غلامی نیاز است)"
      )
      return

    if user_id != OWNER_ID:
      new_gholami = user_data[3] - cost_gholami
      new_pouya = user_data[4] + count
      update_user(user_id, user_data[2], new_gholami, new_pouya)
    else:
      update_user(user_id, user_data[2], user_data[3] - cost_gholami, user_data[4] + count)

    await update.message.reply_text(
        f"🚀 تقویت نسخه ۲ انجام شد!\n{cost_gholami} غلامی مصرف شد و **{count} نیروی پویا** (قدرت: 80) به ارتش پیوست.",
        parse_mode="Markdown",
    )

  # ۵. دستور: حمله مستقیم با نمایش تعداد نیروهای از دست رفته
  elif text == "حمله":
    if update.effective_chat.type == "private":
      await update.message.reply_text("⚠️ دستور حمله فقط در داخل گروه‌ها قابل اجراست!")
      return

    if not update.message.reply_to_message:
      await update.message.reply_text(
          "⚠️ برای حمله حتماً باید روی پیام کاربر مورد نظر ریپلی کنید!"
      )
      return

    target_user = update.message.reply_to_message.from_user
    if target_user.id == user_id:
      await update.message.reply_text("⚠️ نمی‌توانید به خودتان حمله کنید!")
      return

    attacker_total_soldiers = calculate_total_soldiers(user_id, user_data[2], user_data[3], user_data[4])
    if user_id != OWNER_ID and attacker_total_soldiers < 10:
      await update.message.reply_text("⚠️ موجودی شما برای این بازی کافی نیست!")
      return

    target_data = get_user(target_user.id, target_user.username or target_user.first_name)

    # قدرت و امتیازات حمله
    attacker_power = calculate_total_power(user_id, user_data[2], user_data[3], user_data[4])
    target_power = calculate_total_power(target_user.id, target_data[2], target_data[3], target_data[4])

    attacker_boost = (user_data[3] * 2) + (user_data[4] * 4)
    target_boost = (target_data[3] * 2) + (target_data[4] * 4)

    final_attacker_score = attacker_power + (attacker_boost * 10) + random.randint(1, 200)
    final_target_score = target_power + (target_boost * 10) + random.randint(1, 200)

    if final_attacker_score >= final_target_score:
      winner_id, loser_id = user_id, target_user.id
      winner_name, loser_name = user.first_name, target_user.first_name
      winner_data, loser_data = user_data, target_data
    else:
      winner_id, loser_id = target_user.id, user_id
      winner_name, loser_name = target_user.first_name, user.first_name
      winner_data, loser_data = target_data, user_data

    # محاسبه تلفات و غنائم
    lost_araki = random.randint(2, 10)
    loot_araki = loser_data[2] // 3
    loot_gholami = loser_data[3] // 3
    loot_pouya = loser_data[4] // 3

    # به‌روزرسانی بازنده
    new_loser_araki = max(0, loser_data[2] - loot_araki - lost_araki)
    new_loser_gholami = max(0, loser_data[3] - loot_gholami)
    new_loser_pouya = max(0, loser_data[4] - loot_pouya)
    update_user(loser_id, new_loser_araki, new_loser_gholami, new_loser_pouya)

    # به‌روزرسانی برنده
    new_winner_araki = winner_data[2] + loot_araki - random.randint(1, 5)
    new_winner_gholami = winner_data[3] + loot_gholami
    new_winner_pouya = winner_data[4] + loot_pouya
    update_user(winner_id, max(0, new_winner_araki), new_winner_gholami, new_winner_pouya)

    updated_u1 = get_user(user_id)
    updated_u2 = get_user(target_user.id)

    await update.message.reply_text(
        f"⚔️ **نتیجه نبرد و حمله مستقیم!**\n\n"
        f"🏆 **برنده میدان:** {winner_name}\n"
        f"💀 **شکست خورده:** {loser_name}\n\n"
        f"💥 **تلفات جنگ:** در این حمله تعدادی از نیروهای دو طرف از دست رفتند.\n\n"
        f"🛡️ **موجودی جدید دو طرف:**\n"
        f"👤 {user.first_name} ➔ اراکی: {updated_u1[2]} | غلامی: {updated_u1[3]} | پویا: {updated_u1[4]}\n"
        f"👤 {target_user.first_name} ➔ اراکی: {updated_u2[2]} | غلامی: {updated_u2[3]} | پویا: {updated_u2[4]}",
        parse_mode="Markdown",
    )

  # ۶. دستور: جنگ
  elif text.startswith("جنگ"):
    if update.effective_chat.type == "private":
      await update.message.reply_text("⚠️ دستور جنگ فقط در داخل گروه‌ها قابل اجراست!")
      return

    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
      await update.message.reply_text(
          "⚠️ فرمت دستور جنگ اشتباه است. مثال: `جنگ 50`", parse_mode="Markdown"
      )
      return

    bet = int(parts[1])
    total_soliders = calculate_total_soldiers(user_id, user_data[2], user_data[3], user_data[4])
    if user_id != OWNER_ID and total_soliders < bet:
      await update.message.reply_text(
          f"⚠️ موجودی شما برای این بازی کافی نیست! (موجودی کل: {total_soliders})"
      )
      return

    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("⚔️ پیوستن به بازی", callback_data=f"join_war_{chat_id}")],
        [InlineKeyboardButton("❌ لغو بازی", callback_data=f"cancel_war_{chat_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    prize = get_war_prize(bet)

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
        "message_id": sent_msg.message_id,
    }

  # ۷. دستور: انتقال نیرو
  elif text.startswith("انتقال") or text.startswith("انتشار"):
    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
      await update.message.reply_text(
          "⚠️ فرمت اشتباه! مثال: `انتقال 20` (باید روی پیام طرف مقابل ریپلی کنید)",
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
        await update.message.reply_text("⚠️ موجودی شما برای این بازی کافی نیست!")
        return
      new_sender_araki = max(0, user_data[2] - transfer_amount)
      update_user(user_id, new_sender_araki, user_data[3], user_data[4])

    update_user(target_user.id, target_data[2] + transfer_amount, target_data[3], target_data[4])

    updated_sender = get_user(user_id)
    updated_target = get_user(target_user.id)

    await update.message.reply_text(
        f"📤 **انتقال نیرو با موفقیت انجام شد!**\n\n"
        f"🔹 تعداد سرباز انتقال‌یافته: {transfer_amount}\n"
        f"👤 فرستنده ({user.first_name}) - موجودی اراکی فعلی: {updated_sender[2]}\n"
        f"👤 گیرنده ({target_user.first_name}) - موجودی اراکی جدید: {updated_target[2]}",
        parse_mode="Markdown",
    )


# مدیریت کلیک دکمه‌های شیشه‌ای
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  data = query.data
  user = query.from_user
  user_id = user.id

  # مدیریت منوهای راهنما
  if data.startswith("help_"):
    await query.answer()
    if data == "help_war":
      text = "⚔️ **بخش نبرد و جنگ:**\n\n- `جنگ [مبلغ]` : ایجاد مسابقه جنگی\n- `حمله` : ریپلی روی کاربر و حمله مستقیم با تمام نیروها"
    elif data == "help_army":
      text = "🛡️ **بخش ارتش و نیروها:**\n\n- `اراکی` : دریافت نیروی رایگان (هر ۵ دقیقه)\n- `موجودی` : نمایش کل نیروها\n- `قدرت` : نمایش قدرت رزمی\n- `انتقال [تعداد]` : فرستادن نیرو به دوستان"
    elif data == "help_upgrade":
      text = "⚡ **بخش تقویت و ارتقا:**\n\n- `تقویت نیرو [تعداد]` : تبدیل اراکی به غلامی (هر 100 اراکی = 1 غلامی)\n- `تقویت غلامی [تعداد]` : تبدیل غلامی به پویا (هر 30 غلامی = 1 پویا)"
    elif data == "help_spin":
      text = "🎡 **بخش شانس و گردونه:**\n\n- `گردونه` : چرخش گردونه با هزینه 100 نیرو و شانس دریافت جوایز بزرگ!"
    else:
      text = "راهنمای بازی اراکی‌ها"
    
    await query.edit_message_text(text, parse_mode="Markdown")
    return

  await query.answer()
  chat_id = query.message.chat_id

  if data.startswith("join_war_"):
    if chat_id not in active_wars:
      await query.edit_message_text("❌ این بازی به اتمام رسیده یا منقضی شده است.")
      return

    war = active_wars[chat_id]
    if user_id == war["creator_id"]:
      await query.answer("شما مالک بازی هستید و نمی‌توانید حریف خود باشید!", show_alert=True)
      return

    bet = war["bet"]
    creator_id = war["creator_id"]

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
    loser_data = get_user(loser_id)

    prize = get_war_prize(bet)
    update_user(winner_id, winner_data[2] + bet + prize, winner_data[3], winner_data[4])

    winner_name = war["creator_name"] if winner_id == creator_id else user.first_name
    loser_name = user.first_name if winner_id == creator_id else war["creator_name"]

    del active_wars[chat_id]

    final_winner_data = get_user(winner_id)
    final_loser_data = get_user(loser_id)

    await query.edit_message_text(
        f"⚔️ **نتیجه جنگ اعلام شد!**\n\n"
        f"🏆 **برنده:** {winner_name}\n"
        f"💀 **بازنده:** {loser_name}\n\n"
        f"🎁 پاداش برنده: {prize} اراکی به همراه بازگشت ورودی‌ها\n"
        f"📊 موجودی سربازان دو طرف بروزرسانی شد.\n\n"
        f"👤 **موجودی جدید برنده ({winner_name}):**\n"
        f"🔸 اراکی: {final_winner_data[2]} | 🔹 غلامی: {final_winner_data[3]} | 🚀 پویا: {final_winner_data[4]}\n\n"
        f"👤 **موجودی جدید بازنده ({loser_name}):**\n"
        f"🔸 اراکی: {final_loser_data[2]} | 🔹 غلامی: {final_loser_data[3]} | 🚀 پویا: {final_loser_data[4]}",
        parse_mode="Markdown",
    )

  elif data.startswith("cancel_war_"):
    if chat_id not in active_wars:
      await query.edit_message_text("❌ بازی وجود ندارد.")
      return

    war = active_wars[chat_id]
    if user_id != war["creator_id"] and user_id != OWNER_ID:
      await query.answer("شما سازنده بازی نیستید!", show_alert=True)
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
  app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
  main()
