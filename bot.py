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
creds_json_raw = os.environ.get("GOOGLE_CREDENTIALS", "{}")
creds_json = json.loads(creds_json_raw)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("BenuBotData")
training_sheet = sheet.worksheet("TrainingSignups")
network_sheet = sheet.worksheet("NetworkingRegistrations")

# Scheduler for notifications
scheduler = AsyncIOScheduler()
scheduler.start()

# Manager’s Telegram ID (your ID: 499281665)
MANAGER_CHAT_ID = "499281665"

# Training data
UPCOMING_TRAININGS = [
    {"name": "Biscuit Production Basics", "date": "2025-04-15", "resources": None},
    {"name": "Marketing for Startups", "date": "2025-04-20", "resources": None},
]
PAST_TRAININGS = [
    {"name": "Intro to Fortification", "date": "2025-03-10", "video": "https://youtube.com/example", "resources": "https://drive.google.com/example"},
    {"name": "Biscuit Processing Techniques", "date": "2025-03-20", "video": "https://youtu.be/Q9TCM89oNfU?si=5Aia87X1csYSZ4g6", "resources": "https://drive.google.com/file/d/1HTr62gOcWHEU76-OXDnzJRf11l7nXKPv/view"},
]

# Language-specific messages
MESSAGES = {
    "en": {
        "welcome": "Welcome to Benu’s Startup Support Bot!\nPlease select your language:",
        "options": "Choose an option:",
        "ask": "Ask a question",
        "resources": "Access training resources",
        "trainings": "View trainings",
        "networking": "Join the network",
        "news": "Latest updates",
        "contact": "Reach us",
        "subscribenews": "News updates",
        "ask_prompt": "Please type your question, and I’ll do my best to assist you!",
        "resources_title": "Available Training Resources:",
        "no_resources": "No resources available yet.",
        "trainings_past": "Past Trainings:",
        "trainings_upcoming": "Upcoming Trainings:",
        "signup_prompt": "Please provide your full name:",
        "networking_title": "Network by Category (Biscuit & Agriculture Sector):",
        "register_prompt": "Please provide your company name:",
        "news_title": "Latest Announcements:",
        "contact_info": "Contact Us:\nEmail: benu@example.com\nPhone: +251921756683\nAddress: Addis Ababa, Bole Sub city, Woreda 03, H.N. 4/10/A5/FL8",
        "subscribed": "Subscribed to news updates!",
        "signup_thanks": "Thanks for signing up, {name}!",
        "register_thanks": "Registered {company} in the network!",
        "phone_prompt": "Please provide your phone number:",
        "email_prompt": "Please provide your email:",
        "company_prompt": "Please provide your company name:",
        "description_prompt": "Please provide a description of what your company does:",
        "manager_prompt": "Please provide the manager’s name:",
        "categories_prompt": "Select categories (click Done when finished):",
        "public_prompt": "Share email publicly? (Yes/No):",
        "cat_added": "Added {cat}. Select more or click Done:",
    },
    "am": {
        "welcome": "እንኳን ወደ ቤኑ ስታርትአፕ ድጋፍ ቦት በደህና መጡ!\nእባክዎ ቋንቋዎን ይምረጡ:",
        "options": "አማራጭ ይምረጡ:",
        "ask": "ጥያቄ ይጠይቁ",
        "resources": "ሥልጠና መሣሪያዎችን ይድረሱ",
        "trainings": "ሥልጠናዎችን ይመልከቱ",
        "networking": "ኔትወርክ ይቀላቀሉ",
        "news": "የቅርብ ጊዜ ዜናዎች",
        "contact": "ያግኙን",
        "subscribenews": "የዜና ዝመናዎች",
        "ask_prompt": "እባክዎ ጥያቄዎን ይፃፉ፣ እኔም መልካም መልስ ለመስጠት እሞክራለሁ!",
        "resources_title": "የሚገኙ ሥልጠና መሣሪያዎች:",
        "no_resources": "እስካሁን መሣሪያዎች የሉም።",
        "trainings_past": "ያለፉ ሥልጠናዎች:",
        "trainings_upcoming": "መጪ ሥልጠናዎች:",
        "signup_prompt": "እባክዎ ሙሉ ስምዎን ያስፈልጋል:",
        "networking_title": "በምድብ መልክ ኔትወርክ (ቢስኩት እና ግብርና ዘርፍ):",
        "register_prompt": "እባክዎ የኩባንያዎን ስም ያስፈልጋል:",
        "news_title": "የቅርብ ጊዜ ማስታወቂያዎች:",
        "contact_info": "ያግኙን:\nኢሜል: benu@example.com\nስልክ: +251921756683\nአድራሻ: አዲስ አበባ፣ ቦሌ ክፍለ ከተማ፣ ወረዳ 03፣ ቤት ቁ. 4/10/A5/FL8",
        "subscribed": "ለዜና ዝመናዎች ተመዝግበዋል!",
        "signup_thanks": "ለመመዝገብዎ እናመሰግናለን፣ {name}!",
        "register_thanks": "{company} በኔትወርክ ውስጥ ተመዝግቧል!",
        "phone_prompt": "እባክዎ ስልክ ቁጥርዎን ያስፈልጋል:",
        "email_prompt": "እባክዎ ኢሜልዎን ያስፈልጋል:",
        "company_prompt": "እባክዎ የኩባንያዎን ስም ያስፈልጋል:",
        "description_prompt": "እባክዎ የኩባንያዎ መግለጫ ያስፈልጋል:",
        "manager_prompt": "እባክዎ የሥራ አስኪያጁን ስም ያስፈልጋል:",
        "categories_prompt": "ምድቦችን ይምረጡ (ጨርሰዋል የሚለውን ይጫኑ):",
        "public_prompt": "ኢሜልዎን በይፋ ይጋሩ? (አዎ/አይ):",
        "cat_added": "{cat} ታክሏል። ተጨማሪ ይምረጡ ወይም ጨርሰዋል ይጫኑ:",
    }
}

# Bot functions
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
        [InlineKeyboardButton(messages["trainings"], callback_data="cmd:trainings"),
         InlineKeyboardButton(messages["networking"], callback_data="cmd:networking")],
        [InlineKeyboardButton(messages["news"], callback_data="cmd:news"),
         InlineKeyboardButton(messages["contact"], callback_data="cmd:contact")],
        [InlineKeyboardButton(messages["subscribenews"], callback_data="cmd:subscribenews")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(messages["options"], reply_markup=reply_markup)

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    await update.message.reply_text(MESSAGES[lang]["ask_prompt"])

async def resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    past_resources = "\n".join(
        f"- {t['name']} ({t['date']}): {t['resources'] or MESSAGES[lang]['no_resources']}"
        for t in PAST_TRAININGS if t.get("resources")
    )
    await update.message.reply_text(
        f"{MESSAGES[lang]['resources_title']}\n" + (past_resources or MESSAGES[lang]["no_resources"])
    )

async def trainings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    past_text = f"{MESSAGES[lang]['trainings_past']}\n" + "\n".join(
        f"- {t['name']} ({t['date']}): Video: {t['video'] or 'No video'}, Resources: {t['resources'] or 'No resources'}"
        for t in PAST_TRAININGS
    )
    upcoming_text = f"{MESSAGES[lang]['trainings_upcoming']}\n" + "\n".join(
        f"- {t['name']} ({t['date']}) - Reply /signup to join"
        for t in UPCOMING_TRAININGS
    )
    await update.message.reply_text(f"{past_text}\n\n{upcoming_text}")

async def signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    lang = context.user_data.get("lang", "en")
    context.user_data["signup_step"] = "name"
    await update.message.reply_text(MESSAGES[lang]["signup_prompt"])

async def networking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    network_companies = {
        "Biscuit Production": [
            {"name": "EthioBiscuit Co.", "description": "Produces fortified biscuits", "contact": "+251912345678"},
            {"name": "Benu Biscuits", "description": "Specializes in local biscuit varieties", "contact": "Private"}
        ],
        "Agriculture": [
            {"name": "AgriGrow Ethiopia", "description": "Supplies wheat and grains", "contact": "+251987654321"},
            {"name": "FarmTech Ltd.", "description": "Organic farming solutions", "contact": "Private"}
        ]
    }
    
    network_data = network_sheet.get_all_records()
    for entry in network_data:
        for cat in entry["Categories"].split(","):
            if cat not in network_companies:
                network_companies[cat] = []
            network_companies[cat].append({"name": entry["Company"], "description": entry["Description"],
                                           "contact": entry["Phone"] if entry["PublicEmail"] == "Yes" else "Private"})

    text = f"{MESSAGES[lang]['networking_title']}\n"
    for cat, companies in network_companies.items():
        text += f"\n{cat}:\n" + "\n".join(
            f"- {c['name']} | {c['description']} | Contact: {c['contact']}"
            for c in companies
        )
    text += "\n\nReply /register to join the network!"
    await update.message.reply_text(text)

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    lang = context.user_data.get("lang", "en")
    context.user_data["register_step"] = "company"
    await update.message.reply_text(MESSAGES[lang]["register_prompt"])

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    await update.message.reply_text(
        f"{MESSAGES[lang]['news_title']}\n"
        "1. March 12, 2025: Benu secured ETB 2.9M from SWR Ethiopia.\n"
        "2. April 10, 2025: First training held—29 saleswomen trained! See /trainings.\n"
        "3. May 2025: New production line launches.\n"
        "4. May 15, 2025: Networking Event—register at /networking or /trainings.\n"
        "Use /subscribenews for updates!"
    )

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    await update.message.reply_text(MESSAGES[lang]["contact_info"])

async def subscribenews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    lang = context.user_data.get("lang", "en")
    if training_sheet.find(str(chat_id)) is None:
        training_sheet.append_row([str(chat_id), "", "", "", "", datetime.now().isoformat()])
    await update.message.reply_text(MESSAGES[lang]["subscribed"])

# Handle multi-step replies
async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text
    lang = context.user_data.get("lang", "en")

    # Training signup flow
    if "signup_step" in context.user_data:
        step = context.user_data["signup_step"]
        if step == "name":
            context.user_data["name"] = text
            context.user_data["signup_step"] = "phone"
            await update.message.reply_text(MESSAGES[lang]["phone_prompt"])
        elif step == "phone":
            context.user_data["phone"] = text
            context.user_data["signup_step"] = "email"
            await update.message.reply_text(MESSAGES[lang]["email_prompt"])
        elif step == "email":
            context.user_data["email"] = text
            context.user_data["signup_step"] = "company"
            await update.message.reply_text(MESSAGES[lang]["company_prompt"])
        elif step == "company":
            context.user_data["company"] = text
            data = [str(chat_id), context.user_data["name"], context.user_data["phone"],
                    context.user_data["email"], context.user_data["company"], datetime.now().isoformat()]
            training_sheet.append_row(data)
            await context.bot.send_message(MANAGER_CHAT_ID, f"New Signup: {data[1:]}")
            await update.message.reply_text(MESSAGES[lang]["signup_thanks"].format(name=data[1]))
            del context.user_data["signup_step"]

    # Networking registration flow
    elif "register_step" in context.user_data:
        step = context.user_data["register_step"]
        if step == "company":
            context.user_data["company"] = text
            context.user_data["register_step"] = "phone"
            await update.message.reply_text(MESSAGES[lang]["phone_prompt"])
        elif step == "phone":
            context.user_data["phone"] = text
            context.user_data["register_step"] = "email"
            await update.message.reply_text(MESSAGES[lang]["email_prompt"])
        elif step == "email":
            context.user_data["email"] = text
            context.user_data["register_step"] = "description"
            await update.message.reply_text(MESSAGES[lang]["description_prompt"])
        elif step == "description":
            context.user_data["description"] = text
            context.user_data["register_step"] = "manager"
            await update.message.reply_text(MESSAGES[lang]["manager_prompt"])
        elif step == "manager":
            context.user_data["manager"] = text
            context.user_data["register_step"] = "categories"
            keyboard = [
                [InlineKeyboardButton("Biscuit Production", callback_data="cat:Biscuit Production"),
                 InlineKeyboardButton("Agriculture", callback_data="cat:Agriculture")],
                [InlineKeyboardButton("Packaging", callback_data="cat:Packaging"),
                 InlineKeyboardButton("Marketing", callback_data="cat:Marketing")],
                [InlineKeyboardButton("Done", callback_data="cat:done")]
            ]
            await update.message.reply_text(MESSAGES[lang]["categories_prompt"], reply_markup=InlineKeyboardMarkup(keyboard))
        elif step == "public":
            context.user_data["public"] = text.lower() in ["yes", "y"]
            data = [str(chat_id), context.user_data["company"], context.user_data["phone"],
                    context.user_data["email"], context.user_data["description"], context.user_data["manager"],
                    ",".join(context.user_data.get("categories", [])), datetime.now().isoformat(),
                    "Yes" if context.user_data["public"] else "No"]
            network_sheet.append_row(data)
            await context.bot.send_message(MANAGER_CHAT_ID, f"New Network Reg: {data[1:]}")
            await update.message.reply_text(MESSAGES[lang]["register_thanks"].format(company=data[1]))
            del context.user_data["register_step"]

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "en")

    if "lang:" in query.data:
        lang_choice = query.data.split("lang:")[1]
        await show_options(update, context, lang_choice)
    elif "cmd:" in query.data:
        cmd = query.data.split("cmd:")[1]
        handlers = {
            "ask": ask,
            "resources": resources,
            "trainings": trainings,
            "networking": networking,
            "news": news,
            "contact": contact,
            "subscribenews": subscribenews
        }
        if cmd in handlers:
            await handlers[cmd](update, context)
    elif "cat:" in query.data:
        cat = query.data.split("cat:")[1]
        if cat == "done":
            context.user_data["register_step"] = "public"
            await query.edit_message_text(MESSAGES[lang]["public_prompt"])
        else:
            context.user_data.setdefault("categories", []).append(cat)
            await query.edit_message_text(MESSAGES[lang]["cat_added"].format(cat=cat))

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
    app.add_handler(CommandHandler("signup", signup))
    app.add_handler(CommandHandler("register", register))
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