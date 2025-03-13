import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Define bot functions
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.first_name
    await update.message.reply_text(
        f"Welcome, {user}! I’m Benu’s Startup Support Bot.\n"
        "Supporting Ethiopian startups in agriculture and food production.\n"
        "Commands:\n"
        "/resources - Guides and tools\n"
        "/training - Training sessions\n"
        "/ask - Ask us anything\n"
        "/network - Connect with startups\n"
        "/news - Latest announcements"
    )

async def resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Resources for Startups:\n"
        "1. High Energy Biscuit Production Guide - Tips on fortification and scaling [Link Soon]\n"
        "2. Market Research Summary - Gaps in Ethiopia’s biscuit supply chain [Link Soon]\n"
        "3. Packaging Design Tips - Quality packaging on a budget [Link Soon]\n"
        "Stay tuned for downloadable files!"
    )

async def training(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Training Opportunities:\n"
        "1. Biscuit Production Basics - Learn fortification and equipment use\n"
        "   - Next Session: April 15, 2025\n"
        "   - Reply /signup to join\n"
        "2. Marketing for Startups - Reach underserved markets\n"
        "   - Next Session: April 20, 2025\n"
        "   - Reply /signup to join\n"
        "More details coming soon!"
    )

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Got a question? Reply with your question, and we’ll get back to you!\n"
        "Example: 'How do I fortify biscuits with vitamins?'"
    )

async def network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Startup Network:\n"
        "1. XYZ Biscuits - Addis Ababa\n"
        "   - Focus: Fortified snacks\n"
        "   - Contact: [Email soon]\n"
        "2. ABC Foods - Oromia\n"
        "   - Focus: Local ingredient sourcing\n"
        "   - Contact: [Email soon]\n"
        "Want to join? Reply /joinnetwork"
    )

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Latest Announcements:\n"
        "1. March 12, 2025: Benu secured ETB 2.9M from SWR Ethiopia to boost high-energy biscuit production.\n"
        "2. April 2025: Market research completed—new insights soon!\n"
        "3. May 2025: New production line launches, doubling capacity.\n"
        "4. Networking Event: May 15, 2025—details via /training.\n"
        "Stay tuned!"
    )

# Handle signup and joinnetwork replies (basic for now)
async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text == "/signup":
        await update.message.reply_text("Thanks for signing up! We’ll confirm your spot soon.")
    elif text == "/joinnetwork":
        await update.message.reply_text("Welcome to the network! We’ll add your startup soon.")

# Set up the bot
def main():
    application = Application.builder().token("7910442120:AAFMUhnwTONoyF1xilwRpjWIRCTmGa0den4").build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("resources", resources))
    application.add_handler(CommandHandler("training", training))
    application.add_handler(CommandHandler("ask", ask))
    application.add_handler(CommandHandler("network", network))
    application.add_handler(CommandHandler("news", news))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply))
    
    # Run with webhook
    port = int(os.environ.get("PORT", 8443))
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="/",
        webhook_url=f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/"
    )
    print("Bot is running on Render...")

if __name__ == "__main__":
    main()