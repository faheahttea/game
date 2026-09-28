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

# اطلاعات پایه‌ای (آیدی عددی مالک اصلی: 8854073031)
TOKEN = "8559844059:AAHzw5hpToGqME76APSQvjfV0AbThOm277s"
OWNER_ID = 8854073031

# ذخیره وضعیت مالک (آیا مالک در حالت بازیکن است یا خیر)
owner_modes = {}

# اتصال به دیتابیس SQLite
conn = sqlite3.connect("araki_game.db", check_same_thread=False)
cursor = conn.cursor()

# ایجاد جدول کاربران (اضافه شدن فیلدهای مربوط به کارگر ارسام فتحی)
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    araki INTEGER DEFAULT 0,
    gholami INTEGER DEFAULT 0,
    pouya INTEGER DEFAULT 0,
    zeroniga INTEGER DEFAULT 0,
    arsam_fathi INTEGER DEFAULT 0,
    last_claim INTEGER DEFAULT 0,
    last_spin INTEGER DEFAULT 0,
    last_worker_claim INTEGER DEFAULT 0
)
"""
)
conn.commit()

# جدول مدیریت جنگ‌ها و بازی‌های فعال در گروه‌ها
active_wars = {}


def get_user(user_id, username=""):
  cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
  row = cursor.fetchone()
  if not row:
    cursor.execute(
        "INSERT INTO users (user_id, username, araki) VALUES (?, ?, ?)",
        (user_id, username or "User", 0),
    )
    conn.commit()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
  return row


def update_user(user_id, araki, gholami, pouya, zeroniga, arsam_fathi):
  cursor.execute(
      "UPDATE users SET araki = ?, gholami = ?, pouya = ?, zeroniga = ?, arsam_fathi = ? WHERE user_id = ?",
      (araki, gholami, pouya, zeroniga, arsam_fathi, user_id),
  )
  conn.commit()


def calculate_total_power(user_id, araki, gholami, pouya, zeroniga, arsam_fathi):
  if user_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False):
    return 9999999  # قدرت بی‌نهایت برای مالک در حالت ادمین
  return (araki * 44) + (gholami * 60) + (pouya * 80) + (zeroniga * 90) + (arsam_fathi * 120)


def calculate_total_soldiers(user_id, araki, gholami, pouya, zeroniga, arsam_fathi):
  if user_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False):
    return 999999999  # سرباز بی‌نهایت برای مالک در حالت ادمین
  return araki + (gholami * 30) + (pouya * 50) + (zeroniga * 70) + arsam_fathi


def get_war_prize(bet):
  return bet * 2


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


async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if not update.message or not update.message.text:
    return

  text = update.message.text.strip()
  user = update.effective_user
  user_id = user.id
  username = user.username or user.first_name

  # بررسی حالت مالک
  if user_id == OWNER_ID:
    if text == "حالت بازیکن":
      if OWNER_ID not in owner_modes or not owner_modes[OWNER_ID]["is_player_mode"]:
        u_data = get_user(OWNER_ID)
        owner_modes[OWNER_ID] = {
            "is_player_mode": True,
            "saved_araki": u_data[2],
            "saved_gholami": u_data[3],
            "saved_pouya": u_data[4],
            "saved_zeroniga": u_data[5],
            "saved_arsam_fathi": u_data[6],
        }
        update_user(OWNER_ID, 0, 0, 0, 0, 0)
        await update.message.reply_text("👤 حالت مالک تغییر کرد: شما اکنون در **حالت بازیکن** هستید و ارتش شما صفر شد.")
      else:
        await update.message.reply_text("⚠️ شما از قبل در حالت بازیکن هستید.")
      return

    elif text == "حالت مالک":
      if OWNER_ID in owner_modes and owner_modes[OWNER_ID]["is_player_mode"]:
        u_data = get_user(OWNER_ID)
        restored_araki = u_data[2] + owner_modes[OWNER_ID]["saved_araki"]
        restored_gholami = u_data[3] + owner_modes[OWNER_ID]["saved_gholami"]
        restored_pouya = u_data[4] + owner_modes[OWNER_ID]["saved_pouya"]
        restored_zeroniga = u_data[5] + owner_modes[OWNER_ID]["saved_zeroniga"]
        restored_arsam_fathi = u_data[6] + owner_modes[OWNER_ID]["saved_arsam_fathi"]
        
        update_user(OWNER_ID, restored_araki, restored_gholami, restored_pouya, restored_zeroniga, restored_arsam_fathi)
        owner_modes[OWNER_ID]["is_player_mode"] = False
        await update.message.reply_text("👑 حالت مالک بازگشت: قدرتمند شدید و تمام نیروهای قبلی شما بازگردانده شدند!")
      else:
        await update.message.reply_text("⚠️ شما در حالت مالک (نامحدود) هستید.")
      return

    elif text in ["حذف موجودی", "حذف نیرو"]:
      if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ برای حذف نیروهای کاربر باید روی پیام او ریپلی کنید!")
        return
      target_user = update.message.reply_to_message.from_user
      update_user(target_user.id, 0, 0, 0, 0, 0)
      await update.message.reply_text(f"🗑️ تمام نیروها و کارگرهای کاربر {target_user.first_name} با دستور مالک حذف و صفر شدند.")
      return

  user_data = get_user(user_id, username)
  now = int(time.time())

  if text in ["راهنما", "دستورات", "help"]:
    await help_handler(update, context)
    return

  if text == "موجودی":
    total_soliders = calculate_total_soldiers(user_id, user_data[2], user_data[3], user_data[4], user_data[5], user_data[6])
    total_pow = calculate_total_power(user_id, user_data[2], user_data[3], user_data[4], user_data[5], user_data[6])
    await update.message.reply_text(
        f"📊 **موجودی ارتش {user.first_name}:**\n\n"
        f"🔸 اراکی‌ها: {user_data[2]}\n"
        f"🔹 غلامی‌ها: {user_data[3]}\n"
        f"🚀 پویایی‌ها: {user_data[4]}\n"
        f"💎 صفرنیگاها: {user_data[5]}\n"
        f"👷‍♂️ ارسام فتحی: {user_data[6]}\n\n"
        f"👥 کل سربازها: {total_soliders}\n"
        f"⚡ قدرت کل ارتش: {total_pow}",
        parse_mode="Markdown",
    )
    return

  if text == "قدرت":
    total_pow = calculate_total_power(user_id, user_data[2], user_data[3], user_data[4], user_data[5], user_data[6])
    keyboard = [[InlineKeyboardButton(f"🟢 قدرت تیم: {total_pow}", callback_data="none")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🛡️ **جزئیات قدرت ارتش {user.first_name}:**\n\n"
        f"🔸 اراکی (قدرت 44): {user_data[2]}\n"
        f"🔹 غلامی (قدرت 60): {user_data[3]}\n"
        f"🚀 پویا (قدرت 80): {user_data[4]}\n"
        f"💎 صفرنیگا (قدرت 90): {user_data[5]}\n"
        f"👷‍♂️ ارسام فتحی (قدرت 120): {user_data[6]}\n\n"
        f"⚡ **مجموع قدرت:** {total_pow}",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return

  if text in ["اراکی", "لبیک یا اراک"]:
    if user_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False):
      update_user(user_id, user_data[2] + 10000, user_data[3], user_data[4], user_data[5], user_data[6])
      await update.message.reply_text("👑 مالک بزرگ! نیروی ویژه به حساب شما اضافه شد.")
      return

    last_claim = user_data[7]
    if now - last_claim < 300:
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

  elif text == "گردونه":
    spin_cost = 100
    is_owner_admin = (user_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False))
    if not is_owner_admin and user_data[2] < spin_cost:
      await update.message.reply_text(
          f"⚠️ موجودی شما برای این بازی کافی نیست! (گردونه نیازمند {spin_cost} نیروی اراکی است)"
      )
      return

    if not is_owner_admin:
      update_user(user_id, user_data[2] - spin_cost, user_data[3], user_data[4], user_data[5], user_data[6])
      user_data = get_user(user_id)

    rand_val = random.random() * 100
    if rand_val <= 1.0:
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

    update_user(user_id, user_data[2] + prize, user_data[3], user_data[4], user_data[5], user_data[6])
    cursor.execute(
        "UPDATE users SET last_spin = ? WHERE user_id = ?", (now, user_id)
    )
    conn.commit()
    await update.message.reply_text(
        f"🎡 **گردونه شانس اراکی‌ها (هزینه: ۱۰۰ نیرو):**\n{msg}\n🎁 پاداش خالص: {prize} اراکی",
        parse_mode="Markdown",
    )

  elif text.startswith("تقویت کارگر"):
    parts = text.split()
    count = 1
    if len(parts) >= 3 and parts[2].isdigit():
      count = int(parts[2])

    current_arsam = user_data[6]
    is_owner_admin = (user_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False))

    # سقف خرید برداشته شد (بدون محدودیت تعداد)
    cost = count * 100000
    if not is_owner_admin and user_data[2] < cost:
      await update.message.reply_text(
          f"⚠️ موجودی شما کافی نیست! هر کارگر ارسام فتحی نیازمند ۱۰۰,۰۰۰ نیروی اراکی است. (کل هزینه برای {count} عدد: {cost})"
      )
      return

    if not is_owner_admin:
      new_araki = user_data[2] - cost
      new_arsam = current_arsam + count
      update_user(user_id, new_araki, user_data[3], user_data[4], user_data[5], new_arsam)
    else:
      update_user(user_id, user_data[2], user_data[3], user_data[4], user_data[5], current_arsam + count)

    await update.message.reply_text(
        f"👷‍♂️ استخدام موفقیت‌آمیز!\n{cost} نیروی اراکی مصرف شد و **{count} کارگر (ارسام فتحی)** اضافه شد.\n"
        f"کل کارگرهای شما: {current_arsam + count}",
        parse_mode="Markdown",
    )

  elif text == "حقوق کارگری":
    arsam_count = user_data[6]
    if arsam_count <= 0:
      await update.message.reply_text("⚠️ شما هیچ کارگری (ارسام فتحی) ندارید!")
      return

    last_worker_claim = user_data[9] if len(user_data) > 9 and user_data[9] else user_data[7]
    elapsed_seconds = now - last_worker_claim

    if elapsed_seconds < 3600:
      remaining = 3600 - elapsed_seconds
      mins = remaining // 60
      secs = remaining % 60
      await update.message.reply_text(
          f"⏳ هنوز یک ساعت از آخرین دریافت حقوق نگذشته است!\nزمان باقی‌مانده: {mins} دقیقه و {secs} ثانیه."
      )
      return

    hours_passed = elapsed_seconds // 3600

    # جدول حقوق بر اساس تعداد کارگر (ارسام فتحی)
    salary_map = {
        1: 1000,
        2: 2000,
        3: 20000,
        4: 50000,
        5: 100000
    }
    
    per_hour_rate = salary_map.get(arsam_count, arsam_count * 20000)
    earned_araki = per_hour_rate * hours_passed
    
    new_last_claim_time = last_worker_claim + (hours_passed * 3600)
    new_araki = user_data[2] + earned_araki
    
    update_user(user_id, new_araki, user_data[3], user_data[4], user_data[5], user_data[6])
    cursor.execute(
        "UPDATE users SET last_worker_claim = ? WHERE user_id = ?", (new_last_claim_time, user_id)
    )
    conn.commit()

    await update.message.reply_text(
        f"💰 **حقوق کارگری دریافت شد!**\n\n"
        f"👷‍♂️ تعداد کارگران (ارسام فتحی): {arsam_count}\n"
        f"⏱️ ساعت‌های محاسبه‌شده: {hours_passed} ساعت\n"
        f"🎉 سود دریافتی: **{earned_araki}** نیروی اراکی اضافه شد!",
        parse_mode="Markdown",
    )

  elif text.startswith("تقویت نیرو"):
    parts = text.split()
    count = 1
    if len(parts) >= 3 and parts[2].isdigit():
      count = int(parts[2])

    cost = count * 100
    is_owner_admin = (user_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False))
    if not is_owner_admin and user_data[2] < cost:
      await update.message.reply_text(
          f"⚠️ موجودی شما برای این بازی کافی نیست! (حداقل به {cost} نیروی اراکی نیاز دارید)"
      )
      return

    if not is_owner_admin:
      new_araki = user_data[2] - cost
      new_gholami = user_data[3] + count
      update_user(user_id, new_araki, new_gholami, user_data[4], user_data[5], user_data[6])
    else:
      update_user(user_id, user_data[2], user_data[3] + count, user_data[4], user_data[5], user_data[6])

    await update.message.reply_text(
        f"⚡ تقویت انجام شد!\n{cost} نیروی اراکی مصرف شد و **{count} غلامی** به ارتش اضافه شد.",
        parse_mode="Markdown",
    )

  elif text.startswith("تقویت غلامی"):
    parts = text.split()
    count = 1
    if len(parts) >= 3 and parts[2].isdigit():
      count = int(parts[2])

    cost_gholami = count * 30
    is_owner_admin = (user_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False))
    if not is_owner_admin and user_data[3] < cost_gholami:
      await update.message.reply_text(
          f"⚠️ موجودی شما برای این بازی کافی نیست! (به {cost_gholami} غلامی نیاز است)"
      )
      return

    if not is_owner_admin:
      new_gholami = user_data[3] - cost_gholami
      new_pouya = user_data[4] + count
      update_user(user_id, user_data[2], new_gholami, new_pouya, user_data[5], user_data[6])
    else:
      update_user(user_id, user_data[2], user_data[3] - cost_gholami, user_data[4] + count, user_data[5], user_data[6])

    await update.message.reply_text(
        f"🚀 تقویت غلامی انجام شد!\n{cost_gholami} غلامی مصرف شد و **{count} نیروی پویا** به ارتش پیوست.",
        parse_mode="Markdown",
    )

  elif text.startswith("تقویت پویا"):
    parts = text.split()
    count = 1
    if len(parts) >= 3 and parts[2].isdigit():
      count = int(parts[2])

    cost_pouya = count * 100
    is_owner_admin = (user_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False))
    if not is_owner_admin and user_data[4] < cost_pouya:
      await update.message.reply_text(
          f"⚠️ موجودی شما برای این بازی کافی نیست! (به {cost_pouya} نیروی پویا نیاز است)"
      )
      return

    if not is_owner_admin:
      new_pouya = user_data[4] - cost_pouya
      new_zeroniga = user_data[5] + count
      update_user(user_id, user_data[2], user_data[3], new_pouya, new_zeroniga, user_data[6])
    else:
      update_user(user_id, user_data[2], user_data[3], user_data[4], user_data[5] + count, user_data[6])

    await update.message.reply_text(
        f"💎 تقویت پویا انجام شد!\n{cost_pouya} نیروی پویا مصرف شد و **{count} نیروی صفرنیگا** به ارتش شما اضافه شد.",
        parse_mode="Markdown",
    )

  elif text.startswith("حمله"):
    if update.effective_chat.type == "private":
      await update.message.reply_text("⚠️ دستور حمله فقط در داخل گروه‌ها قابل اجراست!")
      return

    target_user_id = None
    target_username_display = "کاربر هدف"

    parts = text.split()
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
      target_user = update.message.reply_to_message.from_user
      target_user_id = target_user.id
      target_username_display = target_user.first_name
    elif len(parts) >= 2 and parts[1].isdigit():
      target_user_id = int(parts[1])
      try:
        chat_member = await context.bot.get_chat_member(update.effective_chat.id, target_user_id)
        if chat_member and chat_member.user:
          target_username_display = chat_member.user.first_name
      except Exception:
        target_username_display = f"کاربر {target_user_id}"

    if not target_user_id:
      await update.message.reply_text(
          "⚠️ برای حمله یا باید روی پیام کاربر ریپلی کنید یا آیدی عددی او را بنویسید!",
          parse_mode="Markdown",
      )
      return

    if target_user_id == user_id:
      await update.message.reply_text("⚠️ نمی‌توانید به خودتان حمله کنید!")
      return

    is_owner_admin = (user_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False))
    attacker_total_soldiers = calculate_total_soldiers(user_id, user_data[2], user_data[3], user_data[4], user_data[5], user_data[6])
    if not is_owner_admin and attacker_total_soldiers < 10:
      await update.message.reply_text("⚠️ موجودی شما برای این بازی کافی نیست!")
      return

    target_data = get_user(target_user_id, target_username_display)

    attacker_power = calculate_total_power(user_id, user_data[2], user_data[3], user_data[4], user_data[5], user_data[6])
    target_power = calculate_total_power(target_user_id, target_data[2], target_data[3], target_data[4], target_data[5], target_data[6])

    attacker_boost = (user_data[3] * 2) + (user_data[4] * 4) + (user_data[5] * 6) + (user_data[6] * 8)
    target_boost = (target_data[3] * 2) + (target_data[4] * 4) + (target_data[5] * 6) + (target_data[6] * 8)

    final_attacker_score = attacker_power + (attacker_boost * 10) + random.randint(1, 200)
    final_target_score = target_power + (target_boost * 10) + random.randint(1, 200)

    if final_attacker_score >= final_target_score:
      winner_id, loser_id = user_id, target_user_id
      winner_name, loser_name = user.first_name, target_username_display
      winner_data, loser_data = user_data, target_data
    else:
      winner_id, loser_id = target_user_id, user_id
      winner_name, loser_name = target_username_display, user.first_name
      winner_data, loser_data = target_data, user_data

    loser_lost_araki = random.randint(5, 15)
    winner_lost_araki = random.randint(2, 8)

    loot_araki = loser_data[2] // 3
    loot_gholami = loser_data[3] // 3
    loot_pouya = loser_data[4] // 3
    loot_zeroniga = loser_data[5] // 3
    loot_arsam = loser_data[6] // 3

    new_loser_araki = max(0, loser_data[2] - loot_araki - loser_lost_araki)
    new_loser_gholami = max(0, loser_data[3] - loot_gholami)
    new_loser_pouya = max(0, loser_data[4] - loot_pouya)
    new_loser_zeroniga = max(0, loser_data[5] - loot_zeroniga)
    new_loser_arsam = max(0, loser_data[6] - loot_arsam)
    update_user(loser_id, new_loser_araki, new_loser_gholami, new_loser_pouya, new_loser_zeroniga, new_loser_arsam)

    is_winner_owner_admin = (winner_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False))
    if not is_winner_owner_admin:
      new_winner_araki = max(0, winner_data[2] + loot_araki - winner_lost_araki)
      new_winner_gholami = winner_data[3] + loot_gholami
      new_winner_pouya = winner_data[4] + loot_pouya
      new_winner_zeroniga = winner_data[5] + loot_zeroniga
      new_winner_arsam = winner_data[6] + loot_arsam
      update_user(winner_id, new_winner_araki, new_winner_gholami, new_winner_pouya, new_winner_zeroniga, new_winner_arsam)

    updated_u1 = get_user(user_id)
    updated_u2 = get_user(target_user_id)

    await update.message.reply_text(
        f"⚔️ **نتیجه نبرد و حمله مستقیم!**\n\n"
        f"🏆 **برنده میدان:** {winner_name}\n"
        f"💀 **شکست خورده:** {loser_name}\n\n"
        f"💥 **تلفات جنگ:**\n"
        f"👤 {user.first_name}: {winner_lost_araki if winner_id == user_id else loser_lost_araki} سرباز از دست داد.\n"
        f"👤 {target_username_display}: {winner_lost_araki if winner_id == target_user_id else loser_lost_araki} سرباز از دست داد.\n\n"
        f"🛡️ **موجودی جدید دو طرف:**\n"
        f"👤 {user.first_name} ➔ اراکی: {updated_u1[2]} | کارگر: {updated_u1[6]}\n"
        f"👤 {target_username_display} ➔ اراکی: {updated_u2[2]} | کارگر: {updated_u2[6]}",
        parse_mode="Markdown",
    )

  elif text.startswith("جنگ") or text.startswith("بازی"):
    if update.effective_chat.type == "private":
      await update.message.reply_text("⚠️ دستورات مسابقه فقط در داخل گروه‌ها قابل اجراست!")
      return

    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
      await update.message.reply_text(
          "⚠️ فرمت دستور اشتباه است. مثال: `جنگ 3000` یا `بازی 1000`", parse_mode="Markdown"
      )
      return

    bet = int(parts[1])
    is_owner_admin = (user_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False))
    total_soliders = calculate_total_soldiers(user_id, user_data[2], user_data[3], user_data[4], user_data[5], user_data[6])
    if not is_owner_admin and total_soliders < bet:
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
        f"⚔️ **درخواست مسابقه و جنگ جدید!**\n\n"
        f"👤 سازنده بازی: {user.first_name}\n"
        f"🎯 تعداد نیرو (ورودی): {bet}\n"
        f"🏆 جایزه برنده: {prize} اراکی\n\n"
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

  elif text.startswith("انتقال") or text.startswith("انتشار"):
    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
      await update.message.reply_text(
          "⚠️ فرمت اشتباه! مثال: `انتقال 20` (باید روی پیام طرف مقابل ریپلی کنید)",
          parse_mode="Markdown",
      )
      return

    transfer_amount = int(parts[1])
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
      await update.message.reply_text(
          "⚠️ برای انتقال نیرو حتماً باید روی پیام کاربر مورد نظر ریپلی کنید!"
      )
      return

    target_user = update.message.reply_to_message.from_user
    if target_user.id == user_id:
      await update.message.reply_text("⚠️ نمی‌توانید به خودتان نیرو انتقال دهید!")
      return

    target_data = get_user(target_user.id, target_user.username or target_user.first_name)
    is_owner_admin = (user_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False))

    if not is_owner_admin:
      sender_total = calculate_total_soldiers(user_id, user_data[2], user_data[3], user_data[4], user_data[5], user_data[6])
      if sender_total < transfer_amount:
        await update.message.reply_text("⚠️ موجودی شما برای این بازی کافی نیست!")
        return
      new_sender_araki = max(0, user_data[2] - transfer_amount)
      update_user(user_id, new_sender_araki, user_data[3], user_data[4], user_data[5], user_data[6])

    update_user(target_user.id, target_data[2] + transfer_amount, target_data[3], target_data[4], target_data[5], target_data[6])

    updated_sender = get_user(user_id)
    updated_target = get_user(target_user.id)

    await update.message.reply_text(
        f"📤 **انتقال نیرو با موفقیت انجام شد!**\n\n"
        f"🔹 تعداد سرباز انتقال‌یافته: {transfer_amount}\n"
        f"👤 فرستنده ({user.first_name}) - اراکی: {updated_sender[2]}\n"
        f"👤 گیرنده ({target_user.first_name}) - اراکی: {updated_target[2]}",
        parse_mode="Markdown",
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  data = query.data
  user = query.from_user
  user_id = user.id

  if data.startswith("help_"):
    await query.answer()
    if data == "help_war":
      text = "⚔️ **بخش نبرد و جنگ:**\n\n- `جنگ [مبلغ]` یا `بازی [مبلغ]` : ایجاد مسابقه جنگی\n- `حمله` (ریپلی یا آیدی عددی) : حمله مستقیم"
    elif data == "help_army":
      text = "🛡️ **بخش ارتش و نیروها:**\n\n- `اراکی` : دریافت نیروی رایگان (هر ۵ دقیقه)\n- `موجودی` : نمایش کل نیروها\n- `قدرت` : نمایش قدرت رزمی\n- `حقوق کارگری` : دریافت سود کارگران (ارسام فتحی)\n- `تقویت کارگر [تعداد]` : خرید کارگر (هر عدد ۱۰۰,۰۰۰ اراکی - بدون محدودیت تعداد)"
    elif data == "help_upgrade":
      text = "⚡ **بخش تقویت و ارتقا:**\n\n- `تقویت نیرو [تعداد]` : تبدیل اراکی به غلامی (بدون سقف)\n- `تقویت غلامی [تعداد]` : تبدیل غلامی به پویا (بدون سقف)\n- `تقویت پویا [تعداد]` : تبدیل پویا به صفرنیگا (بدون سقف)"
    elif data == "help_spin":
      text = "🎡 **بخش شانس و گردونه:**\n\n- `گردونه` : چرخش گردونه با هزینه 100 نیرو"
    elif data == "help_back":
      keyboard_main = [
          [
              InlineKeyboardButton("⚔️ بخش نبرد و جنگ", callback_data="help_war"),
              InlineKeyboardButton("🛡️ ارتش و نیروها", callback_data="help_army")
          ],
          [
              InlineKeyboardButton("⚡ تقویت و ارتقا", callback_data="help_upgrade"),
              InlineKeyboardButton("🎡 شانس و گردونه", callback_data="help_spin")
          ]
      ]
      await query.edit_message_text(
          "📖 **منوی راهنمای جامع بازی اراکی‌ها**\n\nلطفاً یکی از بخش‌های زیر را انتخاب کنید:",
          reply_markup=InlineKeyboardMarkup(keyboard_main),
          parse_mode="Markdown"
      )
      return

    back_keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی راهنما", callback_data="help_back")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(back_keyboard), parse_mode="Markdown")
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
    joiner_is_owner_admin = (user_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False))
    joiner_total = calculate_total_soldiers(user_id, joiner_data[2], joiner_data[3], joiner_data[4], joiner_data[5], joiner_data[6])
    if not joiner_is_owner_admin and joiner_total < bet:
      await query.answer("موجودی شما برای این بازی کافی نیست!", show_alert=True)
      return

    creator_data = get_user(creator_id)
    creator_is_owner_admin = (creator_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False))

    if not creator_is_owner_admin:
      update_user(creator_id, max(0, creator_data[2] - bet), creator_data[3], creator_data[4], creator_data[5], creator_data[6])
    if not joiner_is_owner_admin:
      update_user(user_id, max(0, joiner_data[2] - bet), joiner_data[3], joiner_data[4], joiner_data[5], joiner_data[6])

    winner_id = random.choice([creator_id, user_id])
    loser_id = user_id if winner_id == creator_id else creator_id

    winner_data = get_user(winner_id)
    loser_data = get_user(loser_id)

    prize = get_war_prize(bet)
    winner_is_owner_admin = (winner_id == OWNER_ID and not owner_modes.get(OWNER_ID, {}).get("is_player_mode", False))
    if not winner_is_owner_admin:
      update_user(winner_id, winner_data[2] + prize, winner_data[3], winner_data[4], winner_data[5], winner_data[6])

    winner_name = war["creator_name"] if winner_id == creator_id else user.first_name
    loser_name = user.first_name if winner_id == creator_id else war["creator_name"]

    del active_wars[chat_id]

    final_winner_data = get_user(winner_id)
    final_loser_data = get_user(loser_id)

    await query.edit_message_text(
        f"⚔️ **نتیجه مسابقه اعلام شد!**\n\n"
        f"🏆 **برنده:** {winner_name}\n"
        f"💀 **بازنده:** {loser_name}\n\n"
        f"🎁 پاداش برنده: {prize} اراکی\n\n"
        f"👤 **موجودی جدید برنده ({winner_name}):** اراکی: {final_winner_data[2]} | کارگر: {final_winner_data[6]}\n"
        f"👤 **موجودی جدید بازنده ({loser_name}):** اراکی: {final_loser_data[2]} | کارگر: {final_loser_data[6]}",
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

  app.add_handler(MessageHandler(filters.COMMAND & filters.Regex("^/start$"), start_handler))
  app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
  app.add_handler(CallbackQueryHandler(button_handler))

  print("🤖 Bot is running and ready...")
  app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
  main()
