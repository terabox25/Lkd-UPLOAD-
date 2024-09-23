import csv

import logging

from pymongo import MongoClient

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# Set up logging

logging.basicConfig(

    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',

    level=logging.INFO

)

# Define the Telegram bot token

TOKEN = '7407770383:AAGZXzXXr4qSrS89lp_bpsGURFp7nl9g-5I'

# Admin user ID (the Telegram user ID of the admin)

ADMIN_ID = 768821534  # Replace with the actual admin user ID

# MongoDB setup

client = MongoClient('mongodb+srv://terabox255:Cja5vPiEqfJXvBq7@cluster0.nakwhlt.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')  # Replace with your MongoDB URI

db = client['quiz_bot']

users_collection = db['users']

# Stages for the conversation

UPLOAD_CSV, CHOOSE_DESTINATION, CHOOSE_CHANNEL = range(3)

# Define the function to handle the /start command

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    user_info = users_collection.find_one({'user_id': user_id})

    

    if user_info:

        await update.message.reply_text(

            "Welcome back! ʜɪ ᴛʜᴇʀᴇ!  \n"

            "➻ɪ'ᴍ ʏᴏᴜʀ ᴍᴄQ ʙᴏᴛ. 🤖 \n"

            "➻ᴜᴘʟᴏᴀᴅ ʏᴏᴜʀ ᴄꜱᴠ 📄ꜰɪʟᴇ ᴡɪᴛʜ ᴛʜᴇ ꜰᴏʟʟᴏᴡɪɴɢ ᴄᴏʟᴜᴍɴꜱ: \n"

            "👉Qᴜᴇꜱᴛɪᴏɴ, ᴏᴘᴛɪᴏɴ ᴀ, ᴏᴘᴛɪᴏɴ ʙ, ᴏᴘᴛɪᴏɴ ᴄ, ᴏᴘᴛɪᴏɴ ᴅ, ᴀɴꜱᴡᴇʀ, ᴅᴇꜱᴄʀɪᴘᴛɪᴏɴ.\n"

            "Use Command: -🔰 /uploadcsv."

            "➻ ɪ'ʟʟ ᴄᴏɴᴠᴇʀᴛ ɪᴛ ɪɴᴛᴏ ᴍᴜʟᴛɪᴘʟᴇ-ᴄʜᴏɪᴄᴇ Qᴜᴇꜱᴛɪᴏɴꜱ ꜰᴏʀ ʏᴏᴜ! \n"

            "• Mᴀɪɴᴛᴀɪɴᴇʀ: @How_to_Google \n"

        )

    else:

        users_collection.insert_one({'user_id': user_id})

        await update.message.reply_text(

             "Welcome  ʜɪ ᴛʜᴇʀᴇ!  \n"

            "➻ɪ'ᴍ ʏᴏᴜʀ ᴍᴄQ ʙᴏᴛ. 🤖 \n"

            "➻ᴜᴘʟᴏᴀᴅ ʏᴏᴜʀ ᴄꜱᴠ 📄ꜰɪʟᴇ ᴡɪᴛʜ ᴛʜᴇ ꜰᴏʟʟᴏᴡɪɴɢ ᴄᴏʟᴜᴍɴꜱ: \n"

            "👉Qᴜᴇꜱᴛɪᴏɴ, ᴏᴘᴛɪᴏɴ ᴀ, ᴏᴘᴛɪᴏɴ ʙ, ᴏᴘᴛɪᴏɴ ᴄ, ᴏᴘᴛɪᴏɴ ᴅ, ᴀɴꜱᴡᴇʀ, ᴅᴇꜱᴄʀɪᴘᴛɪᴏɴ.\n"

            "Use Command: -🔰 /uploadcsv."

            "➻ ɪ'ʟʟ ᴄᴏɴᴠᴇʀᴛ ɪᴛ ɪɴᴛᴏ ᴍᴜʟᴛɪᴘʟᴇ-ᴄʜᴏɪᴄᴇ Qᴜᴇꜱᴛɪᴏɴꜱ ꜰᴏʀ ʏᴏᴜ! \n"

            "• Mᴀɪɴᴛᴀɪɴᴇʀ: @How_to_Google \n"


        )

# Start the CSV upload process

async def upload_csv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    user_info = users_collection.find_one({'user_id': user_id})

    

    if user_info or user_id == ADMIN_ID:

        await update.message.reply_text(
        
         "📂 ᴛᴏ ᴜᴘʟᴏᴀᴅ ʏᴏᴜʀ ᴄꜱᴠ ꜰɪʟᴇ ꜰᴏʀ ᴍᴄQ ᴄᴏɴᴠᴇʀꜱɪᴏɴ, ᴘʟᴇᴀꜱᴇ ᴇɴꜱᴜʀᴇ ɪᴛ ᴍᴇᴇᴛꜱ ᴛʜᴇ ꜰᴏʟʟᴏᴡɪɴɢ ʀᴇQᴜɪʀᴇᴍᴇɴᴛꜱ:  \n"
    "👉 ꜰᴏʀᴍᴀᴛ: \"Question\", \"Option A\", \"Option B\", \"Option C\", \"Option D\", \"Answer\", \"Description\".  \n"
    "👉 ᴛʜᴇ \"ᴀɴꜱᴡᴇʀ\" ꜱʜᴏᴜʟᴅ ʙᴇ ɪɴ ᴀ, ʙ, ᴄ, ᴅ ꜰᴏʀᴍᴀᴛ.  \n"
    "👉 ᴛʜᴇ \"ᴅᴇꜱᴄʀɪᴘᴛɪᴏɴ\" ɪꜱ ᴏᴘᴛɪᴏɴᴀʟ. ɪꜰ ɴᴏᴛ ᴘʀᴏᴠɪᴅᴇᴅ, ɪᴛ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ꜰɪʟʟᴇᴅ.  \n"
    "ᴇxᴀᴍᴘʟᴇ ᴄꜱᴠ ꜰᴏʀᴍᴀᴛ: \n"
    "[Download Example CSV](https://t.me/How_To_Google/10) \n"
            
        )

        return UPLOAD_CSV

    else:

        await update.message.reply_text("You are not authorized to use this bot. Please contact the admin.")

        return ConversationHandler.END

# Handle CSV file upload

async def handle_csv_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id == ADMIN_ID or users_collection.find_one({'user_id': user_id}):
        file = await update.message.document.get_file()
        file_path = f"{file.file_id}.csv"
        await file.download_to_drive(file_path)

        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            questions = list(reader)

        context.user_data['questions'] = questions

        keyboard = [
            [InlineKeyboardButton("Bot", callback_data='bot')],
            [InlineKeyboardButton("Channel", callback_data='channel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Do you want to upload these quizzes to the bot or forward them to a channel?",
            reply_markup=reply_markup
        )

        return CHOOSE_DESTINATION

    else:
        await update.message.reply_text("You are not authorized to use this bot. Please contact the admin.")
        return ConversationHandler.END

#yha se hendler add krna hai 

async def choose_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    choice = query.data

    if choice == 'bot':
        chat_id = query.message.chat_id
        questions = context.user_data.get('questions', [])
        await send_all_polls(chat_id, context, questions)
        await query.edit_message_text("Quizzes have been sent to the bot.")
        return ConversationHandler.END

    elif choice == 'channel':
        user_info = users_collection.find_one({'user_id': user_id})
        if 'channels' in user_info and user_info['channels']:
            if len(user_info['channels']) == 1:
                channel_id = user_info['channels'][0]
                questions = context.user_data.get('questions', [])
                await send_all_polls(channel_id, context, questions)
                await query.edit_message_text(f"Quizzes have been sent to {channel_id}.")
                return ConversationHandler.END
            else:
                keyboard = [
                    [InlineKeyboardButton(channel, callback_data=channel) for channel in user_info['channels']]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text("Choose a channel:", reply_markup=reply_markup)
                return CHOOSE_CHANNEL
        else:
            await query.edit_message_text("No channels are set. Please set a channel using /setchannel <channel_id>.")
            return ConversationHandler.END

    else:
        await query.edit_message_text("Invalid choice. Please select 'bot' or 'channel'.")
        return CHOOSE_DESTINATION

async def channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    channel_id = query.data
    questions = context.user_data.get('questions', [])
    await send_all_polls(channel_id, context, questions)
    await query.edit_message_text(text=f"Quizzes have been sent to {channel_id}.")
    return ConversationHandler.END

async def send_all_polls(chat_id, context: ContextTypes.DEFAULT_TYPE, questions):
    answer_mapping = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    max_question_length = 255
    max_option_length = 100
    max_description_length = 200

    for question in questions:
        try:
            text = question.get('Question')
            options = [
                question.get('Option A', ''), 
                question.get('Option B', ''), 
                question.get('Option C', ''), 
                question.get('Option D', '')
            ]
            correct_option = question.get('Answer')
            correct_option_id = answer_mapping.get(correct_option.upper(), None) if correct_option else None
            description = question.get('Description', '')

            # Check for missing data
            missing_data = False
            missing_elements = []

            if not text:
                missing_elements.append("Question")
                missing_data = True

            for index, option in enumerate(options):
                if option == '':
                    missing_elements.append(f"Option {chr(65 + index)}")
                    missing_data = True

            if correct_option is None:
                missing_elements.append("Answer")
                missing_data = True

            if missing_data:
                # Prepare a message showing the MCQ and indicating the missing data
                message_text = f"Question: {text if text else '[Missing]'}\n\n"
                message_text += f"Option A: {options[0] if options[0] else '[Missing]'}\n"
                message_text += f"Option B: {options[1] if options[1] else '[Missing]'}\n"
                message_text += f"Option C: {options[2] if options[2] else '[Missing]'}\n"
                message_text += f"Option D: {options[3] if options[3] else '[Missing]'}\n"
                message_text += f"Answer: {correct_option if correct_option else '[Missing]'}\n"
                message_text += "\nAapne jo MCQ bheja hai usme option ya Answer missing hai. Kripya use sudhar kr punh bheje."
                
                await context.bot.send_message(chat_id=chat_id, text=message_text)
                continue

            # Ensure description contains "@SecondCoaching"
            if '@SecondCoaching' not in description:
                if description:
                    description += ' @SecondCoaching'
                else:
                    description = '@SecondCoaching'

            if (len(text) <= max_question_length and 
                all(len(option) <= max_option_length for option in options) and 
                len(description) <= max_description_length):

                # Send the poll
                await context.bot.send_poll(
                    chat_id=chat_id,
                    question=text,
                    options=options,
                    type='quiz',  # Use 'quiz' for quiz-type polls
                    correct_option_id=correct_option_id,
                    explanation=description,
                    is_anonymous=True  # Set to True to make the quiz anonymous
                )
            else:
                # Send the question and options as a text message
                message_text = f"Question: {text}\n\n"
                message_text += f"Option A: {options[0]}\n"
                message_text += f"Option B: {options[1]}\n"
                message_text += f"Option C: {options[2]}\n"
                message_text += f"Option D: {options[3]}\n"
                if description:
                    message_text += f"\nDescription: {description}"

                await context.bot.send_message(chat_id=chat_id, text=message_text)

                # Send a follow-up quiz
                follow_up_question = "Upr diye gye Question ka Answer kya hoga?👆👆👆👆👆👆👆👆👆"
                follow_up_options = ['A', 'B', 'C', 'D']

                await context.bot.send_poll(
                    chat_id=chat_id,
                    question=follow_up_question,
                    options=follow_up_options,
                    type='quiz',
                    correct_option_id=correct_option_id,
                    is_anonymous=True
                )
        except Exception as e:
            error_message = "Aapne jo CSV file upload ki hai usme kuch gadbadi hai. Kripya use shi karke punh upload kre."
            await context.bot.send_message(chat_id=chat_id, text=error_message)
            continue

    











         



# Command to set the channel ID for a user

async def set_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if user_id == ADMIN_ID:

        try:

            channel_id = context.args[0]

            users_collection.update_one({'user_id': user_id}, {'$addToSet': {'channels': channel_id}})

            await update.message.reply_text(f"Channel ID {channel_id} has been added.")

        except IndexError:

            await update.message.reply_text("Usage: /setchannel <channel_id>")

    else:

        await update.message.reply_text("You are not authorized to use this command.")

# Command to manage channels

async def channels(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if user_id == ADMIN_ID:

        user_info = users_collection.find_one({'user_id': user_id})

        channels = user_info.get('channels', [])

        if not channels:

            await update.message.reply_text("No channels are set. Use /setchannel <channel_id> to add a new channel.")

            return

        

        keyboard = [

            [InlineKeyboardButton(channel, callback_data=f"remove_{channel}") for channel in channels],

            [InlineKeyboardButton("Add new channel", callback_data="add_channel")]

        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Manage your channels:", reply_markup=reply_markup)

    else:

        await update.message.reply_text("You are not authorized to use this command.")

# Handle channel management callbacks

async def channel_management_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    data = query.data

    if data == "add_channel":

        await query.edit_message_text(text="Please use /setchannel <channel_id> to add a new channel.")

    elif data.startswith("remove_"):

        channel_id = data.split("_", 1)[1]

        user_id = update.effective_user.id

        users_collection.update_one({'user_id': user_id}, {'$pull': {'channels': channel_id}})

        await query.edit_message_text(text=f"Channel {channel_id} has been removed.")

# Command to authorize a user

async def authorize(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if user_id == ADMIN_ID:

        try:

            new_user_id = int(context.args[0])

            users_collection.update_one({'user_id': new_user_id}, {'$set': {'authorized': True}}, upsert=True)

            await update.message.reply_text(f"User {new_user_id} has been authorized.")

        except (IndexError, ValueError):

            await update.message.reply_text("Usage: /authorize <user_id>")

    else:

        await update.message.reply_text("You are not authorized to use this command.")

def main():

    application = Application.builder().token(TOKEN).build()

    

    conversation_handler = ConversationHandler(

        entry_points=[CommandHandler("uploadcsv", upload_csv_command)],

        states={

            UPLOAD_CSV: [MessageHandler(filters.Document.FileExtension("csv"), handle_csv_file)],

            CHOOSE_DESTINATION: [CallbackQueryHandler(choose_destination, pattern='^bot|channel$')],
            
            CHOOSE_CHANNEL: [CallbackQueryHandler(channel_callback)]

        },

        fallbacks=[CommandHandler("start", start)]

    )

    

    application.add_handler(conversation_handler)

    application.add_handler(CommandHandler("start", start))

    application.add_handler(CommandHandler("setchannel", set_channel))

    application.add_handler(CommandHandler("channels", channels))

    application.add_handler(CallbackQueryHandler(channel_management_callback, pattern="^remove_|add_channel$"))

    application.add_handler(CommandHandler("authorize", authorize))

    

    application.run_polling()

if __name__ == "__main__":

    main()
