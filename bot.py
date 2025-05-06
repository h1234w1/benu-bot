import os
import json
import requests
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import telegram.error

# Initialize bot data
def init_bot_data(context):
    if "pending_registrations" not in context.bot_data:
        context.bot_data["pending_registrations"] = {}
    if "network_page" not in context.bot_data:
        context.bot_data["network_page"] = {}

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
collab_sheet = sheet.worksheet("Collaborations")
companies_sheet = sheet.worksheet("Companies")  # Create this sheet manually

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
            {"q": "What’s a low-cost promotion?", "options": ["TV Ads", "Social Media", "Billboards"], "answer": "Social Media", "explain": "Social media reaches audiences cheaply."}
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

# Categories
CATEGORIES = ["Biscuit Production", "Agriculture", "Packaging", "Marketing", "Logistics", "Finance"]

# Messages
MESSAGES = {
    "welcome": "Welcome to Benu’s Startup Support Bot!\nPlease select your purpose:",
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
    "register_prompt": "Please provide your company name (Step 1/7):",
    "news_title": "Latest Announcements:",
    "contact_info": "Contact Us:\nEmail: benu@example.com\nPhone: +251921756683\nAddress: Addis Ababa, Bole Sub city, Woreda 03, H.N. 4/10/A5/FL8",
    "subscribed": "Subscribed to news updates!",
    "signup_thanks": "Thanks for signing up, {name}!",
    "register_thanks": "Registered {company} in the network!",
    "phone_prompt": "Please provide your phone number (Step {step}/7):",
    "email_prompt": "Please provide your email (Step {step}/7):",
    "company_prompt": "Please provide your company name (Step 1/7):",
    "description_prompt": "Please provide a description of what your company does (Step 4/7):",
    "manager_prompt": "Please provide the manager’s name (Step 5/7):",
    "categories_prompt": "Select categories (Step 6/7, click Done when finished):",
    "public_prompt": "Share email publicly? (Step 7/7):",
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
    "network_search": "Search by keyword (e.g., company name):",
    "network_connect": "Request connection with {company}:",
    "network_event": "Join Networking Event (May 15, 2025):",
    "network_collab": "Propose collaboration with {company}:",
    "network_edit": "Edit your company profile:",
    "network_stats": "Network Stats:\n{stats}",
    "network_badge": "🎉 You earned the {badge} badge!",
    "network_invalid_email": "Invalid email format. Please use example@domain.com.",
    "network_invalid_phone": "Invalid phone format. Please use +2519xxxxxxxx.",
    "network_suggest_cat": "Suggest a new category:",
    "network_cat_added": "Category {cat} suggested for approval.",
    "network_rate": "Rate your connection with {company} (1-5):",
    "network_refer": "Invite a startup to join the network:",
    "network_showcase": "Startup of the Month: {company}\n{description}",
    "personal_name": "Please provide your full name (Step 1/4):",
    "personal_industry": "Select your industry of interest (Step 4/4):",
    "registration_submitted": "Registration submitted for approval!",
    "registration_approved": "Your registration has been approved! Welcome!",
    "registration_rejected": "Your registration was not approved. Please contact support."
}

# Bot functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Personal", callback_data="reg:personal"),
         InlineKeyboardButton("Company", callback_data="reg:company")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🌟 *Welcome to Benu’s Startup Support Bot!* 🌟\nPlease select your purpose:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def show_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.callback_query.message.chat_id)
    # Check approval status
    user_row = users_sheet.find(chat_id, in_column=1)  # ChatID column
    company_row = companies_sheet.find(chat_id, in_column=1)  # ChatID column
    if (user_row and users_sheet.cell(user_row.row, 7).value == "Approved") or \
       (company_row and companies_sheet.cell(company_row.row, 10).value == "Approved"):
        keyboard = [
            [InlineKeyboardButton(MESSAGES["ask"], callback_data="cmd:ask"),
             InlineKeyboardButton(MESSAGES["resources"], callback_data="cmd:resources")],
            [InlineKeyboardButton(MESSAGES["training_events"], callback_data="cmd:training_events"),
             InlineKeyboardButton(MESSAGES["networking"], callback_data="cmd:networking")],
            [InlineKeyboardButton(MESSAGES["news"], callback_data="cmd:news"),
             InlineKeyboardButton(MESSAGES["contact"], callback_data="cmd:contact")],
            [InlineKeyboardButton(MESSAGES["subscribenews"], callback_data="cmd:subscribenews"),
             InlineKeyboardButton(MESSAGES["learn_startup_skills"], callback_data="cmd:learn_startup_skills")],
            [InlineKeyboardButton(MESSAGES["update_profile"], callback_data="cmd:update_profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            f"🌟 *{MESSAGES['options']}* 🌟", 
            reply_markup=reply_markup, 
            parse_mode="Markdown"
        )
    else:
        await update.callback_query.edit_message_text(
            "🌟 *Awaiting approval.* 🌟\nYou’ll see the main menu once approved.",
            parse_mode="Markdown"
        )

async def networking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    context.bot_data["network_page"][str(chat_id)] = 0  # Reset page
    keyboard = [
        [InlineKeyboardButton("Browse by Category", callback_data="network:category"),
         InlineKeyboardButton("Search by Keyword", callback_data="network:search")],
        [InlineKeyboardButton("Register Company", callback_data="cmd:register"),
         InlineKeyboardButton("Edit Profile", callback_data="network:edit")],
        [InlineKeyboardButton("Join Event", callback_data="network:event"),
         InlineKeyboardButton("Invite Startup", callback_data="network:refer")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
    ]
    if query.from_user.id == int(MANAGER_CHAT_ID):
        keyboard.insert(0, [InlineKeyboardButton("View Stats", callback_data="network:stats"),
                            InlineKeyboardButton("Manage Categories", callback_data="network:manage_cat")])
    await query.message.reply_text(
        f"🌟 *{MESSAGES['networking_title']}* 🌟", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="Markdown"
    )

async def network_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat:{cat}")] for cat in CATEGORIES]
    keyboard.append([InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")])
    await query.edit_message_text(
        "🌟 *Select a Category* 🌟", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="Markdown"
    )

async def network_list(update: Update, context: ContextTypes.DEFAULT_TYPE, category=None, search=None):
    query = update.callback_query
    chat_id = query.message.chat_id
    page = context.bot_data["network_page"].get(str(chat_id), 0)
    network_data = network_sheet.get_all_records()
    companies = []

    for entry in network_data:
        if category and category not in entry["Categories"].split(","):
            continue
        if search:
            search_lower = search.lower()
            if not (search_lower in entry["Company"].lower() or 
                    search_lower in entry["Description"].lower() or 
                    search_lower in entry["Manager"].lower()):
                continue
        companies.append(entry)

    total = len(companies)
    per_page = 5
    start = page * per_page
    end = start + per_page
    sections = []
    for company in companies[start:end]:
        contact = company["Phone"] if company["PublicEmail"] == "Yes" else "Private"
        sections.append(
            f"🏢 *{company['Company']}*\n"
            f"📝 _{company['Description']}_\n"
            f"📞 Contact: {contact}\n"
            f"👤 Manager: {company['Manager']}\n"
            f"📅 Joined: {company['RegDate']}"
        )

    text = f"🌟 *Companies (Page {page + 1}/{max(1, (total + per_page - 1) // per_page)})* 🌟\n\n" + "\n🌟----🌟\n".join(sections)
    keyboard = []
    if total > per_page:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page:{page-1}:{category or ''}:{search or ''}"))
        if end < total:
            nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"page:{page+1}:{category or ''}:{search or ''}"))
        keyboard.append(nav)
    for company in companies[start:end]:
        keyboard.append([InlineKeyboardButton(f"Contact {company['Company']}", callback_data=f"connect:{company['Company']}")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def network_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data["network_search"] = True
    keyboard = [[InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")]]
    await query.edit_message_text(
        f"🌟 *{MESSAGES['network_search']}* 🌟", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="Markdown"
    )

async def network_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    company = query.data.split("connect:")[1]
    network_data = network_sheet.get_all_records()
    entry = next((e for e in network_data if e["Company"] == company), None)
    if not entry:
        await query.edit_message_text("⚠️ Company not found.", parse_mode="Markdown")
        return
    if entry["PublicEmail"] == "Yes":
        text = f"🌟 *Contact {company}* 🌟\nEmail: {entry['Email']}\nPhone: {entry['Phone']}"
    else:
        text = f"🌟 *Connection Requested* 🌟\nWe’ve notified {company}’s manager."
        await context.bot.send_message(
            MANAGER_CHAT_ID,
            f"Connection request for {company} from user {query.from_user.id}",
            parse_mode="Markdown"
        )
    keyboard = [
        [InlineKeyboardButton("Rate Connection", callback_data=f"rate:{company}")],
        [InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")]
    ]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def network_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [[InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")]]
    await query.edit_message_text(
        f"🌟 *{MESSAGES['network_event']}* 🌟\nRegister for the May 15, 2025, networking event!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def network_collab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    company = query.data.split("collab:")[1]
    context.user_data["collab_company"] = company
    context.user_data["collab_step"] = True
    keyboard = [[InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")]]
    await query.edit_message_text(
        f"🌟 *{MESSAGES['network_collab'].format(company=company)}* 🌟\nPlease describe your collaboration proposal:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def network_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    company_row = companies_sheet.find(str(chat_id), in_column=1)
    if not company_row:
        await query.edit_message_text("⚠️ You haven’t registered a company yet.", parse_mode="Markdown")
        return
    row = companies_sheet.row_values(company_row.row)
    context.user_data["register_step"] = "company"
    context.user_data["edit_mode"] = True
    context.user_data["company_data"] = {
        "Company": row[1],
        "Phone": row[2],
        "Email": row[3],
        "Description": row[4],
        "Manager": row[5],
        "Categories": row[6].split(",") if row[6] else [],
        "PublicEmail": row[8],
        "Status": row[9]
    }
    keyboard = [[InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")]]
    await query.edit_message_text(
        f"🌟 *{MESSAGES['register_prompt']}* 🌟\nCurrent: {row[1]}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def network_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != int(MANAGER_CHAT_ID):
        await query.edit_message_text("⚠️ Manager access only.", parse_mode="Markdown")
        return
    network_data = network_sheet.get_all_records()
    cat_counts = {cat: 0 for cat in CATEGORIES}
    for entry in network_data:
        for cat in entry["Categories"].split(","):
            if cat in cat_counts:
                cat_counts[cat] += 1
    stats = [f"{cat}: {count} companies" for cat, count in cat_counts.items()]
    stats.append(f"Total: {len(network_data)} companies")
    text = MESSAGES["network_stats"].format(stats="\n".join(stats))
    keyboard = [[InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def network_manage_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != int(MANAGER_CHAT_ID):
        await query.edit_message_text("⚠️ Manager access only.", parse_mode="Markdown")
        return
    keyboard = [
        [InlineKeyboardButton("Add Category", callback_data="cat:add"),
         InlineKeyboardButton("Remove Category", callback_data="cat:remove")],
        [InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")]
    ]
    await query.edit_message_text(
        "🌟 *Manage Categories* 🌟", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="Markdown"
    )

async def network_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    company = query.data.split("rate:")[1]
    context.user_data["rate_company"] = company
    context.user_data["rate_step"] = True
    keyboard = [[InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")]]
    await query.edit_message_text(
        f"🌟 *{MESSAGES['network_rate'].format(company=company)}* 🌟", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="Markdown"
    )

async def network_refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    referral_link = f"https://t.me/BenuStartupBot?start=refer_{chat_id}"
    text = f"🌟 *{MESSAGES['network_refer']}* 🌟\nShare this link: {referral_link}"
    keyboard = [[InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
    # Check if already registered in Companies
    company_row = companies_sheet.find(str(chat_id), in_column=1)
    if company_row and companies_sheet.cell(company_row.row, 10).value == "Approved":
        row = companies_sheet.row_values(company_row.row)
        network_sheet.append_row([
            str(chat_id), row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]
        ])
        await (update.message.reply_text if update.message else update.callback_query.message.reply_text)(
            f"🌟 *{MESSAGES['register_thanks'].format(company=row[1])}* 🌟",
            parse_mode="Markdown"
        )
        await show_options(update, context)
    else:
        context.user_data["register_step"] = "company"
        context.user_data["edit_mode"] = False
        context.user_data["company_data"] = {}
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
        await (update.message.reply_text if update.message else update.callback_query.message.reply_text)(
            f"🌟 *{MESSAGES['company_prompt']}* 🌟", 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text

    if context.user_data.get("asking"):
        await handle_ask(update, context)
    elif context.user_data.get("personal_step"):
        step = context.user_data["personal_step"]
        personal_data = context.user_data.setdefault("personal_data", {})
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if step == "name":
            personal_data["Name"] = text
            context.user_data["personal_step"] = "phone"
            await update.message.reply_text(
                f"🌟 *{MESSAGES['phone_prompt'].format(step=2)}* 🌟",
                parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "phone":
            if not re.match(r"\+2519\d{8}$", text):
                await update.message.reply_text(
                    f"🌟 *{MESSAGES['network_invalid_phone']}* 🌟", 
                    parse_mode="Markdown", reply_markup=reply_markup)
                return
            personal_data["Phone"] = text
            context.user_data["personal_step"] = "email"
            await update.message.reply_text(
                f"🌟 *{MESSAGES['email_prompt'].format(step=3)}* 🌟",
                parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "email":
            if not re.match(r"[^@]+@[^@]+\.[^@]+", text):
                await update.message.reply_text(
                    f"🌟 *{MESSAGES['network_invalid_email']}* 🌟", 
                    parse_mode="Markdown", reply_markup=reply_markup)
                return
            personal_data["Email"] = text
            context.user_data["personal_step"] = "industry"
            keyboard = [[InlineKeyboardButton(cat, callback_data=f"ind:{cat}")] for cat in CATEGORIES]
            keyboard.append([InlineKeyboardButton("Done", callback_data="ind:done")])
            keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")])
            await update.message.reply_text(
                f"🌟 *{MESSAGES['personal_industry']}* 🌟", 
                reply_markup=InlineKeyboardMarkup(keyboard), 
                parse_mode="Markdown")
    elif context.user_data.get("register_step"):
        step = context.user_data["register_step"]
        edit_mode = context.user_data.get("edit_mode", False)
        company_data = context.user_data["company_data"]
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        step_count = {"company": 1, "phone": 2, "email": 3, "description": 4, "manager": 5, "categories": 6, "public": 7}
        if step == "company":
            company_data["Company"] = text
            context.user_data["register_step"] = "phone"
            await update.message.reply_text(
                f"🌟 *{MESSAGES['phone_prompt'].format(step=2)}* 🌟",
                parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "phone":
            if not re.match(r"\+2519\d{8}$", text):
                await update.message.reply_text(
                    f"🌟 *{MESSAGES['network_invalid_phone']}* 🌟", 
                    parse_mode="Markdown", reply_markup=reply_markup)
                return
            company_data["Phone"] = text
            context.user_data["register_step"] = "email"
            await update.message.reply_text(
                f"🌟 *{MESSAGES['email_prompt'].format(step=3)}* 🌟",
                parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "email":
            if not re.match(r"[^@]+@[^@]+\.[^@]+", text):
                await update.message.reply_text(
                    f"🌟 *{MESSAGES['network_invalid_email']}* 🌟", 
                    parse_mode="Markdown", reply_markup=reply_markup)
                return
            company_data["Email"] = text
            context.user_data["register_step"] = "description"
            await update.message.reply_text(
                f"🌟 *{MESSAGES['description_prompt']}* 🌟",
                parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "description":
            company_data["Description"] = text
            context.user_data["register_step"] = "manager"
            await update.message.reply_text(
                f"🌟 *{MESSAGES['manager_prompt']}* 🌟",
                parse_mode="Markdown", reply_markup=reply_markup)
        elif step == "manager":
            company_data["Manager"] = text
            context.user_data["register_step"] = "categories"
            keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat:{cat}")] for cat in CATEGORIES]
            keyboard.append([InlineKeyboardButton("Suggest Category", callback_data="cat:suggest")])
            keyboard.append([InlineKeyboardButton("Done", callback_data="cat:done")])
            keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")])
            await update.message.reply_text(
                f"🌟 *{MESSAGES['categories_prompt']}* 🌟", 
                reply_markup=InlineKeyboardMarkup(keyboard), 
                parse_mode="Markdown")
        elif step == "public":
            company_data["PublicEmail"] = "Yes" if text.lower() in ["yes", "y"] else "No"
            reg_data = {
                "chat_id": str(chat_id),
                "type": "company",
                "company": company_data["Company"],
                "phone": company_data["Phone"],
                "email": company_data["Email"],
                "description": company_data["Description"],
                "manager": company_data["Manager"],
                "categories": ",".join(company_data.get("Categories", [])),
                "reg_date": datetime.now().isoformat(),
                "public": company_data["PublicEmail"]
            }
            reg_id = f"{chat_id}_{reg_data['reg_date']}"
            context.bot_data["pending_registrations"][reg_id] = reg_data
            manager_text = (
                f"New Company Registration Pending Approval:\n"
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
            if edit_mode:
                row = companies_sheet.find(str(chat_id), in_column=1)
                if row:
                    companies_sheet.delete_rows(row.row)
            companies_sheet.append_row([
                reg_data["chat_id"], reg_data["company"], reg_data["phone"],
                reg_data["email"], reg_data["description"], reg_data["manager"],
                reg_data["categories"], reg_data["reg_date"], reg_data["public"], "Pending"
            ])
            await update.message.reply_text(
                f"🌟 *{MESSAGES['registration_submitted']}* 🌟", 
                parse_mode="Markdown", reply_markup=reply_markup)
            del context.user_data["register_step"]
            del context.user_data["company_data"]
            del context.user_data["edit_mode"]
            if "Categories" in company_data:
                del company_data["Categories"]
    elif context.user_data.get("network_search"):
        await network_list(update, context, search=text)
        del context.user_data["network_search"]
    elif context.user_data.get("collab_step"):
        company = context.user_data["collab_company"]
        collab_sheet.append_row([str(chat_id), company, text, datetime.now().isoformat()])
        await context.bot.send_message(
            MANAGER_CHAT_ID,
            f"Collaboration proposal for {company}:\n{text}\nFrom user {chat_id}",
            parse_mode="Markdown"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")]]
        await update.message.reply_text(
            "🌟 *Proposal submitted!* 🌟", 
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        del context.user_data["collab_step"]
        del context.user_data["collab_company"]
    elif context.user_data.get("rate_step"):
        try:
            rating = int(text)
            if 1 <= rating <= 5:
                company = context.user_data["rate_company"]
                collab_sheet.append_row([str(chat_id), company, f"Rating: {rating}", datetime.now().isoformat()])
                keyboard = [[InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")]]
                await update.message.reply_text(
                    f"🌟 *{MESSAGES['survey_thanks']}* 🌟", 
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
                # Award badge for 5 connections
                user_connections = len([r for r in collab_sheet.get_all_records() if r["ChatID"] == str(chat_id)])
                if user_connections >= 5:
                    user_row = users_sheet.find(str(chat_id), in_column=1)
                    if user_row:
                        users_sheet.update_cell(user_row.row, 8, "Connector")
                        await update.message.reply_text(
                            f"🌟 *{MESSAGES['network_badge'].format(badge='Connector')}* 🌟", 
                            parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    "Please enter a number between 1 and 5.", 
                    parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text(
                "Please enter a valid number (1-5).", 
                parse_mode="Markdown")
        del context.user_data["rate_step"]
        del context.user_data["rate_company"]
    elif context.user_data.get("suggest_cat"):
        reg_id = f"{chat_id}_{datetime.now().isoformat()}"
        context.bot_data["pending_registrations"][reg_id] = {
            "chat_id": str(chat_id),
            "category": text,
            "type": "category",
            "reg_date": datetime.now().isoformat()
        }
        await context.bot.send_message(
            MANAGER_CHAT_ID,
            f"New category suggestion: {text}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approve", callback_data=f"approve:{reg_id}"),
                 InlineKeyboardButton("❌ Reject", callback_data=f"reject:{reg_id}")]
            ])
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Networking", callback_data="cmd:networking")]]
        await update.message.reply_text(
            f"🌟 *{MESSAGES['network_cat_added'].format(cat=text)}* 🌟", 
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        del context.user_data["suggest_cat"]

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        f"🌟 *{MESSAGES['ask_prompt']}* 🌟\n\nProcessing your request...",
        parse_mode="Markdown"
    )
    context.user_data["asking"] = True

async def handle_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("asking"):
        question = update.message.text
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
            response = requests.post(HF_API_URL, json=payload, headers=headers, timeout=10)
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
            print(f"HF_API error: {str(e)}")
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

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        if "cmd:" in query.data:
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
                "main_menu": show_options,
                "all_resources": all_resources,
                "signup": signup,
                "register": register,
                "cancel": cancel_registration
            }
            if cmd in handlers:
                await handlers[cmd](update, context)
        elif "reg:" in query.data:
            reg_type = query.data.split("reg:")[1]
            context.user_data["reg_type"] = reg_type
            if reg_type == "personal":
                context.user_data["personal_step"] = "name"
                keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
                await query.edit_message_text(
                    f"🌟 *{MESSAGES['personal_name']}* 🌟",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            else:  # company
                context.user_data["register_step"] = "company"
                context.user_data["company_data"] = {}
                keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
                await query.edit_message_text(
                    f"🌟 *{MESSAGES['company_prompt']}* 🌟",
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        elif "ind:" in query.data:
            ind = query.data.split("ind:")[1]
            personal_data = context.user_data["personal_data"]
            if ind == "done":
                context.user_data["personal_step"] = None
                reg_data = {
                    "chat_id": str(query.message.chat_id),
                    "type": "personal",
                    "name": personal_data["Name"],
                    "phone": personal_data["Phone"],
                    "email": personal_data["Email"],
                    "industry": personal_data.get("Industry", ""),
                    "reg_date": datetime.now().isoformat()
                }
                reg_id = f"{reg_data['chat_id']}_{reg_data['reg_date']}"
                context.bot_data["pending_registrations"][reg_id] = reg_data
                manager_text = (
                    f"New Personal Registration Pending Approval:\n"
                    f"Name: {reg_data['name']}\n"
                    f"Phone: {reg_data['phone']}\n"
                    f"Email: {reg_data['email']}\n"
                    f"Industry: {reg_data['industry']}"
                )
                keyboard = [
                    [InlineKeyboardButton("✅ Approve", callback_data=f"approve:{reg_id}"),
                     InlineKeyboardButton("❌ Reject", callback_data=f"reject:{reg_id}")]
                ]
                await context.bot.send_message(MANAGER_CHAT_ID, manager_text, reply_markup=InlineKeyboardMarkup(keyboard))
                users_sheet.append_row([
                    reg_data["chat_id"], reg_data["name"], reg_data["phone"],
                    reg_data["email"], reg_data["industry"], reg_data["reg_date"], "Pending"
                ])
                await query.edit_message_text(
                    f"🌟 *{MESSAGES['registration_submitted']}* 🌟",
                    parse_mode="Markdown")
                del context.user_data["personal_data"]
                del context.user_data["personal_step"]
            else:
                personal_data["Industry"] = ind
                await query.edit_message_text(
                    f"🌟 *Selected: {ind}* 🌟\nSelect more or click Done:",
                    parse_mode="Markdown")
        elif "cat:" in query.data:
            cat = query.data.split("cat:")[1]
            if cat == "suggest":
                context.user_data["suggest_cat"] = True
                keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
                await query.edit_message_text(
                    f"🌟 *{MESSAGES['network_suggest_cat']}* 🌟", 
                    parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            elif cat == "done":
                context.user_data["register_step"] = "public"
                keyboard = [
                    [InlineKeyboardButton("Yes", callback_data="public:yes"),
                     InlineKeyboardButton("No", callback_data="public:no")],
                    [InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]
                ]
                await query.edit_message_text(
                    f"🌟 *{MESSAGES['public_prompt']}* 🌟", 
                    reply_markup=InlineKeyboardMarkup(keyboard), 
                    parse_mode="Markdown")
            else:
                context.user_data["company_data"].setdefault("Categories", []).append(cat)
                await query.edit_message_text(
                    f"🌟 *{MESSAGES['cat_added'].format(cat=cat)}* 🌟", 
                    parse_mode="Markdown")
        elif "public:" in query.data:
            choice = query.data.split("public:")[1]
            context.user_data["company_data"]["PublicEmail"] = "Yes" if choice == "yes" else "No"
            await handle_reply(update, context)
        elif "page:" in query.data:
            parts = query.data.split(":")
            page = int(parts[1])
            category = parts[2] if parts[2] else None
            search = parts[3] if parts[3] else None
            context.bot_data["network_page"][str(query.message.chat_id)] = page
            await network_list(update, context, category, search)
        elif "connect:" in query.data:
            await network_connect(update, context)
        elif "network:" in query.data:
            action = query.data.split("network:")[1]
            handlers = {
                "category": network_category,
                "search": network_search,
                "event": network_event,
                "edit": network_edit,
                "stats": network_stats,
                "manage_cat": network_manage_cat,
                "refer": network_refer
            }
            if action in handlers:
                await handlers[action](update, context)
        elif "rate:" in query.data:
            await network_rate(update, context)
        elif "approve:" in query.data:
            reg_id = query.data.split("approve:")[1]
            if query.from_user.id != int(MANAGER_CHAT_ID):
                await query.edit_message_text("⚠️ Manager access only.", parse_mode="Markdown")
                return
            if reg_id in context.bot_data["pending_registrations"]:
                reg_data = context.bot_data["pending_registrations"].pop(reg_id)
                if reg_data.get("type") == "category":
                    global CATEGORIES
                    CATEGORIES.append(reg_data["category"])
                    await query.edit_message_text(f"✅ Approved: Category {reg_data['category']} added!")
                elif reg_data.get("type") == "personal":
                    user_row = users_sheet.find(reg_data["chat_id"], in_column=1)
                    if user_row:
                        users_sheet.update_cell(user_row.row, 7, "Approved")
                    await query.edit_message_text(f"✅ Approved: {reg_data['name']} added!")
                    await context.bot.send_message(
                        reg_data["chat_id"],
                        f"🌟 *{MESSAGES['registration_approved']}* 🌟",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Main Menu", callback_data="cmd:main_menu")]
                        ])
                    )
                else:  # company
                    company_row = companies_sheet.find(reg_data["chat_id"], in_column=1)
                    if company_row:
                        companies_sheet.update_cell(company_row.row, 10, "Approved")
                    await query.edit_message_text(f"✅ Approved: {reg_data['company']} added!")
                    await context.bot.send_message(
                        reg_data["chat_id"],
                        f"🌟 *{MESSAGES['registration_approved']}* 🌟",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Main Menu", callback_data="cmd:main_menu")]
                        ])
                    )
            else:
                await query.edit_message_text("⚠️ Registration no longer pending.")
        elif "reject:" in query.data:
            reg_id = query.data.split("reject:")[1]
            if query.from_user.id != int(MANAGER_CHAT_ID):
                await query.edit_message_text("⚠️ Manager access only.", parse_mode="Markdown")
                return
            if reg_id in context.bot_data["pending_registrations"]:
                reg_data = context.bot_data["pending_registrations"].pop(reg_id)
                await query.edit_message_text(f"❌ Rejected: {reg_data.get('name', reg_data.get('company', reg_data.get('category')))} not added.")
                if reg_data.get("type") != "category":
                    await context.bot.send_message(
                        reg_data["chat_id"],
                        f"🌟 *{MESSAGES['registration_rejected']}* 🌟",
                        parse_mode="Markdown"
                    )
                    if reg_data["type"] == "personal":
                        user_row = users_sheet.find(reg_data["chat_id"], in_column=1)
                        if user_row:
                            users_sheet.delete_rows(user_row.row)
                    else:
                        company_row = companies_sheet.find(reg_data["chat_id"], in_column=1)
                        if company_row:
                            companies_sheet.delete_rows(company_row.row)
            else:
                await query.edit_message_text("⚠️ Registration no longer pending.")
    except telegram.error.BadRequest as e:
        print(f"Query error: {str(e)}")
        keyboard = [[InlineKeyboardButton("🔙 Back to Start", callback_data="cmd:start_over")]]
        await query.message.reply_text(
            "Sorry, that button timed out. Please try again!", 
            reply_markup=InlineKeyboardMarkup(keyboard))

async def resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
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
    formatted_text = (
        f"🌟 *{MESSAGES['resources_title']}* 🌟\n\n" +
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
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(formatted_text, parse_mode="Markdown", reply_markup=reply_markup, disable_web_page_preview=True)

async def training_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    past_sections = [
        f"🌟 *{t['name']}* _({t['date']})_\n_{t['description']}_"
        for t in PAST_TRAININGS
    ]
    past_text = (
        f"🌟 *{MESSAGES['trainings_past']}* 🌟\n\n" +
        "\n-----\n".join(past_sections)
    )
    upcoming_text = (
        f"✨ *{MESSAGES['trainings_upcoming']}* ✨\n\n" +
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
    context.user_data["signup_step"] = "username"
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await (update.message.reply_text if update.message else update.callback_query.message.reply_text)(
        f"🌟 *Please provide your username for training signup:* 🌟",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    news_items = [
        "🌟 *March 12, 2025*: _Benu secured ETB 2.9M from SWR Ethiopia._",
        "🌟 *April 10, 2025*: _First training held—29 saleswomen trained! See /training_events._",
        "🌟 *May 2025*: _New production line launches._",
        "🌟 *May 15, 2025*: _Networking Event—register at /networking or /training_events._"
    ]
    network_data = network_sheet.get_all_records()
    if network_data:
        latest = max(network_data, key=lambda x: x["RegDate"])
        news_items.append(f"🌟 *New Network Member*: _{latest['Company']} joined on {latest['RegDate']}!_")
    text = (
        f"🌟 *{MESSAGES['news_title']}* 🌟\n\n" +
        "\n".join(news_items)
    )
    keyboard = [
        [InlineKeyboardButton("🔔 Subscribe", callback_data="cmd:subscribenews")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text = (
        f"🌟 *{MESSAGES['contact_info'].split(':')[0]}* 🌟\n\n"
        f"✉️ *Email:* benu@example.com\n"
        f"📞 *Phone:* +251921756683\n"
        f"🏢 *Address:* Addis Ababa, Bole Sub city, Woreda 03, H.N. 4/10/A5/FL8"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def subscribenews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.callback_query.message.chat_id
    query = update.callback_query
    if training_sheet.find(str(chat_id)) is None:
        training_sheet.append_row([str(chat_id), "", "", "", "", datetime.now().isoformat()])
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        f"🌟 *{MESSAGES['subscribed']}* 🌟", 
        parse_mode="Markdown", 
        reply_markup=reply_markup
    )

async def learn_startup_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    network_data = network_sheet.get_all_records()
    chat_id = query.message.chat_id
    entry = next((e for e in network_data if e["ChatID"] == str(chat_id)), None)
    suggestions = []
    if entry:
        categories = entry["Categories"].split(",")
        for module in TRAINING_MODULES:
            if any(cat.lower() in module["name"].lower() for cat in categories):
                suggestions.append(module)
    keyboard = [
        [InlineKeyboardButton(f"📚 {m['name']}", callback_data=f"module:{m['id']}")]
        for m in (suggestions or TRAINING_MODULES)
    ]
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cmd:main_menu")])
    await query.message.reply_text(
        f"🌟 *{MESSAGES['modules_title']}* 🌟", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode="Markdown"
    )

async def update_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = str(query.message.chat_id)
    user_row = users_sheet.find(chat_id, in_column=1)
    company_row = companies_sheet.find(chat_id, in_column=1)
    if user_row:
        context.user_data["reg_type"] = "personal"
        context.user_data["personal_step"] = "name"
        context.user_data["edit_mode"] = True
        row = users_sheet.row_values(user_row.row)
        context.user_data["personal_data"] = {
            "Name": row[1],
            "Phone": row[2],
            "Email": row[3],
            "Industry": row[4]
        }
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
        await query.edit_message_text(
            f"🌟 *{MESSAGES['personal_name']}* 🌟\nCurrent: {row[1]}",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif company_row:
        context.user_data["reg_type"] = "company"
        context.user_data["register_step"] = "company"
        context.user_data["edit_mode"] = True
        row = companies_sheet.row_values(company_row.row)
        context.user_data["company_data"] = {
            "Company": row[1],
            "Phone": row[2],
            "Email": row[3],
            "Description": row[4],
            "Manager": row[5],
            "Categories": row[6].split(",") if row[6] else [],
            "PublicEmail": row[8],
            "Status": row[9]
        }
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
        await query.edit_message_text(
            f"🌟 *{MESSAGES['company_prompt']}* 🌟\nCurrent: {row[1]}",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.edit_message_text("⚠️ No profile found. Please register first.", parse_mode="Markdown")

async def all_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data.clear()
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
        await app.bot.send_message(
            chat_id, 
            f"🌟 Reminder: *{name}* training on _{date}_ is in 7 days! Reply /training_events for details.", 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

def main():
    app = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()
    init_bot_data(app)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signup", signup))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply))
    app.add_handler(CallbackQueryHandler(button))
    schedule_notifications(app)
    port = int(os.environ.get("PORT", 8080))
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="/bot",
        webhook_url=f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/bot"
    )
    print("Bot is running on Render...")

if __name__ == "__main__":
    main()