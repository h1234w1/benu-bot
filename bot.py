import os
import json
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import telegram.error
from flask import Flask, request, Response
import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json_raw = os.environ.get("GOOGLE_CREDENTIALS", "{}")
creds_json = json.loads(creds_json_raw)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("BenuBotData")
training_sheet = sheet.worksheet("TrainingSignups")
network_sheet = sheet.worksheet("NetworkingRegistrations")

# Scheduler for notifications and uptime
scheduler = AsyncIOScheduler()

# Manager’s Telegram ID
MANAGER_CHAT_ID = "499281665"

# Hugging Face API setup
HF_API_KEY = os.environ.get("HF_API_KEY")
HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"

# Training data (unchanged, omitted for brevity)
UPCOMING_TRAININGS = [
    {"name": "Biscuit Production Basics", "date": "2025-04-15", "resources": None},
    {"name": "Marketing for Startups", "date": "2025-04-20", "resources": None},
]
PAST_TRAININGS = [
    {"name": "Intro to Fortification", "date": "2025-03-10", "video": "https://youtube.com/example", "resources": "https://drive.google.com/example"},
    {"name": "Biscuit Processing Techniques", "date": "2025-03-20", "video": "https://youtu.be/Q9TCM89oNfU?si=5Aia87X1csYSZ4g6", "resources": "https://drive.google.com/file/d/1HTr62gOcWHEU76-OXDnzJRf11l7nXKPv/view"},
]
TRAINING_MODULES = [
    {"id": 1, "name": "Biscuit Production Basics", "content": "Learn the essentials...", "prereq": [], "quiz": [...]},
    {"id": 2, "name": "Marketing for Startups", "content": "Understand branding...", "prereq": [1], "quiz": [...]},
    {"id": 3, "name": "Financial Planning", "content": "Basics of budgeting...", "prereq": [1, 2], "quiz": [...]}
]  # Full data omitted for brevity

# Language-specific messages (unchanged, omitted for brevity)
MESSAGES = {
    "en": {"welcome": "Welcome to Benu’s Startup Support Bot!\nPlease select your language:", ...},
    "am": {"welcome": "እንኳን ወደ ቤኑ ስታርትአፕ ድጋፍ ቦት በደህና መጡ!\nእባክዎ ቋንቋዎን ይምረጡ:", ...}
}

# Bot functions (unchanged, keeping only essentials for brevity)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("English", callback_data="lang:en"),
         InlineKeyboardButton("አማርኛ", callback_data="lang:am")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome to Benu’s Startup Support Bot!\nPlease select your language:\n\nእንኳን ወደ ቤኑ ስታርትአፕ ድጋፍ ቦት በደህና መጡ!\nእባክዎ ቋንቋዎን ይምረጡ:", reply_markup=reply_markup)

async def show_options(update: Update, context: ContextTypes.DEFAULT_TYPE, lang):
    context.user_data["lang"] = lang
    messages = MESSAGES[lang]
    keyboard = [
        [InlineKeyboardButton(messages["ask"], callback_data="cmd:ask"),
         InlineKeyboardButton(messages["resources"], callback_data="cmd:resources")],
        [InlineKeyboardButton(messages["training_events"], callback_data="cmd:training_events"),
         InlineKeyboardButton(messages["networking"], callback_data="cmd:networking")],
        [InlineKeyboardButton(messages["news"], callback_data="cmd:news"),
         InlineKeyboardButton(messages["contact"], callback_data="cmd:contact")],
        [InlineKeyboardButton(messages["subscribenews"], callback_data="cmd:subscribenews"),
         InlineKeyboardButton(messages["learn_startup_skills"], callback_data="cmd:learn_startup_skills")],
        [InlineKeyboardButton(messages["update_profile"], callback_data="cmd:update_profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(messages["options"], reply_markup=reply_markup)

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    await query.edit_message_text(MESSAGES[lang]["ask_prompt"] + "\n\nProcessing your request...")
    context.user_data["asking"] = True

async def handle_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("asking"):
        lang = context.user_data.get("lang", "en")
        question = update.message.text
        print(f"Processing question: {question}")
        try:
            headers = {
                "Authorization": f"Bearer {HF_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "inputs": f"You are a helpful AI for startup founders. {question}",
                "parameters": {"max_new_tokens": 100, "temperature": 0.7, "return_full_text": False}
            }
            print(f"Sending to HF: {json.dumps(payload)}")
            response = requests.post(HF_API_URL, json=payload, headers=headers, timeout=10)
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
            response.raise_for_status()
            answer = response.json()[0]["generated_text"].strip()
            await update.message.reply_text(answer)
        except Exception as e:
            print(f"HF API error: {str(e)}")
            await update.message.reply_text(MESSAGES[lang]["ask_error"])
        finally:
            del context.user_data["asking"]

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "en")
    print(f"Button clicked: {query.data}")
    try:
        if "lang:" in query.data:
            lang_choice = query.data.split("lang:")[1]
            await show_options(update, context, lang_choice)
        elif "cmd:" in query.data:
            cmd = query.data.split("cmd:")[1]
            handlers = {"ask": ask}  # Add other handlers as needed
            if cmd in handlers:
                await handlers[cmd](update, context)
    except telegram.error.BadRequest as e:
        print(f"Query error: {str(e)}")
        await query.message.reply_text("Sorry, that button timed out. Please try again!")

# Scheduler functions
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
        await app.bot.send_message(chat_id, f"Reminder: {name} training on {date} is in 7 days! Reply /training_events for details.")

async def keep_alive():
    print("Keeping Render awake...")
    async with httpx.AsyncClient() as client:
        try:
            await client.get("https://benu-startup-bot.onrender.com/")
            print("Ping successful.")
        except Exception as e:
            print(f"Ping failed: {str(e)}")

# Flask app setup
flask_app = Flask(__name__)
application = Application.builder().token("7910442120:AAFMUhnwTONoyF1xilwRpjWIRCTmGa0den4").build()

# Add handlers (simplified for brevity)
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ask))
application.add_handler(CallbackQueryHandler(button))

@flask_app.route('/', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return '', 200

async def main():
    loop = asyncio.get_event_loop()
    await application.initialize()
    schedule_notifications(application)
    scheduler.add_job(keep_alive, "interval", minutes=10)  # Ping every 10 mins
    scheduler.start()
    config = Config()
    config.bind = ["0.0.0.0:10000"]
    try:
        await serve(flask_app, config)
    except asyncio.CancelledError:
        print("Shutting down gracefully...")
    finally:
        scheduler.shutdown()
        await application.stop()
        print("Bot has stopped.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop)))
    finally:
        loop.close()