import asyncio
import re
import os
from pyrogram import Client, filters, idle, enums, utils
from pyrogram.enums import ChatType

# --- PATCH FOR LONG IDs ---
# This fixes "ValueError: Peer id invalid" for IDs starting with -1002...
def get_peer_type_patched(peer_id: int) -> str:
    if peer_id < 0:
        if str(peer_id).startswith("-100"):
            return "channel"
        return "chat"
    return "user"

utils.get_peer_type = get_peer_type_patched
# --------------------------
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

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    await message.reply_text(
        "<b>🍌 Banana Bot (Strict Lock)</b>\n\n"
        "• /set_bot @BotName\n"
        "• /add - Forward a msg from target channel\n"
        "• /del [id] - Remove a channel\n"
        "• /channels - List target channels\n"
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

@bot.on_message(filters.command("add") & filters.user(ADMINS))
async def add_channel_cmd(client, message):
    await message.reply_text("Forward a message from the target channel to add it.")

@bot.on_message(filters.forwarded & filters.private & filters.user(ADMINS))
async def handle_forward(client, message):
    if message.forward_from_chat:
        f_chat = message.forward_from_chat
        if f_chat.type not in [ChatType.CHANNEL, ChatType.SUPERGROUP]:
            return await message.reply_text(f"❌ Please forward from a Channel or Supergroup. (Type: {f_chat.type})")
        
        ch_id = f_chat.id
        title = f_chat.title
        await add_channel(ch_id)
        await message.reply_text(f"✅ Channel Added: <b>{title}</b> (<code>{ch_id}</code>)")
    else:
        await message.reply_text("❌ This doesn't seem to be a message forwarded from a channel. Make sure the channel allows forwarding.")

@bot.on_message(filters.command("del") & filters.user(ADMINS))
async def del_channel_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/del -100xxxxxx`")
    try:
        ch_id = int(message.command[1])
        await remove_channel(ch_id)
        await message.reply_text(f"✅ Channel <code>{ch_id}</code> removed.")
    except:
        await message.reply_text("Invalid ID.")

@bot.on_message(filters.command("channels") & filters.user(ADMINS))
async def list_channels_cmd(client, message):
    channels = await get_channels()
    if not channels:
        return await message.reply_text("No target channels added.")
    
    text = "<b>Target Channels:</b>\n\n"
    for ch_id in channels:
        try:
            # Try to get info using user_bot if available, else just show ID
            chat = await user_bot.get_chat(ch_id) if user_bot else None
            if chat:
                text += f"• {chat.title} (<code>{ch_id}</code>)\n"
            else:
                text += f"• <code>{ch_id}</code>\n"
        except:
            text += f"• <code>{ch_id}</code>\n"
    
    await message.reply_text(text)

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
    except Exception as e: await status_msg.edit(f"❌ Error: {e}")

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
            await status_msg.edit(
                f"⏳ <b>Processing:</b> [{i}/{total}]\n"
                f"<b>Channel:</b> <code>{ch_id}</code>\n"
                f"<b>✅ Success:</b> {success_count} | <b>❌ Skipped:</b> {skip_count}"
            )
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
        if new_reply_markup:
            for row in new_reply_markup.inline_keyboard:
                for btn in row:
                    if btn.url and old_link in btn.url: btn.url = new_bot_link

    if processed_any:
        try:
            if msg.text: await bot.send_message(LOG_CHANNEL, new_text, reply_markup=new_reply_markup)
            else: await robust_copy(user_bot, LOG_CHANNEL, msg, caption=new_text, reply_markup=new_reply_markup)
            print(f"DEBUG: Success for post index {index}. Link updated.")
            try:
                if msg.text: await user_bot.edit_message_text(ch_id, msg.id, new_text, reply_markup=new_reply_markup)
                else: await user_bot.edit_message_caption(ch_id, msg.id, new_text, reply_markup=new_reply_markup)
            except Exception as e: 
                print(f"DEBUG: Edit failed: {e}")
            return True
        except Exception as e: 
            print(f"DEBUG: Send failed: {e}")
    else:
        print(f"DEBUG: No links processed for post index {index}.")
    return False

async def collect_files_from_bot(bot_username, start_param):
    files_by_unique_id = {}
    try:
        await user_bot.read_chat_history(bot_username)
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
                if not (msg.document or msg.video or msg.audio):
                    if msg.text:
                        print(f"DEBUG: [{bot_username}] Text received: {msg.text[:60]}...")
                        if "t.me/" in msg.text:
                            print(f"DEBUG: [{bot_username}] Bot sent a link instead of a file. Skipping as requested.")
                    continue

                media = msg.document or msg.video or msg.audio
                unique_id = getattr(media, "file_unique_id", None)
                if unique_id and unique_id not in files_by_unique_id:
                    files_by_unique_id[unique_id] = msg
                    new_found = True
            
            if new_found:
                print(f"DEBUG: Found {len(files_by_unique_id)} files so far...")
                await asyncio.sleep(5) # Wait for remaining files in batch
                async for msg in user_bot.get_chat_history(bot_username, limit=20):
                    if msg.id <= last_id: break
                    media = msg.document or msg.video or msg.audio
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

async def robust_copy(client, chat_id, msg, caption=None, reply_markup=None):
    """Tries to copy a message; if restricted, downloads and uploads it."""
    try:
        return await msg.copy(chat_id, caption=caption, reply_markup=reply_markup)
    except Exception as e:
        print(f"DEBUG: Copy failed ({e}). Falling back to download/upload...")
        try:
            # Download the media
            file_path = await client.download_media(msg)
            if not file_path:
                return None
            
            # Use provided caption/markup or fall back to msg defaults
            final_caption = caption if caption is not None else (msg.caption or "")
            final_markup = reply_markup if reply_markup is not None else msg.reply_markup
            
            if msg.document:
                res = await client.send_document(chat_id, file_path, caption=final_caption, reply_markup=final_markup)
            elif msg.video:
                res = await client.send_video(chat_id, file_path, caption=final_caption, reply_markup=final_markup)
            elif msg.audio:
                res = await client.send_audio(chat_id, file_path, caption=final_caption, reply_markup=final_markup)
            elif msg.photo:
                res = await client.send_photo(chat_id, file_path, caption=final_caption, reply_markup=final_markup)
            elif msg.voice:
                res = await client.send_voice(chat_id, file_path, caption=final_caption, reply_markup=final_markup)
            elif msg.video_note:
                res = await client.send_video_note(chat_id, file_path, reply_markup=final_markup)
            elif msg.animation:
                res = await client.send_animation(chat_id, file_path, caption=final_caption, reply_markup=final_markup)
            elif msg.sticker:
                res = await client.send_sticker(chat_id, file_path, reply_markup=final_markup)
            else:
                # Fallback for unknown media types
                res = await client.send_document(chat_id, file_path, caption=final_caption, reply_markup=final_markup)
            
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
            return res
        except Exception as err:
            print(f"DEBUG: Fallback failed: {err}")
            return None

async def get_link_with_command(fs_bot_username, media_msg):
    try:
        await user_bot.read_chat_history(fs_bot_username)
        last_id = 0
        async for m in user_bot.get_chat_history(fs_bot_username, limit=1):
            last_id = m.id

        sent = await robust_copy(user_bot, fs_bot_username, media_msg)
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
            lf = await robust_copy(user_bot, LOG_CHANNEL, f)
            if lf: log_files.append(lf)
            await asyncio.sleep(3)
        
        if not log_files: return None
        
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
    if user_bot: 
        await user_bot.start()
        # Warm up peer cache so the bot recognizes channels it's in
        # This prevents "KeyError: ID not found" on Railway restarts
        print("Warming up user_bot cache...")
        try:
            async for _ in user_bot.get_dialogs(limit=100):
                pass
        except Exception as e:
            print(f"Cache warmup warning: {e}")
            
    print("Banana Bot Strict Sequential Ready!")
    await idle()

if __name__ == "__main__":
    bot.run(main())
