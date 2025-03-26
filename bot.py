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
    users_sheet.update("A1:I1", [["Username", "Name", "Phone", "Email", "Company", "Description", "ChatID", "Timestamp", "Status"]])

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
        "welcome": "Welcome to Benu’s Startup Support Bot!\nTo access our resources and training for startups, please register first. Select your language:\n\nእንኳን ወደ ቤኑ ስታርትአፕ ድጋፍ ቦት በደህና መጡ!\nለመመዝገብ እባክዎ ቋንቋዎን ይምረጡ:",
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
        "username_prompt": "Please enter your Telegram username (e.g., @Beth):",
        "signup_prompt": "Please provide your full name (e.g., John Doe):",
        "phone_prompt": "Please provide your phone number (e.g., +251912345678):",
        "email_prompt": "Please provide your email (e.g., john.doe@example.com):",
        "company_prompt": "Please provide your company name (e.g., Doe Biscuits):",
        "description_prompt": "Please describe what your company does (e.g., We produce fortified biscuits for local markets):",
        "signup_thanks": "Thank you for registering, {name}! Please wait for approval from our team. We’ll notify you soon.",
        "pending_message": "Your registration is pending approval. Please wait for confirmation.",
        "denied_message": "Your registration was denied. Contact benu@example.com for assistance.",
        "approved_message": "Welcome! Your registration is approved. Use /menu to explore resources and training!",
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
        "welcome": "እንኳን ወደ ቤኑ ስታርትአፕ ድጋፍ ቦት በደህና መጡ!\nለስታርትአፕ ሥልጠናዎችና መሣሪያዎች መድረስ መጀመሪያ መመዝገብ ይኖርብዎታል። ቋንቋዎን ይምረጡ:\n\nWelcome to Benu’s Startup Support Bot!\nTo access our resources and training for startups, please register first. Select your language:",
        "options": "አማራጭ ይምረጡ:",
        "username_prompt": "የቴሌግራም ተጠቃሚ ስምዎን ያስገቡ (ለምሳሌ፡ @Jondoe):",
        "signup_prompt": "ሙሉ ስምዎን ያስገቡ (ለምሳሌ፡ ጆን ዶኤ):",
        "phone_prompt": "ስልክ ቁጥርዎን ያስገቡ (ለምሳሌ፡ +2519xxxxxx78):",
        "email_prompt": "ኢሜልዎን ያስገቡ (ለምሳሌ፡ john.doe@example.com):",
        "company_prompt": "የኩባንያዎን ስም ያስገቡ (ለምሳሌ፡ ዶኤ ቢስኩትስ):",
        "description_prompt": "የኩባንያዎ መግለጫ ያስገቡ (ለምሳሌ፡ ለአካባቢው ገበያ የተጠናከረ ቢስኩት እንሰራለን):",
        "signup_thanks": "ለመመዝገብዎ እናመሰግናለን፣ {name}! እባክዎ ከቡድናችን ማረጋገጫ ይጠብቁ። በቅርቡ ይነገርዎታል።",
        "pending_message": "መመዝገቢያዎ ለማረጋገጫ በመጠባበቅ ላይ ነው። እባክዎ ይጠብቁ።",
        "denied_message": "መመዝገቢዤዎ ተከልክሏል። ለድጋፍ benu@example.com ያግኙ።",
        "approved_message": "እንኳን ደህና መጡ! መመዝገቢዤዎ ተቀባይነት አግኝቷል። መሣሪዤዎችንና ሥልጠናዎችን ለመዳሰስ /menu ይጠቀሙ!",
        "resources_title": "የሚገኙ ሥልጠና መሣሪዤዎች:",
        "no_resources": "እስካሁን መሣሪዤዎች የሉም።",
        "trainings_past": "ያለፉ ሥልጠና ዝግጅቶች:",
        "trainings_upcoming": "መጪ ሥልጠና ዝግጅቶች:",
        "training_signup_success": "{training} ለመማር ተመዝግበዋል!",
        "news_title": "የቅርብ ጊዜ ማስታወቂዤዎች:",
        "subscribed": "ለዜና ዝመናዎች ተመዝግበዋል!",
        "contact_info": "ያግኙን:\nኢሜል: benu@example.com\nስልክ: +251921756683\nአድራሻ: አዲስ አበባ",
    }
}

# Helper functions
def get_user_status(username):
    try:
        cell = users_sheet.find(username)
        if cell:
            row = users_sheet.row_values(cell.row)
            return row[8] if len(row) > 8 else "Pending"
        return None
    except gspread.exceptions.CellNotFound:
        return None

def get_user_info(username):
    try:
        cell = users_sheet.find(username)
        if cell:
            row = users_sheet.row_values(cell.row)
            return {"name": row[1], "phone": row[2], "email": row[3], "company": row[4], "description": row[5], "chat_id": row[6]}
        return None
    except gspread.exceptions.CellNotFound:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    username = update.message.from_user.username
    context.user_data["chat_id"] = chat_id
    status = get_user_status(username) if username else None
    lang = context.user_data.get("lang", "en")
    messages = MESSAGES[lang]

    if status == "Approved":
        await show_options_menu(update, context, lang)  # Show menu directly for approved users
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

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    username = update.message.from_user.username
    context.user_data["chat_id"] = chat_id  # Ensure chat_id is stored
    status = get_user_status(username) if username else None
    lang = context.user_data.get("lang", "en")
    messages = MESSAGES[lang]

    if not username:
        await update.message.reply_text("🌟 *Please set a Telegram username in your profile to use this bot.* 🌟", parse_mode="Markdown")
        return

    if status == "Approved":
        await show_options_menu(update, context, lang)
    elif status == "Denied":
        await update.message.reply_text(f"🌟 *{messages['denied_message']}* 🌟", parse_mode="Markdown")
    elif status == "Pending":
        await update.message.reply_text(f"🌟 *{messages['pending_message']}* 🌟", parse_mode="Markdown")
    else:
        await update.message.reply_text("🌟 *Please register first using /start.* 🌟", parse_mode="Markdown")

async def show_options(update: Update, context: ContextTypes.DEFAULT_TYPE, lang):
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

async def show_options_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, lang):
    context.user_data["lang"] = lang  # Persist language choice
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
    await update.message.reply_text(
        f"🌟 *{messages['options']}* 🌟",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    messages = MESSAGES[lang]
    context.user_data["register_step"] = "username"
    await update.callback_query.message.reply_text(
        f"🌟 *{messages['username_prompt']}* 🌟",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cmd:cancel")]])
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
    username = update.callback_query.from_user.username
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    if training_sheet.find(username) is None:
        user_info = get_user_info(username)
        training_sheet.append_row([username, user_info["name"], "Subscribed to News", datetime.now().isoformat()])
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    await query.message.reply_text(f"🌟 *{messages['subscribed']}* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    username = update.message.from_user.username
    text = update.message.text
    lang = context.user_data.get("lang", "en")
    messages = MESSAGES[lang]
    status = get_user_status(username) if username else None

    if not username and "register_step" not in context.user_data:
        await update.message.reply_text("🌟 *Please set a Telegram username in your profile to use this bot.* 🌟", parse_mode="Markdown")
        return

    if status != "Approved" and "register_step" not in context.user_data:
        await update.message.reply_text(f"🌟 *{messages['pending_message' if status == 'Pending' else 'denied_message']}* 🌟", parse_mode="Markdown")
        return

    if "register_step" in context.user_data:
        step = context.user_data["register_step"]
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cmd:cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if step == "username":
            if not text.startswith("@"):
                text = f"@{text}"
            context.user_data["username"] = text
            context.user_data["register_step"] = "name"
            await update.message.reply_text(f"🌟 *{messages['signup_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "name":
            context.user_data["name"] = text
            context.user_data["register_step"] = "phone"
            await update.message.reply_text(f"🌟 *{oordmessages['phone_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
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
            data = [context.user_data["username"], context.user_data["name"], context.user_data["phone"],
                    context.user_data["email"], context.user_data["company"], text, str(chat_id), datetime.now().isoformat(), "Pending"]
            users_sheet.append_row(data)
            await update.message.reply_text(f"🌟 *{messages['signup_thanks'].format(name=data[1])}* 🌟", parse_mode="Markdown")
            manager_text = (
                f"New Registration Request:\n"
                f"Username: {data[0]}\nName: {data[1]}\nPhone: {data[2]}\nEmail: {data[3]}\nCompany: {data[4]}\nDescription: {data[5]}\nChat ID: {data[6]}"
            )
            keyboard = [
                [InlineKeyboardButton("Approve", callback_data=f"approve:{data[0]}"),
                 InlineKeyboardButton("Deny", callback_data=f"deny:{data[0]}")]
            ]
            await context.bot.send_message(MANAGER_CHAT_ID, manager_text, reply_markup=InlineKeyboardMarkup(keyboard))
            del context.user_data["register_step"]

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    username = query.from_user.username
    lang = context.user_data.get("lang", "en")
    messages = MESSAGES[lang]
    status = get_user_status(username) if username else None

    if not username and "lang:" not in query.data and "approve:" not in query.data and "deny:" not in query.data:
        await query.edit_message_text("🌟 *Please set a Telegram username in your profile to use this bot.* 🌟", parse_mode="Markdown")
        return

    if "lang:" in query.data:
        lang_choice = query.data.split("lang:")[1]
        context.user_data["lang"] = lang_choice
        await register_user(update, context)
    elif "approve:" in query.data:
        username = query.data.split("approve:")[1]
        cell = users_sheet.find(username)
        if cell:
            users_sheet.update_cell(cell.row, 9, "Approved")
            user_info = get_user_info(username)
            await context.bot.send_message(user_info["chat_id"], f"🌟 *{messages['approved_message']}* 🌟", parse_mode="Markdown")
            # Immediately show the menu after approval
            await show_options_menu(update, context, lang)
            await query.edit_message_text(f"User {username} approved!", parse_mode="Markdown")
    elif "deny:" in query.data:
        username = query.data.split("deny:")[1]
        cell = users_sheet.find(username)
        if cell:
            users_sheet.update_cell(cell.row, 9, "Denied")
            user_info = get_user_info(username)
            await context.bot.send_message(user_info["chat_id"], f"🌟 *{messages['denied_message']}* 🌟", parse_mode="Markdown")
            await query.edit_message_text(f"User {username} denied!", parse_mode="Markdown")
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
        user_info = get_user_info(username)
        training_sheet.append_row([username, user_info["name"], training_name, datetime.now().isoformat()])
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        await query.message.reply_text(f"🌟 *{messages['training_signup_success'].format(training=training_name)}* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    app = Application.builder().token("7910442120:AAFMUhnwTONoyF1xilwRpjWIRCTmGa0den4").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply))
    app.add_handler(CallbackQueryHandler(button))
    port = int(os.environ.get("PORT", 8443))
    # Use fallback URL if RENDER_EXTERNAL_HOSTNAME isn’t set
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="/",
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'benu-startup-bot.onrender.com')}/"
    )
    print("Bot is running on Render...")

if __name__ == "__main__":
    main()