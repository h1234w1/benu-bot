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

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json_raw = os.environ.get("GOOGLE_CREDENTIALS", "{}")
creds_json = json.loads(creds_json_raw)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("BenuBotData")

# Initialize worksheets
users_sheet = sheet.worksheet("Users") if "Users" in [ws.title for ws in sheet.worksheets()] else sheet.add_worksheet(title="Users", rows=100, cols=10)
training_sheet = sheet.worksheet("TrainingSignups")
network_sheet = sheet.worksheet("NetworkingRegistrations")

# Set up Users sheet headers if new
if not users_sheet.row_values(1):
    users_sheet.update("A1:H1", [["ChatID", "Name", "Phone", "Email", "Company", "Description", "Timestamp", "Status"]])

# Scheduler for notifications
scheduler = AsyncIOScheduler()
scheduler.start()

# Manager’s Telegram ID
MANAGER_CHAT_ID = "499281665"

# Training data
UPCOMING_TRAININGS = [
    {"name": "Biscuit Production Basics", "date": "2025-04-15"},
    {"name": "Marketing for Startups", "date": "2025-04-20"},
]
PAST_TRAININGS = [
    {"name": "Intro to Fortification", "date": "2025-03-10", "video": "https://youtube.com/example", "resources": "https://drive.google.com/example", "description": "Learn fortification basics."},
    {"name": "Biscuit Processing Techniques", "date": "2025-03-20", "video": "https://youtu.be/Q9TCM89oNfU", "resources": "https://drive.google.com/file/d/1HTr62gOcWHEU76-OXDnzJRf11l7nXKPv/view", "description": "Efficient production techniques."},
]

# Language-specific messages
MESSAGES = {
    "en": {
        "welcome": "Welcome to Benu’s Startup Support Bot!\nSelect your language to register:",
        "options": "Choose an option:",
        "ask": "Ask a question",
        "resources": "Access training resources",
        "training_events": "Training Events",
        "networking": "Join the network",
        "news": "Latest updates",
        "contact": "Reach us",
        "subscribenews": "News updates",
        "learn_startup_skills": "Learn Startup Skills",
        "update_profile": "Update Profile",
        "signup_prompt": "Please provide your full name:",
        "phone_prompt": "Please provide your phone number:",
        "email_prompt": "Please provide your email:",
        "company_prompt": "Please provide your company name:",
        "description_prompt": "Please describe what your company does:",
        "signup_thanks": "Thanks for registering, {name}! Awaiting approval.",
        "pending_message": "Your registration is pending approval. Please wait.",
        "denied_message": "Your registration was denied. Contact benu@example.com.",
        "approved_message": "Welcome! Your registration is approved. Use /start.",
        "resources_title": "Available Training Resources:",
        "no_resources": "No resources available yet.",
        "trainings_past": "Past Training Events:",
        "trainings_upcoming": "Upcoming Training Events:",
        "training_signup_success": "Signed up for {training}!",
        "news_title": "Latest Announcements:",
        "subscribed": "Subscribed to news updates!",
        "contact_info": "Contact Us:\nEmail: benu@example.com\nPhone: +251921756683\nAddress: Addis Ababa",
    },
    "am": {
        "welcome": "እንኳን ወደ ቤኑ ስታርትአፕ ድጋፍ ቦት በደህና መጡ!\nለመመዝገብ ቋንቋዎን ይምረጡ:",
        "options": "አማራጭ ይምረጡ:",
        "signup_prompt": "ሙሉ ስምዎን ያስፈልጋል:",
        "phone_prompt": "ስልክ ቁጥርዎን ያስፈልጋል:",
        "email_prompt": "ኢሜልዎን ያስፈልጋል:",
        "company_prompt": "የኩባንያዎን ስም ያስፈልጋል:",
        "description_prompt": "የኩባንያዎ መግለጫ ያስፈልጋል:",
        "signup_thanks": "ለመመዝገብዎ እናመሰግናለን፣ {name}! ማረጋገጫ በመጠባበቅ ላይ።",
        "pending_message": "መመዝገቢያዎ ለማረጋገጫ በመጠባበቅ ላይ ነው።",
        "denied_message": "መመዝገቢያዎ ተከልክሏል። benu@example.com ያግኙ።",
        "approved_message": "እንኳን ደህና መጡ! መመዝገቢያዎ ተቀባይነት አግኝቷል። /start ይጠቀሙ።",
        "resources_title": "የሚገኙ ሥልጠና መሣሪያዎች:",
        "no_resources": "እስካሁን መሣሪያዎች የሉም።",
        "trainings_past": "ያለፉ ሥልጠና ዝግጅቶች:",
        "trainings_upcoming": "መጪ ሥልጠና ዝግጅቶች:",
        "training_signup_success": "{training} ለመማር ተመዝግበዋል!",
        "news_title": "የቅርብ ጊዜ ማስታወቂያዎች:",
        "subscribed": "ለዜና ዝመናዎች ተመዝግበዋል!",
        "contact_info": "ያግኙን:\nኢሜል: benu@example.com\nስልክ: +251921756683\nአድራሻ: አዲስ አበባ",
    }
}

# Helper function to check user status
def get_user_status(chat_id):
    try:
        cell = users_sheet.find(str(chat_id))
        if cell:
            row = users_sheet.row_values(cell.row)
            return row[7] if len(row) > 7 else "Pending"  # Status in column H (index 7)
        return None
    except gspread.exceptions.CellNotFound:
        return None

# Get user info
def get_user_info(chat_id):
    try:
        cell = users_sheet.find(str(chat_id))
        if cell:
            row = users_sheet.row_values(cell.row)
            return {"name": row[1], "phone": row[2], "email": row[3], "company": row[4], "description": row[5]}
        return None
    except gspread.exceptions.CellNotFound:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    status = get_user_status(chat_id)
    lang = context.user_data.get("lang", "en")
    messages = MESSAGES[lang]

    if status == "Approved":
        await show_options(update, context, lang)
    elif status == "Denied":
        await update.message.reply_text(f"🌟 *{messages['denied_message']}* 🌟", parse_mode="Markdown")
    elif status == "Pending":
        await update.message.reply_text(f"🌟 *{messages['pending_message']}* 🌟", parse_mode="Markdown")
    else:
        keyboard = [
            [InlineKeyboardButton("English", callback_data="lang:en"),
             InlineKeyboardButton("አማርኛ", callback_data="lang:am")]
        ]
        await update.message.reply_text(
            f"🌟 *{messages['welcome']}* 🌟",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

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
    await update.callback_query.edit_message_text(
        f"🌟 *{messages['options']}* 🌟",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    lang = context.user_data.get("lang", "en")
    context.user_data["register_step"] = "name"
    keyboard = [[InlineKeyboardButton("Cancel", callback_data="cmd:cancel")]]
    await update.message.reply_text(
        f"🌟 *{MESSAGES[lang]['signup_prompt']}* 🌟",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    sections = [
        f"✨ *{t['name']}* _({t['date']})_\n📹 [Watch]({t['video']}) | 📄 [Read]({t['resources']})\n_{t['description']}_"
        for t in PAST_TRAININGS if t.get("video") or t.get("resources")
    ]
    text = f"🌟 *{messages['resources_title']}* 🌟\n\n" + "\n🌟====🌟\n".join(sections) if sections else messages["no_resources"]
    keyboard = [
        [InlineKeyboardButton("🎥 Videos Only", callback_data="filter:videos"),
         InlineKeyboardButton("📜 Docs Only", callback_data="filter:resources")],
        [InlineKeyboardButton("⬇️ Get All Resources", callback_data="cmd:all_resources"),
         InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
    ]
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)

async def training_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    past_text = f"🌟 *{messages['trainings_past']}* 🌟\n\n" + "\n-----\n".join(f"🌟 *{t['name']}* _({t['date']})_\n_{t['description']}_" for t in PAST_TRAININGS)
    upcoming_text = f"✨ *{messages['trainings_upcoming']}* ✨\n\n" + "\n".join(f"📅 *{t['name']}* _({t['date']})_" for t in UPCOMING_TRAININGS)
    keyboard = [
        [InlineKeyboardButton("📚 Resources", callback_data="cmd:resources"),
         InlineKeyboardButton("✍️ Sign Up", callback_data="cmd:training_signup")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
    ]
    await query.message.reply_text(f"{past_text}\n\n{upcoming_text}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def training_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    keyboard = [
        [InlineKeyboardButton(t["name"], callback_data=f"signup_training:{t['name']}") for t in UPCOMING_TRAININGS[i:i+2]]
        for i in range(0, len(UPCOMING_TRAININGS), 2)
    ]
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")])
    await query.message.reply_text(f"🌟 *Select a training to sign up for:* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    news_items = [
        "🌟 *March 12, 2025*: _Benu secured ETB 2.9M from SWR Ethiopia._",
        "🌟 *April 10, 2025*: _First training held—29 saleswomen trained!_",
    ]
    text = f"🌟 *{messages['news_title']}* 🌟\n\n" + "\n".join(news_items)
    keyboard = [
        [InlineKeyboardButton("🔔 Subscribe", callback_data="cmd:subscribenews")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
    ]
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    text = f"🌟 *{messages['contact_info'].split(':')[0]}* 🌟\n\n✉️ *Email:* benu@example.com\n📞 *Phone:* +251921756683\n🏢 *Address:* Addis Ababa"
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def subscribenews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.callback_query.message.chat_id
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    if training_sheet.find(str(chat_id)) is None:  # Using TrainingSignups for subscriptions too
        user_info = get_user_info(chat_id)
        training_sheet.append_row([str(chat_id), user_info["name"], "Subscribed to News", datetime.now().isoformat()])
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    await query.message.reply_text(f"🌟 *{messages['subscribed']}* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text
    lang = context.user_data.get("lang", "en")
    messages = MESSAGES[lang]
    status = get_user_status(chat_id)

    if status != "Approved" and "register_step" not in context.user_data:
        await update.message.reply_text(f"🌟 *{messages['pending_message' if status == 'Pending' else 'denied_message']}* 🌟", parse_mode="Markdown")
        return

    if "register_step" in context.user_data:
        step = context.user_data["register_step"]
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cmd:cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if step == "name":
            context.user_data["name"] = text
            context.user_data["register_step"] = "phone"
            await update.message.reply_text(f"🌟 *{messages['phone_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "phone":
            context.user_data["phone"] = text
            context.user_data["register_step"] = "email"
            await update.message.reply_text(f"🌟 *{messages['email_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "email":
            context.user_data["email"] = text
            context.user_data["register_step"] = "company"
            await update.message.reply_text(f"🌟 *{messages['company_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "company":
            context.user_data["company"] = text
            context.user_data["register_step"] = "description"
            await update.message.reply_text(f"🌟 *{messages['description_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "description":
            context.user_data["description"] = text
            data = [str(chat_id), context.user_data["name"], context.user_data["phone"],
                    context.user_data["email"], context.user_data["company"], text, datetime.now().isoformat(), "Pending"]
            users_sheet.append_row(data)
            await update.message.reply_text(f"🌟 *{messages['signup_thanks'].format(name=data[1])}* 🌟", parse_mode="Markdown")
            manager_text = (
                f"New Registration Request:\n"
                f"Name: {data[1]}\nPhone: {data[2]}\nEmail: {data[3]}\nCompany: {data[4]}\nDescription: {data[5]}\nChat ID: {data[0]}"
            )
            keyboard = [
                [InlineKeyboardButton("Approve", callback_data=f"approve:{chat_id}"),
                 InlineKeyboardButton("Deny", callback_data=f"deny:{chat_id}")]
            ]
            await context.bot.send_message(MANAGER_CHAT_ID, manager_text, reply_markup=InlineKeyboardMarkup(keyboard))
            del context.user_data["register_step"]

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    lang = context.user_data.get("lang", "en")
    messages = MESSAGES[lang]
    status = get_user_status(chat_id)

    if status != "Approved" and "lang:" not in query.data and "approve:" not in query.data and "deny:" not in query.data:
        await query.edit_message_text(f"🌟 *{messages['pending_message' if status == 'Pending' else 'denied_message']}* 🌟", parse_mode="Markdown")
        return

    if "lang:" in query.data:
        lang_choice = query.data.split("lang:")[1]
        context.user_data["lang"] = lang_choice
        await query.edit_message_text(f"🌟 *Starting registration in {lang_choice}...* 🌟", parse_mode="Markdown")
        await register_user(update, context)
    elif "approve:" in query.data:
        user_chat_id = query.data.split("approve:")[1]
        cell = users_sheet.find(user_chat_id)
        if cell:
            users_sheet.update_cell(cell.row, 8, "Approved")
            await context.bot.send_message(user_chat_id, f"🌟 *{MESSAGES[lang]['approved_message']}* 🌟", parse_mode="Markdown")
            await query.edit_message_text(f"User {user_chat_id} approved!", parse_mode="Markdown")
    elif "deny:" in query.data:
        user_chat_id = query.data.split("deny:")[1]
        cell = users_sheet.find(user_chat_id)
        if cell:
            users_sheet.update_cell(cell.row, 8, "Denied")
            await context.bot.send_message(user_chat_id, f"🌟 *{MESSAGES[lang]['denied_message']}* 🌟", parse_mode="Markdown")
            await query.edit_message_text(f"User {user_chat_id} denied!", parse_mode="Markdown")
    elif "cmd:" in query.data:
        cmd = query.data.split("cmd:")[1]
        handlers = {
            "cancel": lambda u, c: query.edit_message_text(f"🌟 *Registration cancelled.* 🌟", parse_mode="Markdown"),
            "main_menu": lambda u, c: show_options(u, c, lang),
            "resources": resources,
            "training_events": training_events,
            "training_signup": training_signup,
            "news": news,
            "contact": contact,
            "subscribenews": subscribenews,
        }
        if cmd in handlers:
            await handlers[cmd](update, context)
            if cmd == "cancel":
                del context.user_data["register_step"]
    elif "signup_training:" in query.data:
        training_name = query.data.split("signup_training:")[1]
        user_info = get_user_info(chat_id)
        training_sheet.append_row([str(chat_id), user_info["name"], training_name, datetime.now().isoformat()])
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        await query.message.reply_text(f"🌟 *{messages['training_signup_success'].format(training=training_name)}* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    app = Application.builder().token("7910442120:AAFMUhnwTONoyF1xilwRpjWIRCTmGa0den4").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply))
    app.add_handler(CallbackQueryHandler(button))
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