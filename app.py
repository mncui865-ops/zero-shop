import sqlite3
import asyncio
import logging
import nest_asyncio
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions,
    ChatMemberAdministrator, ChatMemberOwner
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

# ==================== الإعدادات الأساسية ====================
nest_asyncio.apply()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = "8700746570:AAEDSxqlAVJlijQL_feqdh0LsUhY91pzpcY"
ADMIN_ID = 7093004518
BOT_USERNAME = "sudaniTechsbitesbot"
WELCOME_IMAGE = "https://files.catbox.moe/c8sskq.jpg"

# ==================== قاعدة البيانات ====================
conn = sqlite3.connect("group_protection.db", check_same_thread=False)
cur = conn.cursor()

# جدول إعدادات المجموعات
cur.execute("""CREATE TABLE IF NOT EXISTS group_settings (
    chat_id INTEGER PRIMARY KEY,
    antilink INTEGER DEFAULT 0,
    antibadword INTEGER DEFAULT 0,
    antispam INTEGER DEFAULT 0,
    antiphoto INTEGER DEFAULT 0,
    antisticker INTEGER DEFAULT 0,
    antivideo INTEGER DEFAULT 0,
    badwords TEXT DEFAULT '',
    punishment TEXT DEFAULT 'mute',
    mute_minutes INTEGER DEFAULT 60,
    welcome_enabled INTEGER DEFAULT 1,
    welcome_text TEXT DEFAULT ''
)""")

# جدول المجموعات المسجلة
cur.execute("""CREATE TABLE IF NOT EXISTS bot_groups (
    chat_id INTEGER PRIMARY KEY,
    chat_title TEXT,
    added_at TEXT
)""")

# جدول تتبع السبام
cur.execute("""CREATE TABLE IF NOT EXISTS user_spam (
    chat_id INTEGER,
    user_id INTEGER,
    timestamps TEXT,
    PRIMARY KEY(chat_id, user_id)
)""")

# جدول المستخدمين النشطين
cur.execute("""CREATE TABLE IF NOT EXISTS active_users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT
)""")

conn.commit()

# ==================== دوال قاعدة البيانات ====================
def get_settings(chat_id):
    cur.execute("SELECT * FROM group_settings WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO group_settings(chat_id) VALUES(?)", (chat_id,))
        conn.commit()
        return get_settings(chat_id)
    return {
        "antilink": row[1], "antibadword": row[2], "antispam": row[3],
        "antiphoto": row[4], "antisticker": row[5], "antivideo": row[6],
        "badwords": row[7].split(",") if row[7] else [],
        "punishment": row[8], "mute_minutes": row[9],
        "welcome_enabled": row[10], "welcome_text": row[11]
    }

def update_setting(chat_id, key, value):
    cur.execute(f"UPDATE group_settings SET {key}=? WHERE chat_id=?", (value, chat_id))
    conn.commit()

def add_group(chat_id, chat_title):
    cur.execute("INSERT OR REPLACE INTO bot_groups(chat_id, chat_title, added_at) VALUES(?,?,?)",
                (chat_id, chat_title, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()

def get_user_groups(user_id):
    # يعرض كل المجموعات (للمطور) أو مجموعات المستخدم (للمستخدمين العاديين)
    if user_id == ADMIN_ID:
        cur.execute("SELECT chat_id, chat_title FROM bot_groups ORDER BY chat_title")
    else:
        # للمستخدمين العاديين، نعرض كل المجموعات (يمكن تعديلها لترتبط بعضويتهم)
        cur.execute("SELECT chat_id, chat_title FROM bot_groups ORDER BY chat_title")
    groups = []
    for row in cur.fetchall():
        if row[0] < 0:  # فقط المجموعات (الأيدي السالب)
            groups.append({"id": row[0], "title": row[1]})
    return groups

def add_active_user(user_id, username, first_name):
    cur.execute("INSERT OR REPLACE INTO active_users(user_id, username, first_name) VALUES(?,?,?)",
                (user_id, username or "NoUsername", first_name or "User"))
    conn.commit()

def get_all_users():
    cur.execute("SELECT user_id FROM active_users")
    return [row[0] for row in cur.fetchall()]

def is_admin(user_id, chat_id, member):
    return isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)) or user_id == ADMIN_ID

# ==================== لوحات المفاتيح ====================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ أضفني لمجموعة", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton("📋 مجموعاتي", callback_data="my_groups")],
        [InlineKeyboardButton("🛡️ لوحة الحماية", callback_data="panel")]
    ])

def panel_keyboard(chat_id):
    s = get_settings(chat_id)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{'✅' if s['antilink'] else '❌'} مضاد الروابط", callback_data="toggle_antilink")],
        [InlineKeyboardButton(f"{'✅' if s['antibadword'] else '❌'} مضاد الكلمات السيئة", callback_data="toggle_antibad")],
        [InlineKeyboardButton(f"{'✅' if s['antispam'] else '❌'} مضاد السبام", callback_data="toggle_antispam")],
        [InlineKeyboardButton(f"{'✅' if s['antiphoto'] else '❌'} منع الصور", callback_data="toggle_antiphoto")],
        [InlineKeyboardButton(f"{'✅' if s['antisticker'] else '❌'} منع الملصقات", callback_data="toggle_antisticker")],
        [InlineKeyboardButton(f"{'✅' if s['antivideo'] else '❌'} منع الفيديو", callback_data="toggle_antivideo")],
        [InlineKeyboardButton(f"{'✅' if s['welcome_enabled'] else '❌'} الترحيب", callback_data="toggle_welcome")],
        [InlineKeyboardButton("📝 تعديل الكلمات السيئة", callback_data="edit_badwords")],
        [InlineKeyboardButton("⚖️ نوع العقوبة", callback_data="set_punishment")],
        [InlineKeyboardButton("⏱️ مدة الكتم", callback_data="set_mute_time")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
    ])

def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 إذاعة للجميع", callback_data="broadcast_all")],
        [InlineKeyboardButton("📢 إذاعة للمجموعات", callback_data="broadcast_groups")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="stats")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
    ])

def punishment_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 حظر", callback_data="punish_ban"),
         InlineKeyboardButton("🔇 كتم", callback_data="punish_mute"),
         InlineKeyboardButton("⚠️ تحذير وطرد", callback_data="punish_kick")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="panel")]
    ])

def mute_time_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("5 دقائق", callback_data="mute_5"),
         InlineKeyboardButton("30 دقيقة", callback_data="mute_30"),
         InlineKeyboardButton("1 ساعة", callback_data="mute_60")],
        [InlineKeyboardButton("6 ساعات", callback_data="mute_360"),
         InlineKeyboardButton("1 يوم", callback_data="mute_1440"),
         InlineKeyboardButton("3 أيام", callback_data="mute_4320")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="set_punishment")]
    ])

def groups_keyboard(groups, page=0):
    buttons = []
    per_page = 8
    start = page * per_page
    end = start + per_page

    for group in groups[start:end]:
        buttons.append([InlineKeyboardButton(group['title'][:30], callback_data=f"group_{group['id']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"groups_page_{page-1}"))
    if end < len(groups):
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"groups_page_{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)

# ==================== دوال الأوامر ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    add_active_user(user_id, username, first_name)

    if update.message.chat.type == "private":
        if user_id == ADMIN_ID:
            await update.message.reply_text(
                "🤖 أهلاً بك في لوحة تحكم المطور\n"
                "اختر العملية:",
                reply_markup=admin_panel_keyboard()
            )
        else:
            await update.message.reply_text(
                "🤖 أهلاً بك في بوت حماية القروبات\n"
                "أنا بوت متكامل لحماية مجموعتك من السبام والروابط والكلمات السيئة.\n"
                "ضيفني مشرف في قروبك وادخل لوحة التحكم.",
                reply_markup=main_keyboard()
            )

    if update.message.chat.type in ["group", "supergroup"]:
        add_group(update.message.chat.id, update.message.chat.title)

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /panel داخل المجموعة"""
    chat_id = update.effective_chat.id
    
    if chat_id > 0:
        await update.message.reply_text(
            "⚠️ هذا الأمر يعمل داخل المجموعات فقط.\n"
            "استخدم /start ثم 📋 مجموعاتي لاختيار مجموعة.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 مجموعاتي", callback_data="my_groups")]
            ])
        )
        return

    try:
        member = await context.bot.get_chat_member(chat_id, update.effective_user.id)
        if not is_admin(update.effective_user.id, chat_id, member):
            await update.message.reply_text("⛔ للمشرفين فقط.")
            return

        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if not isinstance(bot_member, (ChatMemberAdministrator, ChatMemberOwner)):
            await update.message.reply_text("❌ البوت ليس مشرفاً في هذه المجموعة.")
            return

        s = get_settings(chat_id)
        chat = await context.bot.get_chat(chat_id)
        await update.message.reply_text(
            f"🛡️ لوحة حماية: {chat.title}",
            reply_markup=panel_keyboard(chat_id)
        )
    except Exception as e:
        logging.error(f"Panel error: {e}")
        await update.message.reply_text("⚠️ حدث خطأ. تأكد من صلاحيات البوت.")

async def my_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    groups = get_user_groups(user_id)

    if not groups:
        await query.edit_message_text(
            "📋 لم يتم العثور على مجموعات.\nأضف البوت لمجموعة واجعله مشرف أولاً.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]])
        )
        return

    await query.edit_message_text(
        f"📋 مجموعاتك: {len(groups)}\nاختار مجموعة للدخول للوحة التحكم:",
        reply_markup=groups_keyboard(groups, 0)
    )

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فتح لوحة التحكم من callback"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # استخراج chat_id من البيانات
    if "group_" in query.data:
        chat_id = int(query.data.split("_")[1])
    else:
        # إذا كان الزر من الخاص بدون مجموعة محددة
        await my_groups(update, context)
        return

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if not is_admin(user_id, chat_id, member):
            await query.answer("للمشرفين فقط", show_alert=True)
            return

        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if not isinstance(bot_member, (ChatMemberAdministrator, ChatMemberOwner)):
            await query.answer("البوت ليس مشرفاً في هذه المجموعة", show_alert=True)
            return

        s = get_settings(chat_id)
        chat = await context.bot.get_chat(chat_id)
        await query.edit_message_text(
            f"🛡️ لوحة حماية: {chat.title}",
            reply_markup=panel_keyboard(chat_id)
        )
    except Exception as e:
        logging.error(f"Panel callback error: {e}")
        await query.answer("حدث خطأ. تأكد من صلاحيات البوت", show_alert=True)

async def toggle_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    data = query.data

    member = await context.bot.get_chat_member(chat_id, query.from_user.id)
    if not is_admin(query.from_user.id, chat_id, member):
        await query.answer("للمشرفين فقط", show_alert=True)
        return

    if data == "toggle_antilink":
        s = get_settings(chat_id)
        update_setting(chat_id, "antilink", 0 if s["antilink"] else 1)
    elif data == "toggle_antibad":
        s = get_settings(chat_id)
        update_setting(chat_id, "antibadword", 0 if s["antibadword"] else 1)
    elif data == "toggle_antispam":
        s = get_settings(chat_id)
        update_setting(chat_id, "antispam", 0 if s["antispam"] else 1)
    elif data == "toggle_antiphoto":
        s = get_settings(chat_id)
        update_setting(chat_id, "antiphoto", 0 if s["antiphoto"] else 1)
    elif data == "toggle_antisticker":
        s = get_settings(chat_id)
        update_setting(chat_id, "antisticker", 0 if s["antisticker"] else 1)
    elif data == "toggle_antivideo":
        s = get_settings(chat_id)
        update_setting(chat_id, "antivideo", 0 if s["antivideo"] else 1)
    elif data == "toggle_welcome":
        s = get_settings(chat_id)
        update_setting(chat_id, "welcome_enabled", 0 if s["welcome_enabled"] else 1)
    elif data == "set_punishment":
        await query.edit_message_text("⚖️ اختر نوع العقوبة:", reply_markup=punishment_keyboard())
        return
    elif data.startswith("punish_"):
        punish = data.split("_")[1]
        update_setting(chat_id, "punishment", punish)
        if punish == "mute":
            await query.edit_message_text("⏱️ اختر مدة الكتم:", reply_markup=mute_time_keyboard())
            return
        await query.answer(f"تم تعيين العقوبة: {punish}")

    s = get_settings(chat_id)
    chat = await context.bot.get_chat(chat_id)
    await query.edit_message_text(
        f"🛡️ لوحة حماية: {chat.title}",
        reply_markup=panel_keyboard(chat_id)
    )

async def set_mute_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    minutes = int(query.data.split("_")[1])

    member = await context.bot.get_chat_member(chat_id, query.from_user.id)
    if not is_admin(query.from_user.id, chat_id, member):
        await query.answer("للمشرفين فقط", show_alert=True)
        return

    update_setting(chat_id, "mute_minutes", minutes)
    await query.answer(f"تم تعيين مدة الكتم: {minutes} دقيقة")

    s = get_settings(chat_id)
    chat = await context.bot.get_chat(chat_id)
    await query.edit_message_text(
        f"🛡️ لوحة حماية: {chat.title}",
        reply_markup=panel_keyboard(chat_id)
    )

async def edit_badwords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id

    member = await context.bot.get_chat_member(chat_id, query.from_user.id)
    if not is_admin(query.from_user.id, chat_id, member):
        await query.answer("للمشرفين فقط", show_alert=True)
        return

    context.user_data["state"] = f"waiting_badwords_{chat_id}"
    await query.edit_message_text(
        "📝 أرسل الكلمات السيئة مفصولة بفاصلة\n"
        "مثال: كلمة1,كلمة2,كلمة3\n"
        "أرسل 'حذف' لحذف كل الكلمات"
    )

async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("للمطور فقط", show_alert=True)
        return

    if query.data == "broadcast_all":
        context.user_data["broadcast_type"] = "all"
        await query.edit_message_text("📢 أرسل رسالة الإذاعة الآن\nسيتم إرسالها لكل المستخدمين")
    elif query.data == "broadcast_groups":
        context.user_data["broadcast_type"] = "groups"
        await query.edit_message_text("📢 أرسل رسالة الإذاعة الآن\nسيتم إرسالها لكل المجموعات")

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    b_type = context.user_data.get("broadcast_type")
    if not b_type:
        return

    msg = update.message
    sent = 0
    fail = 0

    if b_type == "all":
        users = get_all_users()
        for uid in users:
            try:
                await msg.copy(uid)
                sent += 1
                await asyncio.sleep(0.1)
            except Exception:
                fail += 1
    elif b_type == "groups":
        groups = get_user_groups(ADMIN_ID)
        for group in groups:
            try:
                await msg.copy(group["id"])
                sent += 1
                await asyncio.sleep(0.1)
            except Exception:
                fail += 1

    await update.message.reply_text(f"✅ تم الإرسال\nنجح: {sent}\nفشل: {fail}")
    context.user_data.pop("broadcast_type", None)

async def handle_badwords_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state", "")
    if not state.startswith("waiting_badwords_"):
        return

    chat_id = int(state.split("_")[2])
    text = update.message.text.strip()

    member = await context.bot.get_chat_member(chat_id, update.effective_user.id)
    if not is_admin(update.effective_user.id, chat_id, member):
        await update.message.reply_text("⛔ ليس لديك صلاحية.")
        return

    if text.lower() == "حذف":
        update_setting(chat_id, "badwords", "")
        await update.message.reply_text("✅ تم حذف كل الكلمات السيئة")
    else:
        update_setting(chat_id, "badwords", text)
        await update.message.reply_text(f"✅ تم حفظ الكلمات السيئة:\n{text}")

    context.user_data.pop("state", None)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text or ""

    # معالجة المدخلات النصية الخاصة
    if chat_id > 0:
        if context.user_data.get("state", "").startswith("waiting_badwords_"):
            await handle_badwords_input(update, context)
            return
        if context.user_data.get("broadcast_type"):
            await handle_broadcast(update, context)
            return
        return

    # التحقق من صلاحيات المستخدم
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if is_admin(user_id, chat_id, member):
            return
    except Exception:
        pass

    s = get_settings(chat_id)

    # مضاد الروابط
    if s["antilink"]:
        if any(x in text.lower() for x in ["http://", "https://", "t.me/", "telegram.me", "www."]):
            await apply_punishment(update, context, "إرسال رابط")
            return

    # مضاد الكلمات السيئة
    if s["antibadword"]:
        for word in s["badwords"]:
            if word and word.lower() in text.lower():
                await apply_punishment(update, context, f"كلمة سيئة: {word}")
                return

    # مضاد السبام (5 رسائل خلال 10 ثوانٍ)
    if s["antispam"]:
        now = datetime.now().timestamp()
        cur.execute("SELECT timestamps FROM user_spam WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        row = cur.fetchone()

        times = []
        if row and row[0]:
            times = [float(t) for t in row[0].split(",") if t]

        # حذف الطوابع الأقدم من 10 ثوانٍ
        times = [t for t in times if now - t < 10]
        times.append(now)

        cur.execute("INSERT OR REPLACE INTO user_spam(chat_id, user_id, timestamps) VALUES(?,?,?)",
                    (chat_id, user_id, ",".join(map(str, times))))
        conn.commit()

        if len(times) > 5:
            await apply_punishment(update, context, "سبام - رسائل متكررة")
            return

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الميديا (صور، فيديو، ملصقات)"""
    if not update.message:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id > 0:
        return

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if is_admin(user_id, chat_id, member):
            return
    except Exception:
        pass

    s = get_settings(chat_id)

    if s["antiphoto"] and update.message.photo:
        await apply_punishment(update, context, "إرسال صورة")
        return

    if s["antisticker"] and update.message.sticker:
        await apply_punishment(update, context, "إرسال ملصق")
        return

    if s["antivideo"] and update.message.video:
        await apply_punishment(update, context, "إرسال فيديو")
        return

async def apply_punishment(update: Update, context: ContextTypes.DEFAULT_TYPE, reason):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    s = get_settings(chat_id)
    punish = s["punishment"]

    try:
        await update.message.delete()
        await asyncio.sleep(0.5)

        if punish == "ban":
            await context.bot.ban_chat_member(chat_id, user_id)
            await update.message.reply_text(f"🚫 تم حظر العضو\nالسبب: {reason}")

        elif punish == "kick":
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.unban_chat_member(chat_id, user_id)
            await update.message.reply_text(f"⚠️ تم طرد العضو\nالسبب: {reason}")

        elif punish == "mute":
            minutes = s["mute_minutes"]
            until = datetime.now() + timedelta(minutes=minutes)
            await context.bot.restrict_chat_member(
                chat_id, user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until
            )
            await update.message.reply_text(
                f"🔇 تم كتم العضو لمدة {minutes} دقيقة\n"
                f"السبب: {reason}\n"
                f"⚠️ فقط مشرفي القروب يمكنهم فك الكتم"
            )
    except Exception as e:
        logging.error(f"Punishment error: {e}")
        await update.message.reply_text("❌ حدث خطأ. تأكد أن البوت مشرف ولديه صلاحيات الحظر والكتم")

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    s = get_settings(chat_id)

    if not s["welcome_enabled"]:
        return

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue

        name = member.full_name
        username = f"@{member.username}" if member.username else "لا يوجد"
        user_id = member.id

        welcome = s["welcome_text"]
        if not welcome:
            welcome = f"""🌿 أهلاً وسهلاً بك في القروب 🌿

👤 الاسم: {name}
━━━━━━━━━━━━━━
👤 اليوزر: {username}
━━━━━━━━━━━━━━
🆔 الايدي: `{user_id}`
━━━━━━━━━━━━━━
شكراً لانضمامك للقروب! نورتنا 💙"""

        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=WELCOME_IMAGE,
                caption=welcome,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logging.error(f"Welcome error: {e}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "back_main":
        if query.from_user.id == ADMIN_ID:
            await query.edit_message_text(
                "🤖 لوحة تحكم المطور",
                reply_markup=admin_panel_keyboard()
            )
        else:
            await query.edit_message_text(
                "🤖 القائمة الرئيسية",
                reply_markup=main_keyboard()
            )
    elif data == "my_groups":
        await my_groups(update, context)
    elif data == "panel":
        # توجيه المستخدم إلى قائمة المجموعات بدلاً من خطأ
        await my_groups(update, context)
    elif data.startswith("group_"):
        await panel(update, context)
    elif data.startswith("groups_page_"):
        page = int(data.split("_")[2])
        groups = get_user_groups(query.from_user.id)
        await query.edit_message_text(
            f"📋 مجموعاتك: {len(groups)}",
            reply_markup=groups_keyboard(groups, page)
        )
    elif data.startswith("toggle_") or data.startswith("punish_") or data == "set_punishment":
        await toggle_setting(update, context)
    elif data.startswith("mute_"):
        await set_mute_time(update, context)
    elif data == "edit_badwords":
        await edit_badwords(update, context)
    elif data in ["broadcast_all", "broadcast_groups"]:
        await broadcast_handler(update, context)
    elif data == "stats":
        users = len(get_all_users())
        groups = len(get_user_groups(ADMIN_ID))
        await query.edit_message_text(
            f"📊 إحصائيات البوت\n"
            f"👥 المستخدمين: {users}\n"
            f"👥 المجموعات: {groups}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]])
        )

# ==================== التشغيل الرئيسي ====================
async def main():
    global BOT_USERNAME
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    bot_info = await app.bot.get_me()
    BOT_USERNAME = bot_info.username

    # إضافة الهاندلرات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panel", panel_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Sticker.ALL, handle_media))

    print(f"✅ البوت @{BOT_USERNAME} شغال الآن...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
