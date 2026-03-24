from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = "7596059729:AAEmS1oaJLHn51IgUrkV2ggCCgksBmSFjzM"

WEB_APP_URL = "https://your-app.onrender.com/quiz"  
# ⚠️ hosting ke baad yaha apna link daalna

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚀 Play in Mini App",
                web_app=WebAppInfo(url=WEB_APP_URL)
            )
        ]
    ])

    await update.message.reply_text(
        "🔥 Quiz start karo 👇",
        reply_markup=keyboard
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
