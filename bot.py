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
training_sheet = sheet.worksheet("TrainingSignups")
network_sheet = sheet.worksheet("NetworkingRegistrations")

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
    {"name": "Intro to Fortification", "date": "2025-03-10", "video": "https://youtube.com/example", "resources": "https://drive.google.com/example"},
    {"name": "Biscuit Processing Techniques", "date": "2025-03-20", "video": "https://youtu.be/Q9TCM89oNfU?si=5Aia87X1csYSZ4g6", "resources": "https://drive.google.com/file/d/1HTr62gOcWHEU76-OXDnzJRf11l7nXKPv/view"},
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
        "ask_prompt": "እባክዎ ጥያቄዎን ይፃፉ፣ እኔም መልስ እፈልግልዎታለሁ!",
        "ask_error": "ይቅርታ፣ አሁን መልስ ለመስጠት ችግር አለብኝ። ቆይተው ይሞክሩ!",
        "resources_title": "የሚገኙ ሥልጠና መሣሪያዎች:",
        "no_resources": "እስካሁን መሣሪያዎች የሉም።",
        "trainings_past": "ያለፉ ሥልጠና ዝግጅቶች:",
        "trainings_upcoming": "መጪ ሥልጠና ዝግጅቶች:",
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
                "parameters": {
                    "max_new_tokens": 100,
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

            # Fancy formatting with Markdown
            formatted_answer = (
                f"✨ *Your Answer* ✨\n"
                f"➡️ *Question:* {question}\n"
                f"📝 *Answer:* _{answer}_\n"
                f"🎉 Powered by BenuBot!"
            )
            keyboard = [
                [InlineKeyboardButton("Ask Another Question", callback_data="cmd:ask_again"),
                 InlineKeyboardButton("Back to Main Menu", callback_data="cmd:main_menu")]
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
                 InlineKeyboardButton("Back to Main Menu", callback_data="cmd:main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(error_msg, parse_mode="Markdown", reply_markup=reply_markup)
        finally:
            del context.user_data["asking"]

async def resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    messages = MESSAGES[lang]

    # Build the resource list with Markdown and inline buttons
    resource_list = []
    for idx, training in enumerate(PAST_TRAININGS, 1):
        if training.get("resources"):
            resource_list.append(
                f"{idx}. *{training['name']}* _({training['date']})_ "
                f"[View Resource]({training['resources']})"
            )

    # Construct the message
    if resource_list:
        formatted_text = (
            f"📚 *{messages['resources_title']}* 📚\n" +
            "\n".join(resource_list) +
            "\n---\n"
        )
    else:
        formatted_text = f"📚 *{messages['resources_title']}* 📚\n{messages['no_resources']}\n---\n"

    # Add "Back to Main Menu" button
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(formatted_text, parse_mode="Markdown", reply_markup=reply_markup, disable_web_page_preview=True)

async def training_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    past_text = f"{MESSAGES[lang]['trainings_past']}\n" + "\n".join(
        f"- {t['name']} ({t['date']}): Video: {t['video'] or 'No video'}, Resources: {t['resources'] or 'No resources'}"
        for t in PAST_TRAININGS
    )
    upcoming_text = f"{MESSAGES[lang]['trainings_upcoming']}\n" + "\n".join(
        f"- {t['name']} ({t['date']}) - Reply /signup to join"
        for t in UPCOMING_TRAININGS
    )
    await query.message.reply_text(f"{past_text}\n\n{upcoming_text}")

async def signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    lang = context.user_data.get("lang", "en")
    context.user_data["signup_step"] = "name"
    await update.message.reply_text(MESSAGES[lang]["signup_prompt"])

async def networking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
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
    await query.message.reply_text(text)

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    lang = context.user_data.get("lang", "en")
    context.user_data["register_step"] = "company"
    await update.message.reply_text(MESSAGES[lang]["register_prompt"])

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    await query.message.reply_text(
        f"{MESSAGES[lang]['news_title']}\n"
        "1. March 12, 2025: Benu secured ETB 2.9M from SWR Ethiopia.\n"
        "2. April 10, 2025: First training held—29 saleswomen trained! See /training_events.\n"
        "3. May 2025: New production line launches.\n"
        "4. May 15, 2025: Networking Event—register at /networking or /training_events.\n"
        "Use /subscribenews for updates!"
    )

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    await query.message.reply_text(MESSAGES[lang]["contact_info"])

async def subscribenews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.callback_query.message.chat_id
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    if training_sheet.find(str(chat_id)) is None:
        training_sheet.append_row([str(chat_id), "", "", "", "", datetime.now().isoformat()])
    await query.message.reply_text(MESSAGES[lang]["subscribed"])

async def learn_startup_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton(m["name"], callback_data=f"module:{m['id']}")]
        for m in TRAINING_MODULES
    ]
    await query.message.reply_text(MESSAGES[lang]["modules_title"], reply_markup=InlineKeyboardMarkup(keyboard))

async def update_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("Name", callback_data="profile:name"),
         InlineKeyboardButton("Phone", callback_data="profile:phone")],
        [InlineKeyboardButton("Email", callback_data="profile:email"),
         InlineKeyboardButton("Company", callback_data="profile:company")]
    ]
    await query.message.reply_text(MESSAGES[lang]["profile_prompt"], reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text
    lang = context.user_data.get("lang", "en")

    if "asking" in context.user_data:
        await handle_ask(update, context)
    elif "signup_step" in context.user_data:
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
            context.user_data["signup_step"] = "survey"
            await update.message.reply_text(MESSAGES[lang]["survey_company_size"])
        elif step == "survey":
            context.user_data["company_size"] = text
            data = [str(chat_id), context.user_data["name"], context.user_data["phone"],
                    context.user_data["email"], context.user_data["company"], datetime.now().isoformat(), text]
            training_sheet.append_row(data)
            await context.bot.send_message(MANAGER_CHAT_ID, f"New Signup: {data[1:]}")
            await update.message.reply_text(MESSAGES[lang]["signup_thanks"].format(name=data[1]))
            del context.user_data["signup_step"]
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
    elif "quiz_step" in context.user_data:
        step = context.user_data["quiz_step"]
        module_id = context.user_data["quiz_module"]
        module = next(m for m in TRAINING_MODULES if m["id"] == module_id)
        question = module["quiz"][step - 1]
        if text.lower() == question["answer"].lower():
            await update.message.reply_text(MESSAGES[lang]["quiz_correct"].format(explain=question["explain"]))
            context.user_data["quiz_score"] = context.user_data.get("quiz_score", 0) + 1
        else:
            await update.message.reply_text(MESSAGES[lang]["quiz_wrong"].format(answer=question["answer"], explain=question["explain"]))
        if step < len(module["quiz"]):
            context.user_data["quiz_step"] += 1
            next_q = module["quiz"][step]
            keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz:{opt}")] for opt in next_q["options"]]
            await update.message.reply_text(MESSAGES[lang]["quiz_question"].format(num=step + 1, q=next_q["q"]),
                                            reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            score = context.user_data.get("quiz_score", 0)
            context.user_data["completed_modules"] = context.user_data.get("completed_modules", []) + [module_id]
            await update.message.reply_text(MESSAGES[lang]["quiz_done"].format(score=score, total=len(module["quiz"])))
            del context.user_data["quiz_step"]
            del context.user_data["quiz_score"]
            if len(context.user_data["completed_modules"]) == 2:
                await update.message.reply_text(MESSAGES[lang]["survey_satisfaction"])
                context.user_data["survey_step"] = "mid"
            elif len(context.user_data["completed_modules"]) == len(TRAINING_MODULES):
                await update.message.reply_text(MESSAGES[lang]["survey_satisfaction"])
                context.user_data["survey_step"] = "end"
    elif "profile_step" in context.user_data:
        step = context.user_data["profile_step"]
        cell = training_sheet.find(str(chat_id))
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
            await update.message.reply_text(MESSAGES[lang]["profile_updated"])
            del context.user_data["profile_step"]
    elif "survey_step" in context.user_data:
        try:
            rating = int(text)
            if 1 <= rating <= 5:
                await update.message.reply_text(MESSAGES[lang]["survey_thanks"])
                del context.user_data["survey_step"]
            else:
                await update.message.reply_text("Please enter a number between 1 and 5.")
        except ValueError:
            await update.message.reply_text("Please enter a valid number (1-5).")

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
                "main_menu": lambda u, c: show_options(u, c, lang)
            }
            if cmd in handlers:
                await handlers[cmd](update, context)
        elif "module:" in query.data:
            module_id = int(query.data.split("module:")[1])
            module = next(m for m in TRAINING_MODULES if m["id"] == module_id)
            completed = context.user_data.get("completed_modules", [])
            if all(prereq in completed for prereq in module["prereq"]):
                await query.message.reply_text(MESSAGES[lang]["module_study"].format(name=module["name"], content=module["content"]))
                keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz:{opt}")] for opt in module["quiz"][0]["options"]]
                await query.message.reply_text(MESSAGES[lang]["quiz_start"].format(name=module["name"]))
                await query.message.reply_text(MESSAGES[lang]["quiz_question"].format(num=1, q=module["quiz"][0]["q"]),
                                               reply_markup=InlineKeyboardMarkup(keyboard))
                context.user_data["quiz_step"] = 1
                context.user_data["quiz_module"] = module_id
            else:
                await query.message.reply_text(MESSAGES[lang]["prereq_error"])
        elif "quiz:" in query.data:
            answer = query.data.split("quiz:")[1]
            step = context.user_data["quiz_step"]
            module_id = context.user_data["quiz_module"]
            module = next(m for m in TRAINING_MODULES if m["id"] == module_id)
            question = module["quiz"][step - 1]
            if answer == question["answer"]:
                await query.message.reply_text(MESSAGES[lang]["quiz_correct"].format(explain=question["explain"]))
                context.user_data["quiz_score"] = context.user_data.get("quiz_score", 0) + 1
            else:
                await query.message.reply_text(MESSAGES[lang]["quiz_wrong"].format(answer=question["answer"], explain=question["explain"]))
            if step < len(module["quiz"]):
                context.user_data["quiz_step"] += 1
                next_q = module["quiz"][step]
                keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz:{opt}")] for opt in next_q["options"]]
                await query.message.reply_text(MESSAGES[lang]["quiz_question"].format(num=step + 1, q=next_q["q"]),
                                               reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                score = context.user_data.get("quiz_score", 0)
                context.user_data["completed_modules"] = context.user_data.get("completed_modules", []) + [module_id]
                await query.message.reply_text(MESSAGES[lang]["quiz_done"].format(score=score, total=len(module["quiz"])))
                del context.user_data["quiz_step"]
                del context.user_data["quiz_score"]
                if len(context.user_data["completed_modules"]) == 2:
                    await query.message.reply_text(MESSAGES[lang]["survey_satisfaction"])
                    context.user_data["survey_step"] = "mid"
                elif len(context.user_data["completed_modules"]) == len(TRAINING_MODULES):
                    await query.message.reply_text(MESSAGES[lang]["survey_satisfaction"])
                    context.user_data["survey_step"] = "end"
        elif "profile:" in query.data:
            field = query.data.split("profile:")[1]
            context.user_data["profile_step"] = field
            await query.message.reply_text(MESSAGES[lang][f"profile_{field}"])
        elif "cat:" in query.data:
            cat = query.data.split("cat:")[1]
            if cat == "done":
                context.user_data["register_step"] = "public"
                await query.edit_message_text(MESSAGES[lang]["public_prompt"])
            else:
                context.user_data.setdefault("categories", []).append(cat)
                await query.edit_message_text(MESSAGES[lang]["cat_added"].format(cat=cat))
    except telegram.error.BadRequest as e:
        print(f"Query error: {str(e)}")
        await query.message.reply_text("Sorry, that button timed out. Please try again!")

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

def main():
    app = Application.builder().token("7910442120:AAFMUhnwTONoyF1xilwRpjWIRCTmGa0den4").build()
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