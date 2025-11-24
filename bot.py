import asyncio
import sqlite3
from datetime import datetime, date, time, timedelta

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============ CONFIG ============

BOT_TOKEN = "8534911818:AAGtLGMxPiT1aa6ocj1lJJoRkyc-3yLznO0"  # এখানে নিজের টোকেন দাও
DB_PATH = "simple_uni.db"

# এখানে যার যার username ( @ ছাড়া ) admin হবে
ADMIN_USERNAMES = {"mrx_46x", "your_friend_username"}

# ============ DATABASE ============

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        cur = conn.cursor()

        # ইউজার লিস্ট (broadcast এর জন্য)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id     INTEGER PRIMARY KEY,
            username    TEXT,
            first_name  TEXT
        )
        """)

        # weekly routine
        cur.execute("""
        CREATE TABLE IF NOT EXISTS routine (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            day     TEXT NOT NULL,         -- mon, tue, wed ...
            time    TEXT NOT NULL,         -- HH:MM
            course  TEXT NOT NULL,
            room    TEXT,
            teacher TEXT
        )
        """)

        # notices
        cur.execute("""
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body  TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # today’s food (date based)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS food_menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_date TEXT UNIQUE,   -- YYYY-MM-DD
            menu TEXT NOT NULL
        )
        """)

        # teacher list
        cur.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT,
            contact TEXT
        )
        """)

        # assignments
        cur.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            course TEXT,
            deadline TEXT NOT NULL  -- YYYY-MM-DD
        )
        """)

        conn.commit()


# ============ HELPERS ============

def is_admin(user) -> bool:
    if not user:
        return False
    uname = (user.username or "").lower()
    return uname in {u.lower() for u in ADMIN_USERNAMES}


async def ensure_user(update: Update):
    user = update.effective_user
    if not user:
        return
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO users (chat_id, username, first_name) VALUES (?, ?, ?)",
                    (user.id, user.username or "", user.first_name or ""))
        conn.commit()


def build_main_keyboard(is_admin_flag: bool) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton("📅 Full Routine"), KeyboardButton("🗓 Today Classes")],
        [KeyboardButton("📢 Notices"), KeyboardButton("🍽 Today Food")],
        [KeyboardButton("👨‍🏫 Teacher List"), KeyboardButton("📚 Assignments")],
    ]
    if is_admin_flag:
        rows.append([
            KeyboardButton("⚙ Admin: Add Notice"),
            KeyboardButton("⚙ Admin: Add Routine"),
        ])
        rows.append([
            KeyboardButton("⚙ Admin: Add Food"),
            KeyboardButton("⚙ Admin: Add Assignment"),
        ])
        rows.append([
            KeyboardButton("⚙ Admin: Broadcast"),
        ])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def weekday_str(dt: datetime | date) -> str:
    return dt.strftime("%a").lower()  # mon, tue, wed, ...


# ============ PUBLIC COMMANDS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    admin_flag = is_admin(update.effective_user)

    kb = build_main_keyboard(admin_flag)
    await update.message.reply_text(
        "Assalamu Alaikum! 😊\n"
        "Welcome to Simple University Helper Bot.\n\n"
        "নিচের মেনু থেকে যেকোনো অপশন সিলেক্ট করো 👇",
        reply_markup=kb
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - main menu\n"
        "/routine - full routine\n"
        "/today - today classes\n"
        "/notices - latest notices\n"
        "/food - today food\n"
        "/assignments - upcoming assignments\n\n"
        "Admin only:\n"
        "/add_notice Title | Body\n"
        "/add_routine DAY | HH:MM | Course | Room | Teacher\n"
        "/clear_routine DAY\n"
        "/add_food Menu text for today\n"
        "/add_assignment Title | YYYY-MM-DD\n"
        "/add_teacher Name | Subject | Contact\n"
        "/broadcast Text..."
    )


async def routine_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_full_routine_text()
    await update.message.reply_text(text or "No routine saved yet.")


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_today_classes_text()
    await update.message.reply_text(text or "No class today.")


async def notices_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_notices_text()
    await update.message.reply_text(text or "No notices yet.")


async def food_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_today_food_text()
    await update.message.reply_text(text or "No food menu for today.")


async def assignments_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_assignments_text()
    await update.message.reply_text(text or "No assignments found.")


# ============ TEXT BUTTON HANDLER ============

async def text_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "📅 Full Routine":
        return await routine_cmd(update, context)
    if text == "🗓 Today Classes":
        return await today_cmd(update, context)
    if text == "📢 Notices":
        return await notices_cmd(update, context)
    if text == "🍽 Today Food":
        return await food_cmd(update, context)
    if text == "👨‍🏫 Teacher List":
        t = get_teachers_text()
        return await update.message.reply_text(t or "No teachers added yet.")
    if text == "📚 Assignments":
        return await assignments_cmd(update, context)

    # admin texts
    if text.startswith("⚙ Admin"):
        await update.message.reply_text(
            "এই কাজগুলো কমান্ড দিয়ে করতে হবে।\n"
            "/add_notice, /add_routine, /add_food, /add_assignment, /broadcast"
        )


# ============ DATA FETCHERS (TEXT) ============

def get_full_routine_text() -> str:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT day, time, course, room, teacher FROM routine ORDER BY day, time")
        rows = cur.fetchall()

    if not rows:
        return ""

    msg = "📅 Full Routine\n\n"
    for r in rows:
        msg += f"{r['day'].upper()} {r['time']} - {r['course']} ({r['teacher']}) Room: {r['room']}\n"
    return msg


def get_today_classes_text() -> str:
    today = weekday_str(date.today())
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT time, course, room, teacher FROM routine WHERE day=? ORDER BY time",
            (today,)
        )
        rows = cur.fetchall()

    if not rows:
        return ""

    msg = f"🗓 Today Classes ({today.upper()})\n\n"
    for r in rows:
        msg += f"{r['time']} - {r['course']} ({r['teacher']}) Room: {r['room']}\n"
    return msg


def get_notices_text() -> str:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT title, body, created_at FROM notices ORDER BY id DESC LIMIT 10")
        rows = cur.fetchall()

    if not rows:
        return ""

    msg = "📢 Latest Notices\n\n"
    for r in rows:
        msg += f"🔹 {r['title']}\n{r['body']}\n({r['created_at']})\n\n"
    return msg


def get_today_food_text() -> str:
    today = date.today().strftime("%Y-%m-%d")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT menu FROM food_menu WHERE day_date=?", (today,))
        row = cur.fetchone()

    if not row:
        return ""
    return f"🍽 Today Food ({today})\n\n{row['menu']}"


def get_assignments_text() -> str:
    today = date.today()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT title, course, deadline FROM assignments ORDER BY deadline")
        rows = cur.fetchall()

    if not rows:
        return ""

    msg = "📚 Assignments\n\n"
    for r in rows:
        d = datetime.strptime(r['deadline'], "%Y-%m-%d").date()
        days_left = (d - today).days
        msg += f"🔹 {r['title']} ({r['course'] or 'N/A'}) - {r['deadline']} (in {days_left} days)\n"
    return msg


def get_teachers_text() -> str:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, subject, contact FROM teachers ORDER BY name")
        rows = cur.fetchall()

    if not rows:
        return ""

    msg = "👨‍🏫 Teacher List\n\n"
    for r in rows:
        msg += f"{r['name']} - {r['subject'] or ''} {r['contact'] or ''}\n"
    return msg


# ============ ADMIN COMMANDS ============

async def admin_only(update: Update) -> bool:
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Only admin can use this command.")
        return False
    return True


async def add_notice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return
    if not context.args:
        return await update.message.reply_text("Usage: /add_notice Title | Body")

    text = " ".join(context.args)
    if "|" not in text:
        return await update.message.reply_text("Format: /add_notice Title | Body")

    title, body = [part.strip() for part in text.split("|", 1)]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notices (title, body, created_at) VALUES (?, ?, ?)",
            (title, body, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()

    await update.message.reply_text("✅ Notice added.")


async def add_routine_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return
    if not context.args:
        return await update.message.reply_text(
            "Usage: /add_routine DAY | HH:MM | Course | Room | Teacher"
        )

    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 5:
        return await update.message.reply_text(
            "Format: /add_routine DAY | HH:MM | Course | Room | Teacher"
        )

    day, tm, course, room, teacher = parts
    day = day.lower()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO routine (day, time, course, room, teacher) VALUES (?, ?, ?, ?, ?)",
            (day, tm, course, room, teacher)
        )
        conn.commit()
    await update.message.reply_text("✅ Routine row added.")


async def clear_routine_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return
    if not context.args:
        return await update.message.reply_text("Usage: /clear_routine DAY (mon,tue,wed...)")
    day = context.args[0].lower()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM routine WHERE day=?", (day,))
        conn.commit()
    await update.message.reply_text(f"✅ Cleared routine for {day}.")


async def add_food_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return
    if not context.args:
        return await update.message.reply_text("Usage: /add_food menu text (for today)")

    menu_text = " ".join(context.args)
    today = date.today().strftime("%Y-%m-%d")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO food_menu (day_date, menu) VALUES (?, ?)",
            (today, menu_text)
        )
        conn.commit()
    await update.message.reply_text("✅ Today's food menu set.")


async def add_assignment_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return
    if not context.args:
        return await update.message.reply_text(
            "Usage: /add_assignment Title | YYYY-MM-DD"
        )

    text = " ".join(context.args)
    if "|" not in text:
        return await update.message.reply_text(
            "Format: /add_assignment Title | YYYY-MM-DD"
        )

    title, deadline = [p.strip() for p in text.split("|", 1)]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO assignments (title, course, deadline) VALUES (?, ?, ?)",
            (title, None, deadline)
        )
        conn.commit()
    await update.message.reply_text("✅ Assignment added.")


async def add_teacher_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return
    if not context.args:
        return await update.message.reply_text(
            "Usage: /add_teacher Name | Subject | Contact"
        )

    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        return await update.message.reply_text(
            "Format: /add_teacher Name | Subject | Contact"
        )

    name, subject, contact = parts
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO teachers (name, subject, contact) VALUES (?, ?, ?)",
            (name, subject, contact)
        )
        conn.commit()
    await update.message.reply_text("✅ Teacher added.")


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return
    if not context.args:
        return await update.message.reply_text("Usage: /broadcast Your message")

    msg = " ".join(context.args)
    await broadcast_to_all(context, f"📢 Broadcast:\n{msg}")
    await update.message.reply_text("✅ Broadcast sent.")


async def broadcast_to_all(context: ContextTypes.DEFAULT_TYPE, text: str):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM users")
        rows = cur.fetchall()

    for r in rows:
        try:
            await context.bot.send_message(chat_id=r["chat_id"], text=text)
        except Exception:
            continue


# ============ AUTO JOBS (JobQueue) ============

async def daily_food_job(context: ContextTypes.DEFAULT_TYPE):
    text = get_today_food_text()
    if not text:
        return
    await broadcast_to_all(context, text)


async def class_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    # প্রতি মিনিটে today routine দেখে 5 মিনিট আগে alert
    now = datetime.now()
    today = weekday_str(now.date())

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT time, course, room, teacher FROM routine WHERE day=?", (today,))
        rows = cur.fetchall()

    for r in rows:
        class_time = datetime.strptime(r["time"], "%H:%M").time()
        class_dt = datetime.combine(now.date(), class_time)
        diff = (class_dt - now).total_seconds()
        if 0 < diff <= 5 * 60:  # পরবর্তী ৫ মিনিটের মধ্যে
            text = (f"⏰ Reminder: {r['course']} ক্লাস শুরু হবে "
                    f"{r['time']} টায় (Room: {r['room']}, Teacher: {r['teacher']})")
            await broadcast_to_all(context, text)


async def assignment_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    today = date.today()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT title, deadline FROM assignments")
        rows = cur.fetchall()

    for r in rows:
        d = datetime.strptime(r["deadline"], "%Y-%m-%d").date()
        days_left = (d - today).days
        if days_left in (3, 1):
            when_txt = "৩ দিন বাকি" if days_left == 3 else "আগামীকাল শেষ দিন!"
            text = f"📚 Assignment Reminder:\n{r['title']}\nDeadline: {r['deadline']} ({when_txt})"
            await broadcast_to_all(context, text)


# ============ MAIN ============

async def main():
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("routine", routine_cmd))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("notices", notices_cmd))
    app.add_handler(CommandHandler("food", food_cmd))
    app.add_handler(CommandHandler("assignments", assignments_cmd))

    # admin commands
    app.add_handler(CommandHandler("add_notice", add_notice_cmd))
    app.add_handler(CommandHandler("add_routine", add_routine_cmd))
    app.add_handler(CommandHandler("clear_routine", clear_routine_cmd))
    app.add_handler(CommandHandler("add_food", add_food_cmd))
    app.add_handler(CommandHandler("add_assignment", add_assignment_cmd))
    app.add_handler(CommandHandler("add_teacher", add_teacher_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))

    # text menu
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_menu_handler))

    # job queue
    jq = app.job_queue
    jq.run_daily(daily_food_job, time=time(12, 30))
    jq.run_repeating(class_reminder_job, interval=60, first=10)
    jq.run_daily(assignment_reminder_job, time=time(9, 0))

    print("🚀 Simple University Helper Bot running...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())