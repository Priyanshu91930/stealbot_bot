import asyncio
import re
import os
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageNotModified
from config import API_ID, API_HASH, BOT_TOKEN, STRING_SESSION, ADMINS, LOG_CHANNEL
from database import add_channel, remove_channel, get_channels

# Clients
bot = Client("BananaBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_bot = None
if STRING_SESSION:
    user_bot = Client("BananaUser", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION, in_memory=True)

BOT_LINK_RE = re.compile(r"(?:https?://)?t\.me/(\w+)\?start=([\w-]+)")
MSG_LINK_RE = re.compile(r"https?://t\.me/(?:c/)?([\w-]+)/(\d+)")
user_settings = {} 

# GLOBAL LOCK to prevent overlapping interactions
interaction_lock = asyncio.Lock()

async def smart_copy(client, message, chat_id, caption=None, reply_markup=None):
    """
    Tries to copy a message. If it fails (e.g., restricted content), 
    it downloads the media and uploads it manually.
    """
    try:
        return await message.copy(chat_id, caption=caption, reply_markup=reply_markup)
    except Exception as e:
        print(f"DEBUG: Copy failed ({e}), attempting download/upload...")
        if message.text:
            return await client.send_message(chat_id, text=caption or message.text, reply_markup=reply_markup)
        
        # Download media
        file_path = await client.download_media(message)
        if not file_path:
            return None
            
        try:
            cap = caption if caption is not None else (message.caption or "")
            if message.document:
                return await client.send_document(chat_id, file_path, caption=cap, reply_markup=reply_markup)
            elif message.video:
                return await client.send_video(chat_id, file_path, caption=cap, reply_markup=reply_markup)
            elif message.audio:
                return await client.send_audio(chat_id, file_path, caption=cap, reply_markup=reply_markup)
            elif message.photo:
                return await client.send_photo(chat_id, file_path, caption=cap, reply_markup=reply_markup)
            elif message.animation:
                return await client.send_animation(chat_id, file_path, caption=cap, reply_markup=reply_markup)
            elif message.voice:
                return await client.send_voice(chat_id, file_path, caption=cap, reply_markup=reply_markup)
            elif message.video_note:
                return await client.send_video_note(chat_id, file_path, reply_markup=reply_markup)
            elif message.sticker:
                return await client.send_sticker(chat_id, file_path, reply_markup=reply_markup)
            return None
        except Exception as upload_err:
            print(f"DEBUG: Upload failed: {upload_err}")
            return None
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    await message.reply_text(
        "<b>🍌 Banana Bot (Strict Lock)</b>\n\n"
        "• /set_bot @BotName\n"
        "• /check [link]\n"
        "• /search [query]\n"
        "<i>Processes only one post at a time.</i>"
    )

@bot.on_message(filters.command("set_bot") & filters.user(ADMINS))
async def set_bot_handler(client, message):
    if len(message.command) < 2: return await message.reply_text("Usage: `/set_bot @BotName`")
    bot_username = message.command[1].replace("@", "")
    user_settings[message.from_user.id] = {"file_store_bot": bot_username}
    await message.reply_text(f"✅ FS Bot set to @{bot_username}")

@bot.on_message(filters.command("check") & filters.user(ADMINS))
async def check_link_handler(client, message):
    if not user_bot: return await message.reply_text("STRING_SESSION missing!")
    settings = user_settings.get(message.from_user.id)
    if not settings: return await message.reply_text("❌ Pehle `/set_bot` karein.")
    link = message.command[1]
    match = MSG_LINK_RE.match(link)
    if not match: return await message.reply_text("❌ Invalid link.")
    ch_id, msg_id = match.group(1), int(match.group(2))
    if ch_id.isdigit(): ch_id = int(f"-100{ch_id}")
    status_msg = await message.reply_text("⏳ Processing...")
    try:
        msg = await user_bot.get_messages(ch_id, msg_id)
        # Use LOCK
        async with interaction_lock:
            await process_single_post(status_msg, ch_id, msg, settings["file_store_bot"], 1, 1)
    except Exception as e:
        try: await status_msg.edit(f"❌ Error: {e}")
        except: pass

@bot.on_message(filters.command("search") & filters.user(ADMINS))
async def search_handler(client, message):
    if not user_bot: return await message.reply_text("STRING_SESSION missing!")
    settings = user_settings.get(message.from_user.id)
    if not settings: return await message.reply_text("❌ Pehle `/set_bot` karein.")
    fs_bot = settings["file_store_bot"]
    query = message.text.split(None, 1)[1] if len(message.command) > 1 else None
    if not query: return await message.reply_text("Provide query.")
    
    target_channels = await get_channels()
    status_msg = await message.reply_text(f"🔍 Searching for <code>{query}</code>...")
    
    all_messages = []
    for ch_id in target_channels:
        async for msg in user_bot.search_messages(ch_id, query=query):
            all_messages.append((ch_id, msg))
    
    total = len(all_messages)
    if total == 0: return await status_msg.edit("❌ No posts found.")
    
    await status_msg.edit(f"✅ Found {total} posts. Processing sequentially...")
    
    success_count = 0
    skip_count = 0
    # USE LOCK for the whole loop of posts
    async with interaction_lock:
        for i, (ch_id, msg) in enumerate(all_messages, 1):
            try:
                await status_msg.edit(
                    f"⏳ <b>Processing:</b> [{i}/{total}]\n"
                    f"<b>Channel:</b> <code>{ch_id}</code>\n"
                    f"<b>✅ Success:</b> {success_count} | <b>❌ Skipped:</b> {skip_count}"
                )
            except MessageNotModified:
                pass
            except Exception as e:
                print(f"DEBUG: Status edit failed: {e}")

            res = await process_single_post(status_msg, ch_id, msg, fs_bot, i, total)
            if res: success_count += 1
            else: skip_count += 1
            await asyncio.sleep(1) # Small buffer between posts

    await status_msg.edit(f"🏁 <b>Done!</b>\nTotal: {total}\nSuccess: {success_count}\nSkipped: {skip_count}")

async def process_single_post(status_msg, ch_id, msg, fs_bot, index, total):
    text = msg.text or msg.caption or ""
    links = BOT_LINK_RE.findall(text)
    if msg.reply_markup and msg.reply_markup.inline_keyboard:
        for row in msg.reply_markup.inline_keyboard:
            for btn in row:
                if btn.url: links.extend(BOT_LINK_RE.findall(btn.url))
    if not links: return False
    
    new_text, new_reply_markup, processed_any = text, msg.reply_markup, False
    for bot_username, start_param in set(links):
        files = await collect_files_from_bot(bot_username, start_param)
        if not files: 
            print(f"DEBUG: No files found for {bot_username} in post {index}. Skipping link.")
            continue
        
        new_bot_link = None
        if len(files) == 1: 
            print(f"DEBUG: 1 file found for {bot_username}. Using /link")
            new_bot_link = await get_link_with_command(fs_bot, files[0])
        else: 
            print(f"DEBUG: {len(files)} files found for {bot_username}. Using /batch")
            new_bot_link = await get_batch_link(fs_bot, files)
        
        if not new_bot_link: 
            print(f"DEBUG: Failed to get new link for {bot_username}")
            continue
        
        processed_any = True
        old_link = f"t.me/{bot_username}?start={start_param}"
        new_text = new_text.replace(old_link, new_bot_link.replace("https://", ""))
        if new_reply_markup and hasattr(new_reply_markup, "inline_keyboard"):
            for row in new_reply_markup.inline_keyboard:
                for btn in row:
                    if btn.url and old_link in btn.url: 
                        btn.url = new_bot_link

    if processed_any:
        try:
            # Check if text/caption actually changed or reply_markup changed
            # (In a real scenario, you'd compare new_text with text and new_reply_markup with msg.reply_markup)
            
            if msg.text: 
                await bot.send_message(LOG_CHANNEL, new_text, reply_markup=new_reply_markup)
            else: 
                await smart_copy(user_bot, msg, LOG_CHANNEL, caption=new_text, reply_markup=new_reply_markup)
            
            print(f"DEBUG: Success for post index {index}. Link updated.")
            
            try:
                if msg.text:
                    if new_text != text or new_reply_markup != msg.reply_markup:
                        await user_bot.edit_message_text(ch_id, msg.id, new_text, reply_markup=new_reply_markup)
                else:
                    if new_text != text or new_reply_markup != msg.reply_markup:
                        await user_bot.edit_message_caption(ch_id, msg.id, new_text, reply_markup=new_reply_markup)
            except MessageNotModified:
                print(f"DEBUG: Post {index} already has the updated link. Skipping edit.")
            except Exception as e: 
                print(f"DEBUG: Edit failed for post {index}: {e}")
            return True
        except Exception as e: 
            print(f"DEBUG: Send to LOG_CHANNEL failed: {e}")
    else:
        print(f"DEBUG: No links processed for post index {index}.")
    return False

async def collect_files_from_bot(bot_username, start_param):
    files_by_unique_id = {}
    try:
        try:
            await user_bot.read_chat_history(bot_username)
        except Exception as e:
            print(f"DEBUG: Could not read history for {bot_username}: {e}")
        
        last_id = 0
        async for m in user_bot.get_chat_history(bot_username, limit=1):
            last_id = m.id
        
        await user_bot.send_message(bot_username, f"/start {start_param}")
        
        # Wait for files to appear
        for i in range(12): 
            await asyncio.sleep(3)
            new_found = False
            async for msg in user_bot.get_chat_history(bot_username, limit=20):
                if msg.id <= last_id: break
                
                # Ignore self messages
                if msg.from_user and msg.from_user.is_self: continue

                # Log bot text responses for debugging
                media = msg.document or msg.video or msg.audio or msg.voice or msg.video_note or msg.photo
                if not media:
                    if msg.text:
                        print(f"DEBUG: [{bot_username}] Text received: {msg.text[:60]}...")
                        if "t.me/" in msg.text:
                            print(f"DEBUG: [{bot_username}] Bot sent a link instead of a file. Skipping as requested.")
                    continue

                unique_id = getattr(media, "file_unique_id", None)
                if unique_id and unique_id not in files_by_unique_id:
                    files_by_unique_id[unique_id] = msg
                    new_found = True
            
            if new_found:
                print(f"DEBUG: Found {len(files_by_unique_id)} files so far...")
                await asyncio.sleep(5) # Wait for remaining files in batch
                async for msg in user_bot.get_chat_history(bot_username, limit=30):
                    if msg.id <= last_id: break
                    media = msg.document or msg.video or msg.audio or msg.voice or msg.video_note or msg.photo
                    if media:
                        unique_id = getattr(media, "file_unique_id", None)
                        if unique_id and unique_id not in files_by_unique_id:
                            files_by_unique_id[unique_id] = msg
                break
            if i % 4 == 0: print(f"DEBUG: Waiting for files from {bot_username}...")
    except FloodWait as e:
        print(f"DEBUG: FloodWait for {e.value}s")
        await asyncio.sleep(e.value)
    except Exception as e:
        print(f"DEBUG: Error in collect_files: {e}")
    return sorted(files_by_unique_id.values(), key=lambda x: x.id)

async def get_link_with_command(fs_bot_username, media_msg):
    try:
        await user_bot.read_chat_history(fs_bot_username)
        last_id = 0
        async for m in user_bot.get_chat_history(fs_bot_username, limit=1):
            last_id = m.id

        sent = await smart_copy(user_bot, media_msg, fs_bot_username)
        if not sent: return None
        await asyncio.sleep(3)
        await sent.reply("/link")
        
        for _ in range(10):
            await asyncio.sleep(4)
            async for msg in user_bot.get_chat_history(fs_bot_username, limit=10):
                if msg.id <= last_id: break
                if msg.from_user and msg.from_user.username and msg.from_user.username.lower() == fs_bot_username.lower():
                    text = msg.text or msg.caption or ""
                    found = BOT_LINK_RE.search(text)
                    if found: return f"https://t.me/{found.group(1)}?start={found.group(2)}"
    except Exception as e:
        print(f"Error in get_link: {e}")
    return None

async def get_batch_link(fs_bot_username, files):
    try:
        await user_bot.read_chat_history(fs_bot_username)
        last_id = 0
        async for m in user_bot.get_chat_history(fs_bot_username, limit=1):
            last_id = m.id

        log_files = []
        for f in files:
            lf = await smart_copy(user_bot, f, LOG_CHANNEL)
            if lf: log_files.append(lf)
            await asyncio.sleep(3)
        
        first_file, last_file = log_files[0], log_files[-1]
        await user_bot.send_message(fs_bot_username, "/batch")
        await asyncio.sleep(5)
        await first_file.forward(fs_bot_username)
        await asyncio.sleep(5)
        await last_file.forward(fs_bot_username)
        
        for _ in range(12):
            await asyncio.sleep(5)
            async for msg in user_bot.get_chat_history(fs_bot_username, limit=10):
                if msg.id <= last_id: break
                if msg.from_user and msg.from_user.username and msg.from_user.username.lower() == fs_bot_username.lower():
                    text = msg.text or msg.caption or ""
                    if "t.me/" in text:
                        found = BOT_LINK_RE.search(text)
                        if found: return f"https://t.me/{found.group(1)}?start={found.group(2)}"
    except Exception as e:
        print(f"Error in get_batch: {e}")
    return None

async def main():
    await bot.start()
    if user_bot: await user_bot.start()
    print("Banana Bot Strict Sequential Ready!")
    try:
        await idle()
    finally:
        await bot.stop()
        if user_bot: await user_bot.stop()

if __name__ == "__main__":
    bot.run(main())
