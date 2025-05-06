import os
import json
import requests
import re
from datetime import datetime
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
companies_sheet = sheet.worksheet("Companies")

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

# Categories (Benu-specific)
CATEGORIES = [
    "Biscuit Production", "Grain Processing", "Food Packaging",
    "Agricultural Supply", "Marketing & Sales", "Logistics & Distribution", "Other"
]

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
    "phone_prompt": "Please provide your phone number (Step {step}/{total}):",
    "email_prompt": "Please provide your email (Step {step}/{total}):",
    "company_prompt": "Please provide your company name (Step 1/7):",
    "description_prompt": "Please provide a description of what your company does (Step 4/7):",
    "manager_prompt": "Please provide the manager’s name (Step 5/7):",
    "categories_prompt": "Select categories (Step 6/7, click Done when finished):",
    "public_prompt": "Share email publicly? (Step 7/7, reply Yes/No):",
    "cat_added": "Added {cat}. Select more or click Done:",
    "other_industry": "Please enter your custom industry:",
    "other_category": "Please enter your custom category:",
    "confirm_personal": "Please review your information:\nName: {name}\nPhone: {phone}\nEmail: {email}\nIndustries: {industries}\nIs this correct?",
    "confirm_company": "Please review your information:\nCompany: {company}\nPhone: {phone}\nEmail: {email}\nDescription: {description}\nManager: {manager}\nCategories: {categories}\nPublic Email: {public}\nIs this correct?",
    "modify_prompt": "Which information would you like to modify?",
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
    "registration_submitted": "Approval requested. You’ll be notified soon!",
    "registration_approved": "Your registration has been approved! Welcome!",
    "registration_rejected": "Your registration was not approved. Please contact support."
}

# Bot functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()  # Clear any previous data
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

async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("Personal", callback_data="reg:personal"),
         InlineKeyboardButton("Company", callback_data="reg:company")]
    ]
    await query.edit_message_text(
        "🌟 *Registration cancelled. Start over:* 🌟",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
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
            nav.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page:{page-1}:{category or ''}:{search or otros}"))
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
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
    await query.edit_message_text(
        f"🌟 *{MESSAGES['company_prompt']}* 🌟\nCurrent: {row[1]}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def network_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != int(MANAGER_CHAT_ID):
        await query.edit_message_text("⚠️ Manager access only.", parse_mode="Markdown")
        return
    network_data = network_sheet.get_all_records()
    cat_counts = {cat: 0 for cat in CATEGORIES if cat != "Other"}
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
        context.user_data["company_data"] = {"Categories": []}
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
        personal_data = context.user_data.setdefault("personal_data", {"Industries": []})
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if step == "name":
            personal_data["Name"] = text
            context.user_data["personal_step"] = "phone"
            await update.message.reply_text(
                f"🌟 *{MESSAGES['phone_prompt'].format(step=2, total=4)}* 🌟",
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
                f"🌟 *{MESSAGES['email_prompt'].format(step=3, total=4)}* 🌟",
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
        elif step == "other_industry":
            if text.strip():
                personal_data["Industries"].append(text.strip())
            context.user_data["personal_step"] = "industry"
            keyboard = [[InlineKeyboardButton(cat, callback_data=f"ind:{cat}")] for cat in CATEGORIES]
            keyboard.append([InlineKeyboardButton("Done", callback_data="ind:done")])
            keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")])
            await update.message.reply_text(
                f"🌟 *{MESSAGES['cat_added'].format(cat=text.strip())}* 🌟\nSelect more or click Done:",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif context.user_data.get("register_step"):
        step = context.user_data["register_step"]
        edit_mode = context.user_data.get("edit_mode", False)
        company_data = context.user_data.setdefault("company_data", {"Categories": []})
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        step_count = {"company": 1, "phone": 2, "email": 3, "description": 4, "manager": 5, "categories": 6, "public": 7}
        total_steps = 7
        if step == "company":
            company_data["Company"] = text
            context.user_data["register_step"] = "phone"
            await update.message.reply_text(
                f"🌟 *{MESSAGES['phone_prompt'].format(step=2, total=total_steps)}* 🌟",
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
                f"🌟 *{MESSAGES['email_prompt'].format(step=3, total=total_steps)}* 🌟",
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
            keyboard.append([InlineKeyboardButton("Done", callback_data="cat:done")])
            keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")])
            await update.message.reply_text(
                f"🌟 *{MESSAGES['categories_prompt']}* 🌟", 
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        elif step == "other_category":
            if text.strip():
                company_data["Categories"].append(text.strip())
            context.user_data["register_step"] = "categories"
            keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat:{cat}")] for cat in CATEGORIES]
            keyboard.append([InlineKeyboardButton("Done", callback_data="cat:done")])
            keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")])
            await update.message.reply_text(
                f"🌟 *{MESSAGES['cat_added'].format(cat=text.strip())}* 🌟\nSelect more or click Done:",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        elif step == "public":
            company_data["PublicEmail"] = "Yes" if text.lower() in ["yes", "y"] else "No"
            context.user_data["register_step"] = "confirm"
            keyboard = [
                [InlineKeyboardButton("Done", callback_data="confirm:done"),
                 InlineKeyboardButton("Modify", callback_data="confirm:modify"),
                 InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]
            ]
            await update.message.reply_text(
                MESSAGES["confirm_company"].format(
                    company=company_data["Company"],
                    phone=company_data["Phone"],
                    email=company_data["Email"],
                    description=company_data["Description"],
                    manager=company_data["Manager"],
                    categories=", ".join(company_data["Categories"]),
                    public=company_data["PublicEmail"]
                ),
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
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
 '

System: The error persists because the `global CATEGORIES` declaration in the `button` function's `approve:` handler is still incorrectly placed after the `CATEGORIES.append(reg_data["category"])` operation. Python requires `global` declarations to come before any use of the variable in the function scope. Let’s fix this by ensuring `global CATEGORIES` is declared at the start of the category approval block in the `button` function.

### Fix
We’ll update the `button` function in `bot.py` to move `global CATEGORIES` before the append operation in the `approve:` handler for category approvals. Since this is an update to the existing `bot.py`, we’ll reuse the `artifact_id` (`464bae0e-867e-4379-b630-d81cdfd1367c`). Only the `button` function is modified to keep the response focused.

#### Changes Made
1. In the `button` function, under the `approve:` handler, move `global CATEGORIES` to the start of the category approval block (before `CATEGORIES.append(reg_data["category"])`).
2. Ensure the rest of the function remains unchanged to preserve existing functionality.

#### Commit Message
```
git commit -m "Fix SyntaxError in button approve handler by placing global CATEGORIES before append"
```

#### Updated Code
Below is the corrected `bot.py` with the updated `button` function. The rest of the code is unchanged but included for completeness, as the artifact requires the full file.

<xaiArtifact artifact_id="464bae0e-867e-4379-b630-d81cdfd1367c" artifact_version_id="b04936fe-7579-4425-af0d-9a1ea85d0cb0" title="bot.py" contentType="text/python">
import os
import json
import requests
import re
from datetime import datetime
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
companies_sheet = sheet.worksheet("Companies")

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

# Categories (Benu-specific)
CATEGORIES = [
    "Biscuit Production", "Grain Processing", "Food Packaging",
    "Agricultural Supply", "Marketing & Sales", "Logistics & Distribution", "Other"
]

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
    "phone_prompt": "Please provide your phone number (Step {step}/{total}):",
    "email_prompt": "Please provide your email (Step {step}/{total}):",
    "company_prompt": "Please provide your company name (Step 1/7):",
    "description_prompt": "Please provide a description of what your company does (Step 4/7):",
    "manager_prompt": "Please provide the manager’s name (Step 5/7):",
    "categories_prompt": "Select categories (Step 6/7, click Done when finished):",
    "public_prompt": "Share email publicly? (Step 7/7, reply Yes/No):",
    "cat_added": "Added {cat}. Select more or click Done:",
    "other_industry": "Please enter your custom industry:",
    "other_category": "Please enter your custom category:",
    "confirm_personal": "Please review your information:\nName: {name}\nPhone: {phone}\nEmail: {email}\nIndustries: {industries}\nIs this correct?",
    "confirm_company": "Please review your information:\nCompany: {company}\nPhone: {phone}\nEmail: {email}\nDescription: {description}\nManager: {manager}\nCategories: {categories}\nPublic Email: {public}\nIs this correct?",
    "modify_prompt": "Which information would you like to modify?",
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
    "registration_submitted": "Approval requested. You’ll be notified soon!",
    "registration_approved": "Your registration has been approved! Welcome!",
    "registration_rejected": "Your registration was not approved. Please contact support."
}

# Bot functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()  # Clear any previous data
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

async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("Personal", callback_data="reg:personal"),
         InlineKeyboardButton("Company", callback_data="reg:company")]
    ]
    await query.edit_message_text(
        "🌟 *Registration cancelled. Start over:* 🌟",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
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
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
    await query.edit_message_text(
        f"🌟 *{MESSAGES['company_prompt']}* 🌟\nCurrent: {row[1]}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def network_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != int(MANAGER_CHAT_ID):
        await query.edit_message_text("⚠️ Manager access only.", parse_mode="Markdown")
        return
    network_data = network_sheet.get_all_records()
    cat_counts = {cat: 0 for cat in CATEGORIES if cat != "Other"}
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
        context.user_data["company_data"] = {"Categories": []}
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
        personal_data = context.user_data.setdefault("personal_data", {"Industries": []})
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if step == "name":
            personal_data["Name"] = text
            context.user_data["personal_step"] = "phone"
            await update.message.reply_text(
                f"🌟 *{MESSAGES['phone_prompt'].format(step=2, total=4)}* 🌟",
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
                f"🌟 *{MESSAGES['email_prompt'].format(step=3, total=4)}* 🌟",
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
        elif step == "other_industry":
            if text.strip():
                personal_data["Industries"].append(text.strip())
            context.user_data["personal_step"] = "industry"
            keyboard = [[InlineKeyboardButton(cat, callback_data=f"ind:{cat}")] for cat in CATEGORIES]
            keyboard.append([InlineKeyboardButton("Done", callback_data="ind:done")])
            keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")])
            await update.message.reply_text(
                f"🌟 *{MESSAGES['cat_added'].format(cat=text.strip())}* 🌟\nSelect more or click Done:",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif context.user_data.get("register_step"):
        step = context.user_data["register_step"]
        edit_mode = context.user_data.get("edit_mode", False)
        company_data = context.user_data.setdefault("company_data", {"Categories": []})
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="cmd:cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        step_count = {"company": 1, "phone": 2, "email": 3, "description": 4, "manager": 5, "categories": 6, "public": 7}
        total_steps = 7
        if step == "company":
            company_data["Company"] = text
            context.user_data["register_step"] = "phone"
            await update.message.reply_text(
                f"🌟 *{MESSAGES['phone_prompt'].format(step=2, total=total_steps)}* 🌟",
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
                f"🌟 *{MESSAGES['email_prompt'].format(step=3, total=total_steps)}* 🌟",
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
                f