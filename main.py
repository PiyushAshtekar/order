import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackContext, CommandHandler, CallbackQueryHandler

# Replace with the actual URL where you will host your mini_app.html
MINI_APP_URL = "https://order-rhgz.onrender.com"

async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Open Mini App", web_app={"url": MINI_APP_URL})]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Click the button to open the Mini App!", reply_markup=reply_markup)

async def web_app_callback(update: Update, context: CallbackContext):
    if update.callback_query and update.callback_query.web_app_data:
        web_app_data = update.callback_query.web_app_data.data
        try:
            data = json.loads(web_app_data)
            product = data.get("product")
            price = data.get("price")
            user_id = data.get("user_id")
            await update.callback_query.answer("Data received successfully!")
            await update.callback_query.message.reply_text(
                f"Received data from Mini App:\nProduct: {product}\nPrice: ${price}\nUser ID: {user_id}"
            )
        except json.JSONDecodeError:
            await update.callback_query.answer("Received non-JSON data!")
            await update.callback_query.message.reply_text(f"Received raw data: {web_app_data}")
    else:
        await update.callback_query.answer("No data received from Mini App.")

def main():
    application = ApplicationBuilder().token("7231225101:AAHd6slHljb2RTH89cyZdfrQwUHC7DZJ93M").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(web_app_callback))

    application.run_polling()

if __name__ == '__main__':
    main()