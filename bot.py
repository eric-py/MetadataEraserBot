from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv
import os
import json

load_dotenv()

TOKEN = os.getenv('TOKEN')
UPLOADFOLDER = os.getenv('UPLOADFOLDER')
FILECONFIG = json.loads(os.getenv('FILECONFIG'))

os.makedirs(UPLOADFOLDER, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    username = update.effective_user.username or "Anonymous"
    await update.message.reply_text(f"Hello, {username}! I'm a metadata eraser bot.")

async def download_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download the file if it meets the criteria."""
    file, file_name, file_type = get_file_info(update.message)
    
    if not file:
        await update.message.reply_text("Please send a file (document, photo, video, or audio).")
        return

    file_size_mb = file.file_size / (1024 * 1024)
    file_type = 'music' if file_type == 'audio' else file_type

    if file_type not in FILECONFIG:
        await update.message.reply_text(f"File type '{file_type}' is not supported.")
        return

    max_size_mb = float(FILECONFIG[file_type])
    if file_size_mb > max_size_mb:
        await update.message.reply_text(f"File size ({file_size_mb:.2f} MB) exceeds the limit of {max_size_mb} MB for {file_type} files.")
        return

    try:
        new_file = await file.get_file()
        file_path = os.path.join(UPLOADFOLDER, file_name)
        await new_file.download_to_drive(file_path)
        await update.message.reply_text("Your File successfully downloaded...")
    except Exception as e:
        await update.message.reply_text("An error occurred while downloading the file. Please try again.")

def get_file_info(message):
    """Extract file information from the message."""
    if message.document:
        mime_type = message.document.mime_type.split('/')[0]
        if mime_type == 'audio':
            return message.document, message.document.file_name, 'music'
        return message.document, message.document.file_name, mime_type
    elif message.photo:
        photo = message.photo[-1]
        return photo, f"photo_{photo.file_id}.jpg", "image"
    elif message.video:
        return message.video, message.video.file_name or f"video_{message.video.file_id}.mp4", "video"
    elif message.audio:
        return message.audio, message.audio.file_name or f"audio_{message.audio.file_id}.mp3", "music"
    return None, None, None

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.ALL, download_file))
    application.run_polling()

if __name__ == '__main__':
    main()