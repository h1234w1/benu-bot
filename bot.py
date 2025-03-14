import os
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = json.loads(os.environ.get("GOOGLE_CREDENTIALS", "{}"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("BenuBotData")
training_sheet = sheet.worksheet("TrainingSignups")
network_sheet = sheet.worksheet("NetworkingRegistrations")

# Scheduler for notifications
scheduler = AsyncIOScheduler()
scheduler.start()

# Manager’s Telegram ID (replace with yours or a bot’s ID)
MANAGER_CHAT_ID = "YOUR_MANAGER_CHAT_ID"

# Training data (update as needed)
UPCOMING_TRAININGS = [
    {"name": "Biscuit Production Basics", "date": "2025-04-15", "resources": None},
    {"name": "Marketing for Startups", "date": "2025-04-20", "resources": None},
]
PAST_TRAININGS = [
    {"name": "Intro to Fortification", "date": "2025-03-10", "video": "https://youtube.com/example", "resources": "https://drive.google.com/example"},
]

# Bot functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Benu’s Startup Support Bot!\n"
        "Commands:\n"
        "/trainings - View trainings\n"
        "/networking - Join the network\n"
        "/news - Latest updates\n"
        "/contact - Reach us\n"
        "/subscribenews - News updates"
    )

async def trainings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    past_text = "Past Trainings:\n" + "\n".join(
        f"- {t['name']} ({t['date']}): {t['video'] or 'No video'}, {t['resources'] or 'No resources'}"
        for t in PAST_TRAININGS
    )
    upcoming_text = "Upcoming Trainings:\n" + "\n".join(
        f"- {t['name']} ({t['date']}) - Reply /signup to join"
        for t in UPCOMING_TRAININGS
    )
    await update.message.reply_text(f"{past_text}\n\n{upcoming_text}")

async def signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    context.user_data["signup_step"] = "name"
    await update.message.reply_text("Please provide your full name:")

async def networking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    network_data = network_sheet.get_all_records()
    categories = {}
    for entry in network_data:
        for cat in entry["Categories"].split(","):
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(f"{entry['Company']} - {entry['Description']} - "
                                  f"{'Contact: ' + entry['Phone'] if entry['PublicEmail'] == 'Yes' else 'Private'}")
    
    text = "Network by Category:\n"
    for cat, entries in categories.items():
        text += f"\n{cat}:\n" + "\n".join(f"- {entry}" for entry in entries)
    text += "\n\nReply /register to join the network!"
    await update.message.reply_text(text)

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    context.user_data["register_step"] = "company"
    await update.message.reply_text("Please provide your company name:")

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Latest Announcements:\n"
        "1. March 12, 2025: Benu secured ETB 2.9M from SWR Ethiopia.\n"
        "2. April 10, 2025: First training held—29 saleswomen trained! See /trainings.\n"
        "3. May 2025: New production line launches.\n"
        "4. May 15, 2025: Networking Event—register at /networking or /trainings.\n"
        "Use /subscribenews for updates!"
    )

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Contact Us:\n"
        "Email: benu@example.com\n"
        "Phone: +251921756683\n"
        "Address: Addis Ababa, Bole Sub city, Woreda 03, H.N. 4/10/A5/FL8"
    )

async def subscribenews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if training_sheet.find(str(chat_id)) is None:
        training_sheet.append_row([str(chat_id), "", "", "", "", datetime.now().isoformat()])
    await update.message.reply_text("Subscribed to news updates!")

# Handle multi-step replies
async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text

    # Training signup flow
    if "signup_step" in context.user_data:
        step = context.user_data["signup_step"]
        if step == "name":
            context.user_data["name"] = text
            context.user_data["signup_step"] = "phone"
            await update.message.reply_text("Please provide your phone number:")
        elif step == "phone":
            context.user_data["phone"] = text
            context.user_data["signup_step"] = "email"
            await update.message.reply_text("Please provide your email:")
        elif step == "email":
            context.user_data["email"] = text
            context.user_data["signup_step"] = "company"
            await update.message.reply_text("Please provide your company name:")
        elif step == "company":
            context.user_data["company"] = text
            data = [str(chat_id), context.user_data["name"], context.user_data["phone"],
                    context.user_data["email"], context.user_data["company"], datetime.now().isoformat()]
            training_sheet.append_row(data)
            await context.bot.send_message(MANAGER_CHAT_ID, f"New Signup: {data[1:]}")
            await update.message.reply_text(f"Thanks for signing up, {data[1]}!")
            del context.user_data["signup_step"]

    # Networking registration flow
    elif "register_step" in context.user_data:
        step = context.user_data["register_step"]
        if step == "company":
            context.user_data["company"] = text
            context.user_data["register_step"] = "phone"
            await update.message.reply_text("Please provide your phone number:")
        elif step == "phone":
            context.user_data["phone"] = text
            context.user_data["register_step"] = "email"
            await update.message.reply_text("Please provide your email:")
        elif step == "email":
            context.user_data["email"] = text
            context.user_data["register_step"] = "description"
            await update.message.reply_text("Please provide a description of what your company does:")
        elif step == "description":
            context.user_data["description"] = text
            context.user_data["register_step"] = "manager"
            await update.message.reply_text("Please provide the manager’s name:")
        elif step == "manager":
            context.user_data["manager"] = text
            context.user_data["register_step"] = "categories"
            keyboard = [
                [InlineKeyboardButton("Food Production", callback_data="cat:Food Production"),
                 InlineKeyboardButton("Packaging", callback_data="cat:Packaging")],
                [InlineKeyboardButton("Marketing", callback_data="cat:Marketing"),
                 InlineKeyboardButton("Sourcing", callback_data="cat:Sourcing")],
                [InlineKeyboardButton("Done", callback_data="cat:done")]
            ]
            await update.message.reply_text("Select categories (click Done when finished):", reply_markup=InlineKeyboardMarkup(keyboard))
        elif step == "public":
            context.user_data["public"] = text.lower() in ["yes", "y"]
            data = [str(chat_id), context.user_data["company"], context.user_data["phone"],
                    context.user_data["email"], context.user_data["description"], context.user_data["manager"],
                    ",".join(context.user_data.get("categories", [])), datetime.now().isoformat(),
                    "Yes" if context.user_data["public"] else "No"]
            network_sheet.append_row(data)
            await context.bot.send_message(MANAGER_CHAT_ID, f"New Network Reg: {data[1:]}")
            await update.message.reply_text(f"Registered {data[1]} in the network!")
            del context.user_data["register_step"]

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if "cat:" in query.data:
        cat = query.data.split("cat:")[1]
        if cat == "done":
            context.user_data["register_step"] = "public"
            await query.edit_message_text("Share email publicly? (Yes/No):")
        else:
            context.user_data.setdefault("categories", []).append(cat)
            await query.edit_message_text(f"Added {cat}. Select more or click Done:")

# Schedule notifications
def schedule_notifications(app):
    for training in UPCOMING_TRAININGS:
        date = datetime.strptime(training["date"], "%Y-%m-%d")
        notify_date = date - timedelta(days=7)
        if notify_date > datetime.now():
            scheduler.add_job(
                lambda: notify_training(app, training["name"], training["date"]),
                "date", run_date=notify_date
            )

async def notify_training(app, name, date):
    for row in training_sheet.get_all_records():
        chat_id = row["ChatID"]
        await app.bot.send_message(chat_id, f"Reminder: {name} training on {date} is in 7 days! Reply /trainings for details.")

# Set up the bot
def main():
    app = Application.builder().token("7910442120:AAFMUhnwTONoyF1xilwRpjWIRCTmGa0den4").build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("trainings", trainings))
    app.add_handler(CommandHandler("signup", signup))
    app.add_handler(CommandHandler("networking", networking))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CommandHandler("contact", contact))
    app.add_handler(CommandHandler("subscribenews", subscribenews))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply))
    app.add_handler(CallbackQueryHandler(button))
    
    # Schedule notifications
    schedule_notifications(app)
    
    # Run with webhook
    port = int(os.environ.get("PORT", 8443))
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="/",
        webhook_url=f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/"
    )
    print("Bot is running on Render...")

if __name__ == "__main__":
    main()