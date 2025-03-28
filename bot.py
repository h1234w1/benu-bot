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

# Add after line 10
def init_bot_data(context):
    if "pending_registrations" not in context.bot_data:
        context.bot_data["pending_registrations"] = {}

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json_raw = os.environ.get("GOOGLE_CREDENTIALS", "{}")
creds_json = json.loads(creds_json_raw)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("BenuBotData")
training_sheet = sheet.worksheet("TrainingSignups")
network_sheet = sheet.worksheet("NetworkingRegistrations")
users_sheet = sheet.worksheet("Users")

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
        "welcome": "Welcome to Benu’s Startup Support Bot!\nPlease select your language:",
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
        "survey_thanks": "Thank you for your feedback!"
    },
    "am": {
        "welcome": "እንኳን ወደ ቤኑ ስታርትአፕ ድጋፍ ቦት በደህና መጡ!\nእባክዎ ቋንቋዎን ይምረጡ:",
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
        "resources_title": "የሚገኙ ሥልጠና መሣሪዪዎች:",
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
        "signup_thanks": "ለመመዝገብዎ እናመሰግናለን፣ {name}!",
        "register_thanks": "{company} በኔትወርክ ውስጥ ተመዝግቧል!",
        "phone_prompt": "እባክዎ ስልክ ቁጥርዎን ያስፈልጋል:",
        "email_prompt": "እባክዎ ኢሜልዎን ያስፈልጋል:",
        "company_prompt": "እባክዎ የኩባንያዎን ስም ያስፈልጋል:",
        "description_prompt": "እባክዎ የኩባኔተዎ መግለጫ ያስፈልጋል:",
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
        "profile_email": "አዲስ ኢሜል:",
        "profile_company": "አዲስ ኩባንያ:",
        "profile_updated": "መገለጫ ተሻሽሏል!",
        "survey_satisfaction": "ሥልጠናው ምን ያህል እንደሚያረካዎት? (1-5):",
        "survey_thanks": "ለአስተያየትዎ እናመሰግናለን!"
    }
}

# Bot functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("English", callback_data="lang:en"),
         InlineKeyboardButton("አማርኛ", callback_data="lang:am")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🌟 *Welcome to Benu’s Startup Support Bot!* 🌟\nPlease select your language to begin registration:\n\n"
        "እንኳን ወደ ቤኑ ስታርትአፕ ድጋፍ ቦት በደህና መጡ!\nለመመዝገብ ቋንቋዎን ይምረጡ:",
        reply_markup=reply_markup,
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
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        f"🌟 *{messages['options']}* 🌟", 
        reply_markup=reply_markup, 
        parse_mode="Markdown"
    )

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    await query.edit_message_text(
        f"🌟 *{MESSAGES[lang]['ask_prompt']}* 🌟\n\nProcessing your request...",
        parse_mode="Markdown"
    )
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
                "parameters": {
                    "max_new_tokens": 200,
                    "temperature": 0.7,
                    "return_full_text": False
                }
            }
            print(f"Sending to HF: {json.dumps(payload)}")
            response = requests.post(HF_API_URL, json=payload, headers=headers, timeout=10)
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
            response.raise_for_status()
            answer = response.json()[0]["generated_text"].strip()

            formatted_answer = (
                f"🌟 *Your Answer* 🌟\n"
                f"➡️ *Question:* {question}\n"
                f"📝 *Answer:* _{answer}_\n"
                f"🎉 Powered by BenuBot!"
            )
            keyboard = [
                [InlineKeyboardButton("Ask Another Question", callback_data="cmd:ask_again"),
                 InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(formatted_answer, parse_mode="Markdown", reply_markup=reply_markup)
        except Exception as e:
            print(f"HF API error: {str(e)}")
            error_msg = (
                f"⚠️ *Oops!* ⚠️\n"
                f"Sorry, I couldn’t fetch an answer right now.\n"
                f"Try again later!"
            )
            keyboard = [
                [InlineKeyboardButton("Try Again", callback_data="cmd:ask_again"),
                 InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(error_msg, parse_mode="Markdown", reply_markup=reply_markup)
        finally:
            del context.user_data["asking"]

async def resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]

    sections = []
    for training in PAST_TRAININGS:
        links = []
        if training.get("video"):
            links.append(f"📹 [Watch]({training['video']})")
        if training.get("resources"):
            links.append(f"📄 [Read]({training['resources']})")
        section = (
            f"✨ *{training['name']}* _({training['date']})_\n"
            f"{' | '.join(links)}\n"
            f"_{training['description']}_"
        )
        sections.append(section)

    if sections:
        formatted_text = (
            f"🌟 *{messages['resources_title']}* 🌟\n\n" +
            "\n🌟====🌟\n".join(sections)
        )
    else:
        formatted_text = f"🌟 *{messages['resources_title']}* 🌟\n{messages['no_resources']}"

    keyboard = [
        [
            InlineKeyboardButton("🎥 Videos Only", callback_data="filter:videos"),
            InlineKeyboardButton("📜 Docs Only", callback_data="filter:resources")
        ],
        [
            InlineKeyboardButton("⬇️ Get All Resources", callback_data="cmd:all_resources"),
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(formatted_text, parse_mode="Markdown", reply_markup=reply_markup, disable_web_page_preview=True)

async def training_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]

    past_sections = [
        f"🌟 *{t['name']}* _({t['date']})_\n_{t['description']}_"
        for t in PAST_TRAININGS
    ]
    past_text = (
        f"🌟 *{messages['trainings_past']}* 🌟\n\n" +
        "\n-----\n".join(past_sections)
    )

    upcoming_text = (
        f"✨ *{messages['trainings_upcoming']}* ✨\n\n" +
        "\n".join(f"📅 *{t['name']}* _({t['date']})_" for t in UPCOMING_TRAININGS)
    )

    keyboard = [
        [
            InlineKeyboardButton("📚 Resources", callback_data="cmd:resources"),
            InlineKeyboardButton("✍️ Sign Up", callback_data="cmd:signup")
        ],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        f"{past_text}\n\n{upcoming_text}",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
    lang = context.user_data.get("lang", "en")
    context.user_data["signup_step"] = "username"
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await (update.message.reply_text if update.message else update.callback_query.message.reply_text)(
        f"🌟 *Please provide your username for training signup:* 🌟",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def networking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    
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

    sections = []
    for cat, companies in network_companies.items():
        cat_section = (
            f"🌟 *{cat}* 🌟\n" +
            "\n".join(
                f"🏢 *{c['name']}*\n_{c['description']}_\n📞 Contact: {c['contact']}"
                for c in companies
            )
        )
        sections.append(cat_section)

    text = (
        f"🌟 *{messages['networking_title']}* 🌟\n\n" +
        "\n🌟----🌟\n".join(sections)
    )
    
    keyboard = [
        [InlineKeyboardButton("📝 Register", callback_data="cmd:register")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
    lang = context.user_data.get("lang", "en")
    context.user_data["register_step"] = "company"
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await (update.message.reply_text if update.message else update.callback_query.message.reply_text)(
        f"🌟 *{MESSAGES[lang]['register_prompt']}* 🌟", 
        parse_mode="Markdown", 
        reply_markup=reply_markup
    )

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
    
    text = (
        f"🌟 *{messages['news_title']}* 🌟\n\n" +
        "\n".join(news_items)
    )
    
    keyboard = [
        [InlineKeyboardButton("🔔 Subscribe", callback_data="cmd:subscribenews")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    
    text = (
        f"🌟 *{messages['contact_info'].split(':')[0]}* 🌟\n\n"
        f"✉️ *Email:* benu@example.com\n"
        f"📞 *Phone:* +251921756683\n"
        f"🏢 *Address:* Addis Ababa, Bole Sub city, Woreda 03, H.N. 4/10/A5/FL8"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def subscribenews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.callback_query.message.chat_id
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    if training_sheet.find(str(chat_id)) is None:
        training_sheet.append_row([str(chat_id), "", "", "", "", datetime.now().isoformat()])
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        f"🌟 *{MESSAGES[lang]['subscribed']}* 🌟", 
        parse_mode="Markdown", 
        reply_markup=reply_markup
    )

async def learn_startup_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    keyboard = [
        [InlineKeyboardButton(f"📚 {m['name']}", callback_data=f"module:{m['id']}")]
        for m in TRAINING_MODULES
    ]
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")])
    await query.message.reply_text(
        f"🌟 *{messages['modules_title']}* 🌟", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="Markdown"
    )

async def update_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]
    keyboard = [
        [InlineKeyboardButton("Name", callback_data="profile:name"),
         InlineKeyboardButton("Phone", callback_data="profile:phone")],
        [InlineKeyboardButton("Email", callback_data="profile:email"),
         InlineKeyboardButton("Company", callback_data="profile:company")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
    ]
    await query.message.reply_text(
        f"🌟 *{messages['profile_prompt']}* 🌟", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="Markdown"
    )

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text
    lang = context.user_data.get("lang", "en")

    if "asking" in context.user_data:
        await handle_ask(update, context)
    elif "signup_step" in context.user_data:
        step = context.user_data["signup_step"]
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if step == "username":
            context.user_data["username"] = text
            context.user_data["signup_step"] = "name"
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['signup_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "name":
            context.user_data["name"] = text
            context.user_data["signup_step"] = "phone"
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['phone_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "phone":
            context.user_data["phone"] = text
            context.user_data["signup_step"] = "action"
            keyboard = [
                [InlineKeyboardButton(t["name"], callback_data=f"train:{t['name']}") for t in UPCOMING_TRAININGS],
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
            ]
            await update.message.reply_text(f"🌟 *Select a training:* 🌟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        elif step == "action":
            context.user_data["action"] = text
            data = [context.user_data["username"], context.user_data["name"], context.user_data["phone"],
                    text, datetime.now().isoformat()]
            training_sheet.append_row(data)
            await context.bot.send_message(MANAGER_CHAT_ID, f"New Training Signup: {data}")
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['signup_thanks'].format(name=data[1])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            del context.user_data["signup_step"]
    elif "start_register_step" in context.user_data:
        step = context.user_data["start_register_step"]
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if step == "username":
            context.user_data["username"] = text
            context.user_data["start_register_step"] = "name"
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['signup_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "name":
            context.user_data["name"] = text
            context.user_data["start_register_step"] = "phone"
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['phone_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "phone":
            context.user_data["phone"] = text
            context.user_data["start_register_step"] = "email"
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['email_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "email":
            context.user_data["email"] = text
            context.user_data["start_register_step"] = "company"
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['company_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "company":
            context.user_data["company"] = text
            context.user_data["start_register_step"] = "description"
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['description_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "description":
            context.user_data["description"] = text
            reg_data = {
                "chat_id": str(chat_id),
                "username": context.user_data["username"],
                "name": context.user_data["name"],
                "phone": context.user_data["phone"],
                "email": context.user_data["email"],
                "company": context.user_data["company"],
                "description": context.user_data["description"],
                "timestamp": datetime.now().isoformat(),
                "status": "Pending"
            }
            reg_id = f"{chat_id}_{reg_data['timestamp']}"
            context.bot_data["pending_registrations"][reg_id] = reg_data
            
            # Notify manager
            manager_text = (
                f"New User Registration Pending Approval:\n"
                f"Username: {reg_data['username']}\n"
                f"Name: {reg_data['name']}\n"
                f"Phone: {reg_data['phone']}\n"
                f"Email: {reg_data['email']}\n"
                f"Company: {reg_data['company']}\n"
                f"Description: {reg_data['description']}"
            )
            keyboard = [
                [InlineKeyboardButton("✅ Approve", callback_data=f"approve:{reg_id}"),
                 InlineKeyboardButton("❌ Reject", callback_data=f"reject:{reg_id}")]
            ]
            await context.bot.send_message(MANAGER_CHAT_ID, manager_text, reply_markup=InlineKeyboardMarkup(keyboard))
            
            # Notify user
            await update.message.reply_text(f"🌟 *Registration submitted for approval!* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            del context.user_data["start_register_step"]        
        elif "register_step" in context.user_data:
            step = context.user_data["register_step"]
            keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            if step == "company":
                context.user_data["company"] = text
                context.user_data["register_step"] = "phone"
                await update.message.reply_text(f"🌟 *{MESSAGES[lang]['phone_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            elif step == "phone":
                context.user_data["phone"] = text
                context.user_data["register_step"] = "email"
                await update.message.reply_text(f"🌟 *{MESSAGES[lang]['email_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            elif step == "email":
                context.user_data["email"] = text
                context.user_data["register_step"] = "description"
                await update.message.reply_text(f"🌟 *{MESSAGES[lang]['description_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            elif step == "description":
                context.user_data["description"] = text
                context.user_data["register_step"] = "manager"
                await update.message.reply_text(f"🌟 *{MESSAGES[lang]['manager_prompt']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            elif step == "manager":
                context.user_data["manager"] = text
                context.user_data["register_step"] = "categories"
                keyboard = [
                    [InlineKeyboardButton("Biscuit Production", callback_data="cat:Biscuit Production"),
                     InlineKeyboardButton("Agriculture", callback_data="cat:Agriculture")],
                    [InlineKeyboardButton("Packaging", callback_data="cat:Packaging"),
                     InlineKeyboardButton("Marketing", callback_data="cat:Marketing")],
                    [InlineKeyboardButton("Done", callback_data="cat:done")],
                    [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
                ]
                await update.message.reply_text(f"🌟 *{MESSAGES[lang]['categories_prompt']}* 🌟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            elif step == "public":
                context.user_data["public"] = text.lower() in ["yes", "y"]
                # Store pending registration instead of writing to sheet
                reg_data = {
                    "chat_id": str(chat_id),
                    "company": context.user_data["company"],
                    "phone": context.user_data["phone"],
                    "email": context.user_data["email"],
                    "description": context.user_data["description"],
                    "manager": context.user_data["manager"],
                    "categories": ",".join(context.user_data.get("categories", [])),
                    "timestamp": datetime.now().isoformat(),
                    "public": "Yes" if context.user_data["public"] else "No"
                }
                reg_id = f"{chat_id}_{reg_data['timestamp']}"
                context.bot_data["pending_registrations"][reg_id] = reg_data
                
                # Notify manager
                manager_text = (
                    f"New Network Registration Pending Approval:\n"
                    f"Company: {reg_data['company']}\n"
                    f"Phone: {reg_data['phone']}\n"
                    f"Email: {reg_data['email']}\n"
                    f"Description: {reg_data['description']}\n"
                    f"Manager: {reg_data['manager']}\n"
                    f"Categories: {reg_data['categories']}\n"
                    f"Public Email: {reg_data['public']}"
                )
                keyboard = [
                    [InlineKeyboardButton("✅ Approve", callback_data=f"approve:{reg_id}"),
                     InlineKeyboardButton("❌ Reject", callback_data=f"reject:{reg_id}")]
                ]
                await context.bot.send_message(MANAGER_CHAT_ID, manager_text, reply_markup=InlineKeyboardMarkup(keyboard))
                
                # Notify user
                await update.message.reply_text(f"🌟 *Registration submitted for approval!* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
                del context.user_data["register_step"]
    elif "quiz_step" in context.user_data:
        step = context.user_data["quiz_step"]
        module_id = context.user_data["quiz_module"]
        module = next(m for m in TRAINING_MODULES if m["id"] == module_id)
        question = module["quiz"][step - 1]
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if text.lower() == question["answer"].lower():
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['quiz_correct'].format(explain=question['explain'])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            context.user_data["quiz_score"] = context.user_data.get("quiz_score", 0) + 1
        else:
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['quiz_wrong'].format(answer=question['answer'], explain=question['explain'])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        if step < len(module["quiz"]):
            context.user_data["quiz_step"] += 1
            next_q = module["quiz"][step]
            keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz:{opt}")] for opt in next_q["options"]]
            keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")])
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['quiz_question'].format(num=step + 1, q=next_q['q'])}* 🌟",
                                            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            score = context.user_data.get("quiz_score", 0)
            context.user_data["completed_modules"] = context.user_data.get("completed_modules", []) + [module_id]
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['quiz_done'].format(score=score, total=len(module['quiz']))}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            del context.user_data["quiz_step"]
            del context.user_data["quiz_score"]
            if len(context.user_data["completed_modules"]) == 2:
                await update.message.reply_text(f"🌟 *{MESSAGES[lang]['survey_satisfaction']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
                context.user_data["survey_step"] = "mid"
            elif len(context.user_data["completed_modules"]) == len(TRAINING_MODULES):
                await update.message.reply_text(f"🌟 *{MESSAGES[lang]['survey_satisfaction']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
                context.user_data["survey_step"] = "end"
    elif "profile_step" in context.user_data:
        step = context.user_data["profile_step"]
        cell = training_sheet.find(str(chat_id))
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if cell:
            row = cell.row
            if step == "name":
                training_sheet.update_cell(row, 2, text)
            elif step == "phone":
                training_sheet.update_cell(row, 3, text)
            elif step == "email":
                training_sheet.update_cell(row, 4, text)
            elif step == "company":
                training_sheet.update_cell(row, 5, text)
            await update.message.reply_text(f"🌟 *{MESSAGES[lang]['profile_updated']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            del context.user_data["profile_step"]
    elif "survey_step" in context.user_data:
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            rating = int(text)
            if 1 <= rating <= 5:
                await update.message.reply_text(f"🌟 *{MESSAGES[lang]['survey_thanks']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
                del context.user_data["survey_step"]
            else:
                await update.message.reply_text("Please enter a number between 1 and 5.", reply_markup=reply_markup)
        except ValueError:
            await update.message.reply_text("Please enter a valid number (1-5).", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "en")
    print(f"Button clicked: {query.data}")

    try:
        if "lang:" in query.data:
            lang_choice = query.data.split("lang:")[1]
            context.user_data["lang"] = lang_choice
            context.user_data["start_register_step"] = "username"
            keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"🌟 *Please provide your username:* 🌟",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        elif "cmd:" in query.data:
            cmd = query.data.split("cmd:")[1]
            handlers = {
                "ask": ask,
                "resources": resources,
                "training_events": training_events,
                "networking": networking,
                "news": news,
                "contact": contact,
                "subscribenews": subscribenews,
                "learn_startup_skills": learn_startup_skills,
                "update_profile": update_profile,
                "ask_again": ask,
                "main_menu": lambda u, c: show_options(u, c, lang),
                "all_resources": lambda u, c: all_resources(u, c, lang),
                "signup": signup,
                "register": register,
                "cancel": lambda u, c: cancel_registration(u, c, lang),
                "start_over": start_over
            }
            if cmd in handlers:
                await handlers[cmd](update, context)
        elif "filter:" in query.data:
            filter_type = query.data.split("filter:")[1]
            filtered_trainings = (
                [t for t in PAST_TRAININGS if t.get("video")] if filter_type == "videos" else
                [t for t in PAST_TRAININGS if t.get("resources")]
            )
            sections = []
            for training in filtered_trainings:
                links = []
                if training.get("video"):
                    links.append(f"📹 [Watch]({training['video']})")
                if training.get("resources"):
                    links.append(f"📄 [Read]({training['resources']})")
                section = (
                    f"✨ *{training['name']}* _({training['date']})_\n"
                    f"{' | '.join(links)}\n"
                    f"_{training['description']}_"
                )
                sections.append(section)
            formatted_text = (
                f"🌟 *{MESSAGES[lang]['resources_title']}* 🌟\n\n" +
                "\n🌟====🌟\n".join(sections)
            )
            keyboard = [
                [
                    InlineKeyboardButton("🎥 Videos Only", callback_data="filter:videos"),
                    InlineKeyboardButton("📜 Docs Only", callback_data="filter:resources")
                ],
                [
                    InlineKeyboardButton("⬇️ Get All Resources", callback_data="cmd:all_resources"),
                    InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")
                ]
            ]
            await query.edit_message_text(formatted_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)
        elif "module:" in query.data:
            module_id = int(query.data.split("module:")[1])
            module = next(m for m in TRAINING_MODULES if m["id"] == module_id)
            completed = context.user_data.get("completed_modules", [])
            keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            if all(prereq in completed for prereq in module["prereq"]):
                await query.message.reply_text(f"🌟 *{MESSAGES[lang]['module_study'].format(name=module['name'], content=module['content'])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
                keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz:{opt}")] for opt in module["quiz"][0]["options"]]
                keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")])
                await query.message.reply_text(f"🌟 *{MESSAGES[lang]['quiz_start'].format(name=module['name'])}* 🌟", parse_mode="Markdown")
                await query.message.reply_text(f"🌟 *{MESSAGES[lang]['quiz_question'].format(num=1, q=module['quiz'][0]['q'])}* 🌟",
                                               reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                context.user_data["quiz_step"] = 1
                context.user_data["quiz_module"] = module_id
            else:
                await query.message.reply_text(f"🌟 *{MESSAGES[lang]['prereq_error']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
        elif "quiz:" in query.data:
            answer = query.data.split("quiz:")[1]
            step = context.user_data["quiz_step"]
            module_id = context.user_data["quiz_module"]
            module = next(m for m in TRAINING_MODULES if m["id"] == module_id)
            question = module["quiz"][step - 1]
            keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            if answer == question["answer"]:
                await query.message.reply_text(f"🌟 *{MESSAGES[lang]['quiz_correct'].format(explain=question['explain'])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
                context.user_data["quiz_score"] = context.user_data.get("quiz_score", 0) + 1
            else:
                await query.message.reply_text(f"🌟 *{MESSAGES[lang]['quiz_wrong'].format(answer=question['answer'], explain=question['explain'])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            if step < len(module["quiz"]):
                context.user_data["quiz_step"] += 1
                next_q = module["quiz"][step]
                keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz:{opt}")] for opt in next_q["options"]]
                keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")])
                await query.message.reply_text(f"🌟 *{MESSAGES[lang]['quiz_question'].format(num=step + 1, q=next_q['q'])}* 🌟",
                                               reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            else:
                score = context.user_data.get("quiz_score", 0)
                context.user_data["completed_modules"] = context.user_data.get("completed_modules", []) + [module_id]
                await query.message.reply_text(f"🌟 *{MESSAGES[lang]['quiz_done'].format(score=score, total=len(module['quiz']))}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
                del context.user_data["quiz_step"]
                del context.user_data["quiz_score"]
                if len(context.user_data["completed_modules"]) == 2:
                    await query.message.reply_text(f"🌟 *{MESSAGES[lang]['survey_satisfaction']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
                    context.user_data["survey_step"] = "mid"
                elif len(context.user_data["completed_modules"]) == len(TRAINING_MODULES):
                    await query.message.reply_text(f"🌟 *{MESSAGES[lang]['survey_satisfaction']}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
                    context.user_data["survey_step"] = "end"
        elif "profile:" in query.data:
            field = query.data.split("profile:")[1]
            context.user_data["profile_step"] = field
            keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
            await query.message.reply_text(f"🌟 *{MESSAGES[lang][f'profile_{field}']}* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        elif "cat:" in query.data:
            cat = query.data.split("cat:")[1]
            if cat == "done":
                context.user_data["register_step"] = "public"
                keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
                await query.edit_message_text(f"🌟 *{MESSAGES[lang]['public_prompt']}* 🌟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                context.user_data.setdefault("categories", []).append(cat)
                await query.edit_message_text(f"🌟 *{MESSAGES[lang]['cat_added'].format(cat=cat)}* 🌟", parse_mode="Markdown")
        elif "train:" in query.data:
            training = query.data.split("train:")[1]
            context.user_data["action"] = training
            data = [context.user_data["username"], context.user_data["name"], context.user_data["phone"],
                    training, datetime.now().isoformat()]
            training_sheet.append_row(data)
            await context.bot.send_message(MANAGER_CHAT_ID, f"New Training Signup: {data}")
            keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"🌟 *{MESSAGES[lang]['signup_thanks'].format(name=data[1])}* 🌟", parse_mode="Markdown", reply_markup=reply_markup)
            del context.user_data["signup_step"]
        elif "approve:" in query.data:
            reg_id = query.data.split("approve:")[1]
            if query.from_user.id == int(MANAGER_CHAT_ID):
                if reg_id in context.bot_data["pending_registrations"]:
                    reg_data = context.bot_data["pending_registrations"].pop(reg_id)
                    if "username" in reg_data:  # Initial registration
                        users_sheet.append_row([reg_data["chat_id"], reg_data["username"], reg_data["name"],
                                                reg_data["phone"], reg_data["email"], reg_data["company"],
                                                reg_data["description"], reg_data["timestamp"], "Approved"])
                        await query.edit_message_text(f"✅ Approved: {reg_data['username']} registered!")
                        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await context.bot.send_message(reg_data["chat_id"],
                            f"🌟 *Congratulations! You’re registered with BenuBot!* 🌟",
                            parse_mode="Markdown",
                            reply_markup=reply_markup)
                    else:  # Networking registration
                        network_sheet.append_row([reg_data["chat_id"], reg_data["company"], reg_data["phone"],
                                                  reg_data["email"], reg_data["description"], reg_data["manager"],
                                                  reg_data["categories"], reg_data["timestamp"], reg_data["public"]])
                        await query.edit_message_text(f"✅ Approved: {reg_data['company']} added to network!")
                        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await context.bot.send_message(reg_data["chat_id"],
                            f"🌟 *{MESSAGES[lang]['register_thanks'].format(company=reg_data['company'])}* 🌟",
                            parse_mode="Markdown",
                            reply_markup=reply_markup)
                else:
                    await query.edit_message_text("⚠️ Registration no longer pending.")
            else:
                await query.edit_message_text("⚠️ Only the manager can approve registrations.")
        elif "reject:" in query.data:
            reg_id = query.data.split("reject:")[1]
            if query.from_user.id == int(MANAGER_CHAT_ID):
                if reg_id in context.bot_data["pending_registrations"]:
                    reg_data = context.bot_data["pending_registrations"].pop(reg_id)
                    await query.edit_message_text(f"❌ Rejected: {reg_data.get('username', reg_data.get('company'))} not added.")
                    await context.bot.send_message(reg_data["chat_id"],
                        "🌟 *Registration rejected by manager.* 🌟",
                        parse_mode="Markdown")
                else:
                    await query.edit_message_text("⚠️ Registration no longer pending.")
            else:
                await query.edit_message_text("⚠️ Only the manager can reject registrations.")
    except telegram.error.BadRequest as e:
        print(f"Query error: {str(e)}")
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        await query.message.reply_text("Sorry, that button timed out. Please try again!", reply_markup=InlineKeyboardMarkup(keyboard))

async def all_resources(update: Update, context: ContextTypes.DEFAULT_TYPE, lang):
    query = update.callback_query
    links = []
    for training in PAST_TRAININGS:
        if training.get("video"):
            links.append(f"📹 *{training['name']}* Video: {training['video']}")
        if training.get("resources"):
            links.append(f"📄 *{training['name']}* Resource: {training['resources']}")
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    await query.message.reply_text(
        f"🌟 *All Resources* 🌟\n\n" + "\n".join(links),
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE, lang):
    query = update.callback_query
    del context.user_data["start_register_step"]
    keyboard = [[InlineKeyboardButton("🔙 Back to Start", callback_data="cmd:start_over")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"🌟 *Registration cancelled. Use /start to try again!* 🌟",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def start_over(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

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
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
        await app.bot.send_message(chat_id, f"🌟 Reminder: *{name}* training on _{date}_ is in 7 days! Reply /training_events for details.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    app = Application.builder().token("7910442120:AAFMUhnwTONoyF1xilwRpjWIRCTmGa0den4").build()
    init_bot_data(app)  # Initialize bot_data
    app.add_handler(CommandHandler("start", start))
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