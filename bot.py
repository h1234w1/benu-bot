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
import urllib.parse

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json_raw = os.environ.get("GOOGLE_CREDENTIALS", "{}")
creds_json = json.loads(creds_json_raw)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("BenuBotData")
training_sheet = sheet.worksheet("TrainingSignups")
network_sheet = sheet.worksheet("NetworkingRegistrations")
# Add Users sheet if it doesn’t exist
users_sheet = sheet.worksheet("Users") if "Users" in [ws.title for ws in sheet.worksheets()] else sheet.add_worksheet(title="Users", rows=100, cols=10)
if not users_sheet.row_values(1):
    users_sheet.update("A1:I1", [["Username", "Name", "Phone", "Email", "Company", "Description", "ChatID", "Timestamp", "Status"]])

# Scheduler for notifications
scheduler = AsyncIOScheduler()
scheduler.start()

# Manager’s Telegram ID
MANAGER_CHAT_ID = "499281665"

# Hugging Face API setup
HF_API_KEY = os.environ.get("HF_API_KEY")
HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"

# Training data
UPCOMING_TRAININGS = [
    {"name": "Biscuit Production Basics", "date": "2025-04-15", "resources": None},
    {"name": "Marketing for Startups", "date": "2025-04-20", "resources": None},
]
PAST_TRAININGS = [
    {
        "name": "Intro to Fortification",
        "date": "2025-03-10",
        "video": "https://youtube.com/example",
        "resources": "https://drive.google.com/example",
        "description": "Learn the basics of fortifying biscuits with nutrients."
    },
    {
        "name": "Biscuit Processing Techniques",
        "date": "2025-03-20",
        "video": "https://youtu.be/Q9TCM89oNfU?si=5Aia87X1csYSZ4g6",
        "resources": "https://drive.google.com/file/d/1HTr62gOcWHEU76-OXDnzJRf11l7nXKPv/view",
        "description": "Techniques for efficient biscuit production."
    },
]
TRAINING_MODULES = [
    {
        "id": 1,
        "name": "Biscuit Production Basics",
        "content": "Learn the essentials of biscuit production: ingredients, equipment, and quality control.",
        "prereq": [],
        "quiz": [
            {"q": "What’s a key ingredient in biscuits?", "options": ["Sugar", "Salt", "Water"], "answer": "Sugar", "explain": "Sugar is key for flavor and texture in biscuits."},
            {"q": "What equipment is vital for mixing?", "options": ["Oven", "Mixer", "Scale"], "answer": "Mixer", "explain": "A mixer ensures uniform dough consistency."},
            {"q": "What ensures product consistency?", "options": ["Taste", "Quality Control", "Packaging"], "answer": "Quality Control", "explain": "Quality control checks standards at every step."}
        ]
    },
    {
        "id": 2,
        "name": "Marketing for Startups",
        "content": "Understand branding, target markets, and low-cost promotion strategies.",
        "prereq": [1],
        "quiz": [
            {"q": "What defines your brand?", "options": ["Logo", "Values", "Price"], "answer": "Values", "explain": "Values shape your brand’s identity and customer trust."},
            {"q": "Who is your target market?", "options": ["Everyone", "Specific Group", "Competitors"], "answer": "Specific Group", "explain": "A specific group helps tailor your marketing effectively."},
            {"q": "What’s a low-cost promotion?", "options": ["TV Ads", "Social Media", "Billboards"], "answer": "Social Media", "explain": "Social media reaches wide audiences cheaply."}
        ]
    },
    {
        "id": 3,
        "name": "Financial Planning",
        "content": "Basics of budgeting, cash flow, and securing startup funds.",
        "prereq": [1, 2],
        "quiz": [
            {"q": "What tracks income vs. expenses?", "options": ["Budget", "Loan", "Sales"], "answer": "Budget", "explain": "A budget plans your financial resources."},
            {"q": "What’s key to cash flow?", "options": ["Profit", "Timing", "Debt"], "answer": "Timing", "explain": "Timing ensures money is available when needed."},
            {"q": "Where can startups get funds?", "options": ["Friends", "Investors", "Savings"], "answer": "Investors", "explain": "Investors provide capital for growth."}
        ]
    }
]

# Language-specific messages
MESSAGES = {
    "en": {
        "welcome": "Welcome to Benu’s Startup Support Bot!\nPlease select your language to register:",
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
        "ask_prompt": "Please type your question, and I’ll get an answer for you!",
        "ask_error": "Sorry, I’m having trouble answering right now. Try again later!",
        "resources_title": "Available Training Resources:",
        "no_resources": "No resources available yet.",
        "trainings_past": "Past Training Events:",
        "trainings_upcoming": "Upcoming Training Events:",
        "signup_prompt": "Please provide your full name:",
        "survey_company_size": "What’s your company size? (e.g., Small, Medium, Large):",
        "networking_title": "Network by Category (Biscuit & Agriculture Sector):",
        "register_prompt": "Please provide your company name:",
        "news_title": "Latest Announcements:",
        "contact_info": "Contact Us:\nEmail: benu@example.com\nPhone: +251921756683\nAddress: Addis Ababa, Bole Sub city, Woreda 03, H.N. 4/10/A5/FL8",
        "subscribed": "Subscribed to news updates!",
        "signup_thanks": "Thanks for signing up, {name}! Your registration is pending approval.",
        "register_thanks": "Registered {company} in the network!",
        "phone_prompt": "Please provide your phone number:",
        "email_prompt": "Please provide your email:",
        "company_prompt": "Please provide your company name:",
        "description_prompt": "Please provide a description of what your company does:",
        "manager_prompt": "Please provide the manager’s name:",
        "categories_prompt": "Select categories (click Done when finished):",
        "public_prompt": "Share email publicly? (Yes/No):",
        "cat_added": "Added {cat}. Select more or click Done:",
        "modules_title": "Startup Skills Modules:",
        "module_study": "Study: {name}\n{content}",
        "quiz_start": "Test your knowledge for {name}:",
        "quiz_question": "Q{num}: {q}",
        "quiz_correct": "Correct!\nExplanation: {explain}",
        "quiz_wrong": "Wrong. The answer was {answer}.\nExplanation: {explain}",
        "quiz_done": "Quiz complete! Score: {score}/{total}. Next module unlocked.",
        "prereq_error": "Please complete the previous module(s) first.",
        "profile_prompt": "Select what to update:",
        "profile_name": "New name:",
        "profile_phone": "New phone:",
        "profile_email": "New email:",
        "profile_company": "New company:",
        "profile_updated": "Profile updated!",
        "survey_satisfaction": "How satisfied are you with the training? (1-5):",
        "survey_thanks": "Thank you for your feedback!",
        "pending_message": "Your registration is pending approval. Please wait for confirmation.",
        "denied_message": "Your registration was denied. Contact benu@example.com for assistance.",
        "approved_message": "Welcome! Your registration is approved. Use /menu to explore resources and training!"
    },
    "am": {
        "welcome": "እንኳን ወደ ቤኑ ስታርትአፕ ድጋፍ ቦት በደህና መጡ!\nለመመዝገብ ቋንቋዎን ይምረጡ:",
        "options": "አማራጭ ይምረጡ:",
        "ask": "ጥያቄ ይጠይቁ",
        "resources": "ሥልጠና መሣሪያዎችን ይድረሱ",
        "training_events": "ሥልጠና ዝግጅቶች",
        "networking": "ኔትወርክ ይቀላቀሉ",
        "news": "የቅርብ ጊዜ ዜናዎች",
        "contact": "ያግኙን",
        "subscribenews": "የዜና ዝመናዎች",
        "learn_startup_skills": "የስታርትአፕ ክህሎቶችን ይማሩ",
        "update_profile": "መገለጫ ያሻሽሉ",
        "ask_prompt": "እባክዎ ጥያቄዎን ይፃፉ፣ መልስ እፈልግልዎታለሁ!",
        "ask_error": "ይቅርታ፣ አሁን መልስ ለመስጠት ችግር አለብኝ። ቆይተው ይሞክሩ!",
        "resources_title": "የሚገኙ ሥልጠና መሣሪያዎች:",
        "no_resources": "እስካሁን መሣሪያዎች የሉም።",
        "trainings_past": "ያለፉ ሥልጠና ዝግጅቶች:",
        "trainings_upcoming": "በቅርቡ የሚጀመሩ ስልጠናዎች:",
        "signup_prompt": "እባክዎ ሙሉ ስምዎን ያስፈልጋል:",
        "survey_company_size": "የኩባንያዎ መጠን ምንድን ነው? (ለምሳሌ፡ ትንሽ፣ መካከለኛ፣ ትልቅ):",
        "networking_title": "በምድብ መልክ ኔትወርክ (ቢስኩት እና ግብርና ዘርፍ):",
        "register_prompt": "እባክዎ የኩባንያዎን ስም ያስፈልጋል:",
        "news_title": "የቅርብ ጊዜ ማስታወቂያዎች:",
        "contact_info": "ያግኙን:\nኢሜል: benu@example.com\nስልክ: +251921756683\nአድራሻ: አዲስ አበባ፣ ቦሌ ክፍለ ከተማ፣ ወረዳ 03፣ ቤት ቁ. 4/10/A5/FL8",
        "subscribed": "ለዜና ዝመናዎች ተመዝግበዋል!",
        "signup_thanks": "ለመመዝገብዎ እናመሰግናለን፣ {name}! መመዝገቢያዎ ለማረጋገጫ በመጠባበቅ ላይ ነው።",
        "register_thanks": "{company} በኔትወርክ ውስጥ ተመዝግቧል!",
        "phone_prompt": "እባክዎ ስልክ ቁጥርዎን ያስፈልጋል:",
        "email_prompt": "እባክዎ ኢሜልዎ ያስፈልጋል:",
        "company_prompt": "እባክዎ የኩባንያዎን ስም ያስፈልጋል:",
        "description_prompt": "እባክዎ የኩባኒዎ መግለጫ ያስፈልጋል:",
        "manager_prompt": "እባክዎ የሥራ አስኪያጁን ስም ያስፈልጋል:",
        "categories_prompt": "ምድቦችን ይምረጡ (ጨርሰዋል የሚለውን ይጫኑ):",
        "public_prompt": "ኢሜልዎን በይፋ ይጋሩ? (አዎ/አይ):",
        "cat_added": "{cat} ታክሏል። ተጨማሪ ይምረጡ ወይም ጨርሰዋል ይጫኑ:",
        "modules_title": "የስታርትአፕ ክህሎት ሞጁሎች:",
        "module_study": "መማር: {name}\n{content}",
        "quiz_start": "{name} ዕውቀትዎን ይፈትኑ:",
        "quiz_question": "ጥ{num}: {q}",
        "quiz_correct": "ትክክል!\nማብራሪያ: {explain}",
        "quiz_wrong": "ተሳስቷል። መልሱ {answer} ነበር።\nማብራሪያ: {explain}",
        "quiz_done": "ፈተና ተጠናቋል! ነጥብ: {score}/{total}። ቀጣዩ ሞጁል ተከፍቷል።",
        "prereq_error": "እባክዎ ቀደም ሲል ያሉትን ሞጁሎች መጀመሪያ ይጨርሱ።",
        "profile_prompt": "ምን ማሻሻል ይፈልጋሉ?:",
        "profile_name": "አዲስ ስም:",
        "profile_phone": "አዲስ ስልክ:",
        "profile_email": "አዲሸ ኢሜል:",
        "profile_company": "አዲስ ኩባንያ:",
        "profile_updated": "መገለጫ ተሻሽሏል!",
        "survey_satisfaction": "ሥልጠናው ምን ያህል እንደሚያረካዎት? (1-5):",
        "survey_thanks": "ለአስተያየትዎ እናመሰግናለን!",
        "pending_message": "መመዝገቢያዎ ለማረጋገጫ በመጠባበቅ ላይ ነው። እባክዎ ይጠብቁ።",
        "denied_message": "መመዝገቢያዎ ተከልክሏል። ለድጋፍ benu@example.com ያግኙ።",
        "approved_message": "እንኳን ደህና መጡ! መመዝገቢያዎ ተቀባይነት አግኝቷል። መሣሪያዎችንና ሥልጠናዎችን ለመዳሰስ /menu ይጠቀሙ!"
    }
}

# Helper functions
def get_user_status(username):
    try:
        cell = users_sheet.find(username)
        return users_sheet.row_values(cell.row)[8] if cell else None
    except gspread.exceptions.CellNotFound:
        return None

# Bot functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    username = update.message.from_user.username
    context.user_data["chat_id"] = chat_id
    status = get_user_status(username) if username else None
    lang = context.user_data.get("lang", "en")
    messages = MESSAGES[lang]

    if not username:
        await update.message.reply_text("🌟 *Please set a Telegram username in your profile to use this bot.* 🌟", parse_mode="Markdown")
    elif status == "Approved":
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
        await update.message.reply_text(f"🌟 *{messages['welcome']}* 🌟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    username = update.message.from_user.username
    context.user_data["chat_id"] = chat_id
    status = get_user_status(username) if username else None
    lang = context.user_data.get("lang", "en")
    messages = MESSAGES[lang]

    if not username:
        await update.message.reply_text("🌟 *Please set a Telegram username in your profile to use this bot.* 🌟", parse_mode="Markdown")
    elif status == "Approved":
        await show_options_menu(update, context, lang)
    elif status == "Denied":
        await update.message.reply_text(f"🌟 *{messages['denied_message']}* 🌟", parse_mode="Markdown")
    elif status == "Pending":
        await update.message.reply_text(f"🌟 *{messages['pending_message']}* 🌟", parse_mode="Markdown")
    else:
        await update.message.reply_text("🌟 *Please register first using /start.* 🌟", parse_mode="Markdown")

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
    await update.callback_query.edit_message_text(f"🌟 *{messages['options']}* 🌟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_options_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, lang):
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
    await update.message.reply_text(f"🌟 *{messages['options']}* 🌟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    await query.edit_message_text(f"🌟 *{MESSAGES[lang]['ask_prompt']}* 🌟\n\nProcessing your request...", parse_mode="Markdown")
    context.user_data["asking"] = True

async def handle_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("asking"):
        lang = context.user_data.get("lang", "en")
        question = update.message.text
        try:
            headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}
            payload = {"inputs": f"You are a helpful AI for startup founders. {question}", "parameters": {"max_new_tokens": 200, "temperature": 0.7, "return_full_text": False}}
            response = requests.post(HF_API_URL, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            answer = response.json()[0]["generated_text"].strip()
            formatted_answer = f"🌟 *Your Answer* 🌟\n➡️ *Question:* {question}\n📝 *Answer:* _{answer}_\n🎉 Powered by BenuBot!"
            keyboard = [[InlineKeyboardButton("Ask Another Question", callback_data="cmd:ask_again"), InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
            await update.message.reply_text(formatted_answer, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            error_msg = f"🌟 *{MESSAGES[lang]['ask_error']}* 🌟"
            keyboard = [[InlineKeyboardButton("Try Again", callback_data="cmd:ask_again"), InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
            await update.message.reply_text(error_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        finally:
            del context.user_data["asking"]

async def resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    sections = [
        f"✨ *{t['name']}* _({t['date']})_\n"
        f"{'📹 [Watch]({t['video']})' if t.get('video') else ''}"
        f"{' | ' if t.get('video') and t.get('resources') else ''}"
        f"{'📄 [Read]({t['resources']})' if t.get('resources') else ''}"
        f"\n_{t['description']}_"
        for t in PAST_TRAININGS if t.get("video") or t.get("resources")
    ]
    text = f"🌟 *{messages['resources_title']}* 🌟\n\n" + "\n🌟====🌟\n".join(sections) if sections else messages["no_resources"]
    keyboard = [
        [InlineKeyboardButton("🎥 Videos Only", callback_data="filter:videos"), InlineKeyboardButton("📜 Docs Only", callback_data="filter:resources")],
        [InlineKeyboardButton("⬇️ Get All Resources", callback_data="cmd:all_resources"), InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
    ]
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)

async def training_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    past_text = f"🌟 *{messages['trainings_past']}* 🌟\n\n" + "\n-----\n".join(f"🌟 *{t['name']}* _({t['date']})_\n_{t['description']}_" for t in PAST_TRAININGS)
    upcoming_text = f"✨ *{messages['trainings_upcoming']}* ✨\n\n" + "\n".join(f"📅 *{t['name']}* _({t['date']})_" for t in UPCOMING_TRAININGS)
    keyboard = [
        [InlineKeyboardButton("📚 Resources", callback_data="cmd:resources"), InlineKeyboardButton("✍️ Sign Up", callback_data="cmd:signup")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
    ]
    await query.message.reply_text(f"{past_text}\n\n{upcoming_text}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    context.user_data["signup_step"] = "name"
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    await update.message.reply_text(f"🌟 *{MESSAGES[lang]['signup_prompt']}* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def networking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    network_companies = {
        "Biscuit Production": [{"name": "EthioBiscuit Co.", "description": "Produces fortified biscuits", "contact": "+251912345678"}, {"name": "Benu Biscuits", "description": "Specializes in local biscuit varieties", "contact": "Private"}],
        "Agriculture": [{"name": "AgriGrow Ethiopia", "description": "Supplies wheat and grains", "contact": "+251987654321"}, {"name": "FarmTech Ltd.", "description": "Organic farming solutions", "contact": "Private"}]
    }
    network_data = network_sheet.get_all_records()
    for entry in network_data:
        for cat in entry["Categories"].split(","):
            if cat not in network_companies:
                network_companies[cat] = []
            network_companies[cat].append({"name": entry["Company"], "description": entry["Description"], "contact": entry["Phone"] if entry["PublicEmail"] == "Yes" else "Private"})
    sections = [f"🌟 *{cat}* 🌟\n" + "\n".join(f"🏢 *{c['name']}*\n_{c['description']}_\n📞 Contact: {c['contact']}" for c in companies) for cat, companies in network_companies.items()]
    text = f"🌟 *{messages['networking_title']}* 🌟\n\n" + "\n🌟----🌟\n".join(sections)
    keyboard = [[InlineKeyboardButton("📝 Register", callback_data="cmd:register")], [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    context.user_data["register_step"] = "company"
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    await update.message.reply_text(f"🌟 *{MESSAGES[lang]['register_prompt']}* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    news_items = [
        "🌟 *March 12, 2025*: _Benu secured ETB 2.9M from SWR Ethiopia._",
        "🌟 *April 10, 2025*: _First training held—29 saleswomen trained! See /training_events._",
        "🌟 *May 2025*: _New production line launches._",
        "🌟 *May 15, 2025*: _Networking Event—register at /networking or /training_events._"
    ]
    text = f"🌟 *{messages['news_title']}* 🌟\n\n" + "\n".join(news_items)
    keyboard = [[InlineKeyboardButton("🔔 Subscribe", callback_data="cmd:subscribenews")], [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    text = f"🌟 *{messages['contact_info'].split(':')[0]}* 🌟\n\n✉️ *Email:* benu@example.com\n📞 *Phone:* +251921756683\n🏢 *Address:* Addis Ababa, Bole Sub city, Woreda 03, H.N. 4/10/A5/FL8"
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def subscribenews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.callback_query.message.chat_id
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    if training_sheet.find(str(chat_id)) is None:
        training_sheet.append_row([str(chat_id), "", "", "", "", datetime.now().isoformat()])
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    await query.message.reply_text(f"🌟 *{MESSAGES[lang]['subscribed']}* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def learn_startup_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    keyboard = [[InlineKeyboardButton(f"📚 {m['name']}", callback_data=f"module:{m['id']}")] for m in TRAINING_MODULES]
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")])
    await query.message.reply_text(f"🌟 *{messages['modules_title']}* 🌟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def update_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    keyboard = [
        [InlineKeyboardButton("Name", callback_data="profile:name"), InlineKeyboardButton("Phone", callback_data="profile:phone")],
        [InlineKeyboardButton("Email", callback_data="profile:email"), InlineKeyboardButton("Company", callback_data="profile:company")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
    ]
    await query.message.reply_text(f"🌟 *{messages['profile_prompt']}* 🌟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text
    lang = context.user_data.get("lang", "en")
    username = update.message.from_user.username
    messages = MESSAGES[lang]

    if "asking" in context.user_data:
        await handle_ask(update, context)
    elif "signup_step" in context.user_data:
        step = context.user_data["signup_step"]
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if step == "name":
            context.user_data["name"] = text
            context.user_data["signup_step"] = "phone"
            await update.message.reply_text(f"🌟 *{messages['phone_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "phone":
            context.user_data["phone"] = text
            context.user_data["signup_step"] = "email"
            await update.message.reply_text(f"🌟 *{messages['email_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "email":
            context.user_data["email"] = text
            context.user_data["signup_step"] = "company"
            await update.message.reply_text(f"🌟 *{messages['company_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "company":
            context.user_data["company"] = text
            user_data = context.user_data
            users_sheet.append_row([username, user_data["name"], user_data["phone"], user_data["email"], user_data["company"], "", str(chat_id), datetime.now().isoformat(), "Pending"])
            await update.message.reply_text(f"🌟 *{messages['signup_thanks'].format(name=user_data['name'])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            await context.bot.send_message(MANAGER_CHAT_ID, f"New Signup:\nUsername: {username}\nName: {user_data['name']}\nPhone: {user_data['phone']}\nEmail: {user_data['email']}\nCompany: {user_data['company']}", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Approve", callback_data=f"approve:{username}"), InlineKeyboardButton("Deny", callback_data=f"deny:{username}")]
            ]))
            del context.user_data["signup_step"]
    elif "register_step" in context.user_data:
        step = context.user_data["register_step"]
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if step == "company":
            context.user_data["company"] = text
            context.user_data["register_step"] = "phone"
            await update.message.reply_text(f"🌟 *{messages['phone_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "phone":
            context.user_data["phone"] = text
            context.user_data["register_step"] = "email"
            await update.message.reply_text(f"🌟 *{messages['email_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "email":
            context.user_data["email"] = text
            context.user_data["register_step"] = "description"
            await update.message.reply_text(f"🌟 *{messages['description_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "description":
            context.user_data["description"] = text
            context.user_data["register_step"] = "manager"
            await update.message.reply_text(f"🌟 *{messages['manager_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "manager":
            context.user_data["manager"] = text
            context.user_data["register_step"] = "categories"
            keyboard = [
                [InlineKeyboardButton("Biscuit Production", callback_data="cat:Biscuit Production"), InlineKeyboardButton("Agriculture", callback_data="cat:Agriculture")],
                [InlineKeyboardButton("Packaging", callback_data="cat:Packaging"), InlineKeyboardButton("Marketing", callback_data="cat:Marketing")],
                [InlineKeyboardButton("Done", callback_data="cat:done")],
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
            ]
            await update.message.reply_text(f"🌟 *{messages['categories_prompt']}* 🌟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        elif step == "public":
            context.user_data["public"] = text.lower() in ["yes", "y"]
            data = [str(chat_id), context.user_data["company"], context.user_data["phone"], context.user_data["email"], context.user_data["description"], context.user_data["manager"], ",".join(context.user_data.get("categories", [])), datetime.now().isoformat(), "Yes" if context.user_data["public"] else "No"]
            network_sheet.append_row(data)
            await context.bot.send_message(MANAGER_CHAT_ID, f"New Network Reg: {data[1:]}")
            await update.message.reply_text(f"🌟 *{messages['register_thanks'].format(company=data[1])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            del context.user_data["register_step"]
    elif "quiz_step" in context.user_data:
        step = context.user_data["quiz_step"]
        module_id = context.user_data["quiz_module"]
        module = next(m for m in TRAINING_MODULES if m["id"] == module_id)
        question = module["quiz"][step - 1]
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if text.lower() == question["answer"].lower():
            await update.message.reply_text(f"🌟 *{messages['quiz_correct'].format(explain=question['explain'])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            context.user_data["quiz_score"] = context.user_data.get("quiz_score", 0) + 1
        else:
            await update.message.reply_text(f"🌟 *{messages['quiz_wrong'].format(answer=question['answer'], explain=question['explain'])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        if step < len(module["quiz"]):
            context.user_data["quiz_step"] += 1
            next_q = module["quiz"][step]
            keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz:{opt}")] for opt in next_q["options"]]
            keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")])
            await update.message.reply_text(f"🌟 *{messages['quiz_question'].format(num=step + 1, q=next_q['q'])}* 🌟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            score = context.user_data.get("quiz_score", 0)
            context.user_data["completed_modules"] = context.user_data.get("completed_modules", []) + [module_id]
            await update.message.reply_text(f"🌟 *{messages['quiz_done'].format(score=score, total=len(module['quiz']))}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            del context.user_data["quiz_step"]
            del context.user_data["quiz_score"]
    elif "profile_step" in context.user_data:
        step = context.user_data["profile_step"]
        cell = users_sheet.find(username)
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if cell:
            row = cell.row
            col = {"name": 2, "phone": 3, "email": 4, "company": 5}[step]
            users_sheet.update_cell(row, col, text)
            await update.message.reply_text(f"🌟 *{messages['profile_updated']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            del context.user_data["profile_step"]

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "en")
    messages = MESSAGES[lang]
    username = query.from_user.username

    if query.data.startswith("lang:"):
        lang_choice = query.data.split("lang:")[1]
        context.user_data["lang"] = lang_choice
        context.user_data["signup_step"] = "name"
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cmd:main_menu")]]
        await query.message.reply_text(f"🌟 *{MESSAGES[lang_choice]['signup_prompt']}* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data == "cmd:ask":
        await ask(update, context)
    elif query.data == "cmd:ask_again":
        await ask(update, context)
    elif query.data == "cmd:resources":
        await resources(update, context)
    elif query.data == "cmd:training_events":
        await training_events(update, context)
    elif query.data == "cmd:signup":
        await signup(update, context)
    elif query.data == "cmd:networking":
        await networking(update, context)
    elif query.data == "cmd:register":
        await register(update, context)
    elif query.data == "cmd:news":
        await news(update, context)
    elif query.data == "cmd:contact":
        await contact(update, context)
    elif query.data == "cmd:subscribenews":
        await subscribenews(update, context)
    elif query.data == "cmd:learn_startup_skills":
        await learn_startup_skills(update, context)
    elif query.data == "cmd:update_profile":
        await update_profile(update, context)
    elif query.data == "cmd:main_menu":
        await show_options(update, context, lang)
    elif query.data.startswith("approve:"):
        username_to_approve = query.data.split("approve:")[1]
        cell = users_sheet.find(username_to_approve)
        users_sheet.update_cell(cell.row, 9, "Approved")
        chat_id = users_sheet.cell(cell.row, 7).value
        await context.bot.send_message(chat_id=chat_id, text=f"🌟 *{messages['approved_message']}* 🌟", parse_mode="Markdown")
        await query.edit_message_text(f"Approved {username_to_approve}")
    elif query.data.startswith("deny:"):
        username_to_deny = query.data.split("deny:")[1]
        cell = users_sheet.find(username_to_deny)
        users_sheet.update_cell(cell.row, 9, "Denied")
        chat_id = users_sheet.cell(cell.row, 7).value
        await context.bot.send_message(chat_id=chat_id, text=f"🌟 *{messages['denied_message']}* 🌟", parse_mode="Markdown")
        await query.edit_message_text(f"Denied {username_to_deny}")
    elif "filter:" in query.data:
        filter_type = query.data.split("filter:")[1]
        filtered_trainings = [t for t in PAST_TRAININGS if t.get("video")] if filter_type == "videos" else [t for t in PAST_TRAININGS if t.get("resources")]
        sections = [
            f"✨ *{t['name']}* _({t['date']})_\n"
            f"{'📹 [Watch]({t['video']})' if t.get('video') else ''}"
            f"{' | ' if t.get('video') and t.get('resources') else ''}"
            f"{'📄 [Read]({t['resources']})' if t.get('resources') else ''}"
            f"\n_{t['description']}_"
            for t in filtered_trainings
        ]
        text = f"🌟 *{messages['resources_title']}* 🌟\n\n" + "\n🌟====🌟\n".join(sections)
        keyboard = [
            [InlineKeyboardButton("🎥 Videos Only", callback_data="filter:videos"), InlineKeyboardButton("📜 Docs Only", callback_data="filter:resources")],
            [InlineKeyboardButton("⬇️ Get All Resources", callback_data="cmd:all_resources"), InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)
    elif "module:" in query.data:
        module_id = int(query.data.split("module:")[1])
        module = next(m for m in TRAINING_MODULES if m["id"] == module_id)
        completed = context.user_data.get("completed_modules", [])
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if all(prereq in completed for prereq in module["prereq"]):
            await query.message.reply_text(f"🌟 *{messages['module_study'].format(name=module['name'], content=module['content'])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz:{opt}")] for opt in module["quiz"][0]["options"]]
            keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")])
            await query.message.reply_text(f"🌟 *{messages['quiz_start'].format(name=module['name'])}* 🌟", parse_mode="Markdown")
            await query.message.reply_text(f"🌟 *{messages['quiz_question'].format(num=1, q=module['quiz'][0]['q'])}* 🌟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            context.user_data["quiz_step"] = 1
            context.user_data["quiz_module"] = module_id
        else:
            await query.message.reply_text(f"🌟 *{messages['prereq_error']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
    elif "quiz:" in query.data:
        answer = query.data.split("quiz:")[1]
        step = context.user_data["quiz_step"]
        module_id = context.user_data["quiz_module"]
        module = next(m for m in TRAINING_MODULES if m["id"] == module_id)
        question = module["quiz"][step - 1]
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if answer == question["answer"]:
            await query.message.reply_text(f"🌟 *{messages['quiz_correct'].format(explain=question['explain'])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            context.user_data["quiz_score"] = context.user_data.get("quiz_score", 0) + 1
        else:
            await query.message.reply_text(f"🌟 *{messages['quiz_wrong'].format(answer=question['answer'], explain=question['explain'])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        if step < len(module["quiz"]):
            context.user_data["quiz_step"] += 1
            next_q = module["quiz"][step]
            keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz:{opt}")] for opt in next_q["options"]]
            keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")])
            await query.message.reply_text(f"🌟 *{messages['quiz_question'].format(num=step + 1, q=next_q['q'])}* 🌟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            score = context.user_data.get("quiz_score", 0)
            context.user_data["completed_modules"] = context.user_data.get("completed_modules", []) + [module_id]
            await query.message.reply_text(f"🌟 *{messages['quiz_done'].format(score=score, total=len(module['quiz']))}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            del context.user_data["quiz_step"]
            del context.user_data["quiz_score"]
    elif "profile:" in query.data:
        field = query.data.split("profile:")[1]
        context.user_data["profile_step"] = field
        await query.message.reply_text(f"🌟 *{messages[f'profile_{field}']}* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]))
    elif "cat:" in query.data:
        cat = query.data.split("cat:")[1]
        if cat == "done":
            context.user_data["register_step"] = "public"
            keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
            await query.edit_message_text(f"🌟 *{messages['public_prompt']}* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            context.user_data.setdefault("categories", []).append(cat)
            await query.edit_message_text(f"🌟 *{messages['cat_added'].format(cat=cat)}* 🌟", parse_mode="Markdown")

async def all_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    links = [f"📹 *{t['name']}* Video: {t['video']}" if t.get("video") else f"📄 *{t['name']}* Resource: {t['resources']}" for t in PAST_TRAININGS if t.get("video") or t.get("resources")]
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    await query.message.reply_text(f"🌟 *All Resources* 🌟\n\n" + "\n".join(links), parse_mode="Markdown", disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(keyboard))

def schedule_notifications(app):
    for training in UPCOMING_TRAININGS:
        date = datetime.strptime(training["date"], "%Y-%m-%d")
        notify_date = date - timedelta(days=7)
        if notify_date > datetime.now():
            scheduler.add_job(lambda: notify_training(app, training["name"], training["date"]), "date", run_date=notify_date)

async def notify_training(app, name, date):
    for row in training_sheet.get_all_records():
        chat_id = row["ChatID"]
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        await app.bot.send_message(chat_id, f"🌟 Reminder: *{name}* training on _{date}_ is in 7 days! Reply /training_events for details.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    app = Application.builder().token(os.environ.get("TELEGRAM_TOKEN", "7910442120:AAFMUhnwTONoyF1xilwRpjWIRCTmGa0den4")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("signup", signup))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply))
    app.add_handler(CallbackQueryHandler(button))
    schedule_notifications(app)
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