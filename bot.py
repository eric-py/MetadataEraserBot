from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.error import TimedOut, NetworkError
from dotenv import load_dotenv
import os
import json
from PIL import Image
from moviepy.editor import VideoFileClip
import asyncio
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
from mutagen.mp3 import MP3

load_dotenv()

TOKEN = os.getenv('TOKEN')
UPLOADFOLDER = os.getenv('UPLOADFOLDER')
FILECONFIG = json.loads(os.getenv('FILECONFIG'))

os.makedirs(UPLOADFOLDER, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.effective_user.username or "Anonymous"
    await update.message.reply_text(f"Hello, {username}! I'm a metadata eraser bot.")

async def download_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    file, file_name, file_type = get_file_info(update.message)
    
    if not file:
        await update.message.reply_text("Please send a file (document, photo, video, or audio).")
        return

    file_size_mb = file.file_size / (1024 * 1024)
    file_type = 'music' if file_type == 'audio' else file_type

    if file_type not in FILECONFIG or file_size_mb > float(FILECONFIG[file_type]):
        await update.message.reply_text(f"File type '{file_type}' is not supported or file size exceeds the limit.")
        return

    try:
        new_file = await file.get_file()
        file_path = os.path.join(UPLOADFOLDER, file_name)
        await new_file.download_to_drive(file_path)
        
        processing_message = await update.message.reply_text("Processing your file. This may take a few moments...\n\n[          ] 0%")
        
        async def update_progress(percentage):
            progress = int(percentage / 10)
            bar = "█" * progress + " " * (10 - progress)
            await processing_message.edit_text(f"Processing your file. This may take a few moments...\n\n[{bar}] {percentage}%")

        if file_type in ['image', 'video', 'music']:
            await process_and_send_file(update, file_path, file_type, update_progress)
        else:
            await update.message.reply_text("Unsupported file type for processing.")
            os.remove(file_path)

        await processing_message.delete()
    except (TimedOut, NetworkError):
        await update.message.reply_text("Network error occurred. Please try again later.")
    except Exception as e:
        await update.message.reply_text("An error occurred. Please try again later.")
        print(f"Error: {str(e)}")
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

def get_file_info(message):
    if message.document:
        mime_type = message.document.mime_type.split('/')[0]
        return message.document, message.document.file_name, 'music' if mime_type == 'audio' else mime_type
    elif message.photo:
        photo = message.photo[-1]
        return photo, f"photo_{photo.file_id}.jpg", "image"
    elif message.video:
        return message.video, message.video.file_name or f"video_{message.video.file_id}.mp4", "video"
    elif message.audio:
        return message.audio, message.audio.file_name or f"audio_{message.audio.file_id}.mp3", "music"
    return None, None, None

async def process_and_send_file(update: Update, file_path: str, file_type: str, progress_callback):
    processed_file_path = file_path
    try:
        if file_type == 'image':
            img = Image.open(file_path)
            data = list(img.getdata())
            image_without_exif = Image.new(img.mode, img.size)
            image_without_exif.putdata(data)
            processed_file_path = f"{file_path}_processed.jpg"
            image_without_exif.save(processed_file_path)
            await progress_callback(50)

        elif file_type == 'video':
            clip = VideoFileClip(file_path)
            processed_file_path = f"{file_path}_processed.mp4"
            clip.write_videofile(processed_file_path, codec='libx264', audio_codec='aac', temp_audiofile='temp-audio.m4a', remove_temp=True)
            clip.close()
            await progress_callback(50)

        elif file_type == 'music':
            processed_file_path = f"{file_path}_processed.mp3"
            audio = MP3(file_path, ID3=ID3)
            audio.delete()
            audio.save()

            if update.message.caption:
                parts = update.message.caption.split(',', 1)
                audio = EasyID3(file_path)
                if len(parts) > 0:
                    audio['title'] = parts[0].strip()
                if len(parts) > 1:
                    audio['artist'] = parts[1].strip()
                audio.save()

            os.rename(file_path, processed_file_path)
            await progress_callback(50)

        with open(processed_file_path, 'rb') as file:
            await update.message.reply_document(
                document=file,
                filename=os.path.basename(processed_file_path),
                read_timeout=300,
                write_timeout=300,
                connect_timeout=60
            )

        await progress_callback(100)
        await update.message.reply_text("File processed and sent successfully. Metadata has been removed or updated as requested.")
    except Exception as e:
        await update.message.reply_text("An error occurred while processing the file. Please try again later.")
        print(f"Error details: {str(e)}")
    finally:
        if os.path.exists(processed_file_path):
            os.remove(processed_file_path)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document_limit = FILECONFIG.get('document')
    image_limit = FILECONFIG.get('image')
    video_limit = FILECONFIG.get('video')
    music_limit = FILECONFIG.get('music')

    help_text = f"""
🤖 MetadataEraserBot Help 🤖

This bot helps you remove metadata from your files. Here's how to use it:

1. Send any supported file type (document, image, video, audio) to the bot.
2. The bot will process the file and remove its metadata.
3. You'll receive the processed file back, free of metadata.

Supported file types and size limits:
• Documents: Up to {document_limit} MB
• Images (JPEG, PNG): Up to {image_limit} MB
• Videos (MP4): Up to {video_limit} MB
• Audio (MP3): Up to {music_limit} MB

🎵 To send music files:
   - You can add a caption in the format "Title, Artist" to set these metadata fields.
   - Example: "Title, Artist"
   - If you don't add a caption, all metadata will be removed.


Commands:
/start - Start the bot
/help - Show this help message

    """
    await update.message.reply_text(help_text)

def main() -> None:
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.ALL, download_file))
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()