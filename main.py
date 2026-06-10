import asyncio
import re
import os
from datetime import datetime, time
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
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo, InputMediaAudio, InputMediaDocument, InputMediaAnimation
from pyrogram.errors import FloodWait, MessageNotModified
from config import API_ID, API_HASH, BOT_TOKEN, STRING_SESSION, ADMINS, LOG_CHANNEL
from database import (
    add_channel, remove_channel, get_channels,
    get_scheduler_settings, update_scheduler_settings,
    add_to_queue, get_queue_count, pop_queue_batch
)

# Clients
bot = Client("BananaBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_bot = None
if STRING_SESSION:
    user_bot = Client("BananaUser", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION, in_memory=True)

BOT_LINK_RE = re.compile(r"(?:https?://)?t\.me/(\w+)\?start=([\w-]+)")
MSG_LINK_RE = re.compile(r"https?://t\.me/(?:c/)?([\w-]+)/(\d+)")

# Relaxed pattern to match t.me links that may contain newlines/whitespace inside the username or start parameter.
BOT_LINK_RE_RELAXED = re.compile(
    r"(?:https?://\s*)?t\s*\.\s*m\s*e\s*/\s*([\w\s]+)\s*\?\s*s\s*t\s*a\s*r\s*t\s*=\s*([\w\s-]+)",
    re.IGNORECASE
)

def extract_bot_links(text):
    if not text:
        return []
    results = []
    pos = 0
    while True:
        idx = text.lower().find("t.me", pos)
        if idx == -1:
            break
        
        match_start = idx
        if match_start >= 8 and text[match_start-8:match_start].lower() == "https://":
            match_start -= 8
        elif match_start >= 7 and text[match_start-7:match_start].lower() == "http://":
            match_start -= 7
            
        scan_idx = idx + 4
        # Consume '/' with optional whitespace
        while scan_idx < len(text) and text[scan_idx].isspace():
            scan_idx += 1
        if scan_idx < len(text) and text[scan_idx] == '/':
            scan_idx += 1
        else:
            pos = idx + 4
            continue
            
        while scan_idx < len(text) and text[scan_idx].isspace():
            scan_idx += 1
            
        username_chars = []
        raw_username_span_end = scan_idx
        while scan_idx < len(text):
            char = text[scan_idx]
            if char.isalnum() or char == '_':
                username_chars.append(char)
                scan_idx += 1
                raw_username_span_end = scan_idx
            elif char.isspace():
                scan_idx += 1
            else:
                break
                
        username = "".join(username_chars)
        if not username:
            pos = idx + 4
            continue
            
        scan_idx = raw_username_span_end
        while scan_idx < len(text) and text[scan_idx].isspace():
            scan_idx += 1
            
        if scan_idx >= len(text) or text[scan_idx] != '?':
            pos = idx + 4
            continue
        scan_idx += 1
        
        while scan_idx < len(text) and text[scan_idx].isspace():
            scan_idx += 1
            
        if scan_idx + 5 <= len(text) and text[scan_idx:scan_idx+5].lower() == "start":
            scan_idx += 5
        else:
            pos = idx + 4
            continue
            
        while scan_idx < len(text) and text[scan_idx].isspace():
            scan_idx += 1
            
        if scan_idx >= len(text) or text[scan_idx] != '=':
            pos = idx + 4
            continue
        scan_idx += 1
        
        while scan_idx < len(text) and text[scan_idx].isspace():
            scan_idx += 1
            
        start_chars = []
        raw_start_span_end = scan_idx
        while scan_idx < len(text):
            char = text[scan_idx]
            if char.isalnum() or char in ['_', '-']:
                start_chars.append(char)
                scan_idx += 1
                raw_start_span_end = scan_idx
            elif char.isspace():
                peek_idx = scan_idx
                has_more_param_chars = False
                newlines_count = 0
                while peek_idx < len(text):
                    peek_char = text[peek_idx]
                    if peek_char == '\n':
                        newlines_count += 1
                    if newlines_count >= 2:
                        break
                    if peek_char.isalnum() or peek_char in ['_', '-']:
                        has_more_param_chars = True
                        break
                    if not peek_char.isspace():
                        break
                    peek_idx += 1
                
                if has_more_param_chars:
                    scan_idx = peek_idx
                else:
                    break
            else:
                break
                
        start_param = "".join(start_chars)
        if not start_param:
            pos = idx + 4
            continue
            
        raw_match = text[match_start:raw_start_span_end]
        results.append((raw_match, username, start_param))
        pos = raw_start_span_end
        
    return results

def _extract_links_from_msg_obj(text_msg):
    """Extract bot links from a single message object's text, caption, entities and buttons."""
    if not text_msg:
        return []
    text = text_msg.text or text_msg.caption or ""
    links = extract_bot_links(text)
    
    entities = text_msg.entities or text_msg.caption_entities or []
    for entity in entities:
        type_str = str(entity.type).lower()
        if "text_link" in type_str and entity.url:
            clean_url = "".join(entity.url.split())
            m = BOT_LINK_RE.search(clean_url)
            if m:
                links.append((entity.url, m.group(1), m.group(2)))
        elif "url" in type_str:
            raw_url = text[entity.offset : entity.offset + entity.length]
            clean_url = "".join(raw_url.split())
            m = BOT_LINK_RE.search(clean_url)
            if m:
                links.append((raw_url, m.group(1), m.group(2)))
                
    if text_msg.reply_markup and text_msg.reply_markup.inline_keyboard:
        for row in text_msg.reply_markup.inline_keyboard:
            for btn in row:
                if btn.url:
                    clean_url = "".join(btn.url.split())
                    m = BOT_LINK_RE.search(clean_url)
                    if m:
                        links.append((btn.url, m.group(1), m.group(2)))
    return links

def get_all_bot_links(text_msg):
    """Get all bot links from message, including quoted/replied-to message content."""
    if not text_msg:
        return []
    
    links = _extract_links_from_msg_obj(text_msg)
    
    # Also check reply_to_message (the blue 'quote' block in Telegram)
    # The link may live inside the quoted/replied message rather than the main text
    replied = getattr(text_msg, 'reply_to_message', None)
    if replied:
        links.extend(_extract_links_from_msg_obj(replied))
    
    # Also check quote field (newer Pyrogram versions expose this separately)
    quote = getattr(text_msg, 'quote', None)
    if quote:
        quote_text = getattr(quote, 'text', '') or ''
        if quote_text:
            links.extend(extract_bot_links(quote_text))
        for entity in (getattr(quote, 'entities', None) or []):
            type_str = str(entity.type).lower()
            if "text_link" in type_str and entity.url:
                clean_url = "".join(entity.url.split())
                m = BOT_LINK_RE.search(clean_url)
                if m:
                    links.append((entity.url, m.group(1), m.group(2)))
                    
    unique_links = []
    seen = set()
    for raw_match, bot_username, start_param in links:
        key = (raw_match, bot_username.lower(), start_param)
        if key not in seen:
            seen.add(key)
            unique_links.append((raw_match, bot_username, start_param))
            
    return unique_links

user_settings = {}
user_states = {} 

# GLOBAL LOCK to prevent overlapping interactions
interaction_lock = asyncio.Lock()

@bot.on_message(filters.command("start") & filters.private & filters.user(ADMINS))
async def start_cmd(client, message):
    await message.reply_text(
        "<b>🍌 Banana Bot (Strict Lock)</b>\n\n"
        "• /set_bot @BotName\n"
        "• /add - Forward a msg from target channel\n"
        "• /del [id] - Remove a channel\n"
        "• /channels - List target channels\n"
        "• /check [link]\n"
        "• /search [query]\n"
        "• /fetch - Fetch files by forwarding a range (first & last msg)\n"
        "• /scheduler - Manage scheduler settings\n"
        "• /queue - View scheduled posts queue\n"
        "• /q - Add ready-made posts directly to queue\n"
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

@bot.on_message(filters.command("fetch") & filters.user(ADMINS))
async def fetch_range_cmd(client, message):
    user_states[message.from_user.id] = {"state": "AWAITING_FIRST_MSG"}
    await message.reply_text("Forward the **first message** of the range from the target channel/chat.")

@bot.on_message(filters.forwarded & filters.private & filters.user(ADMINS))
async def handle_forward(client, message):
    user_id = message.from_user.id
    state_info = user_states.get(user_id)
    
    if state_info and state_info.get("state") == "AWAITING_FIRST_MSG":
        if not message.forward_from_chat:
            return await message.reply_text("❌ Could not detect the original chat. Make sure it's a channel or group message.")
        
        chat_id = message.forward_from_chat.id
        msg_id = message.forward_from_message_id
        
        import time
        user_states[user_id] = {
            "state": "AWAITING_LAST_MSG",
            "chat_id": chat_id,
            "first_msg_id": msg_id,
            "time": time.time()
        }
        await message.reply_text(
            f"✅ First message received.\n"
            f"• Chat: <code>{chat_id}</code>\n"
            f"• Msg ID: <code>{msg_id}</code>\n\n"
            f"Now forward the **last message** of the range from the same chat."
        )
        return

    elif state_info and state_info.get("state") == "AWAITING_Q_MSG":
        user_states.pop(user_id, None)
        status_msg = await message.reply_text("⏳ Storing post to LOG_CHANNEL and queueing...")
        sent_msg = await robust_copy(bot, LOG_CHANNEL, message)
        if sent_msg:
            await add_to_queue(sent_msg.id)
            await status_msg.edit("✅ Successfully added your ready-made post to the scheduler queue!")
        else:
            await status_msg.edit("❌ Failed to save post to LOG_CHANNEL.")
        return

    elif state_info and state_info.get("state") == "AWAITING_LAST_MSG":
        import time
        elapsed = time.time() - state_info.get("time", 0)
        if elapsed < 2.0:
            return
            
        if not message.forward_from_chat:
            return await message.reply_text("❌ Could not detect the original chat.")
        
        chat_id = message.forward_from_chat.id
        msg_id = message.forward_from_message_id
        
        if chat_id != state_info["chat_id"]:
            return await message.reply_text("❌ The last message must be from the same chat as the first message. Please try again or use /fetch to restart.")
        
        first_msg_id = state_info["first_msg_id"]
        # Clear state
        user_states.pop(user_id, None)
        
        status_msg = await message.reply_text("⏳ Processing range...")
        
        # Ensure we have user_bot
        if not user_bot:
            return await status_msg.edit("❌ STRING_SESSION missing!")
        
        settings = user_settings.get(user_id)
        if not settings:
            return await status_msg.edit("❌ Pehle `/set_bot` karein.")
        
        fs_bot = settings["file_store_bot"]
        
        # Determine start/end range
        start_id = min(first_msg_id, msg_id)
        end_id = max(first_msg_id, msg_id)
        
        # Fetch files in range
        try:
            try:
                await user_bot.join_chat(chat_id)
                print(f"DEBUG JOIN: Successfully joined or already in chat {chat_id}")
            except Exception as je:
                print(f"DEBUG JOIN: Could not join chat {chat_id}: {je}")
                
            all_messages = []
            processed_media_groups = set()
            total_ids = list(range(start_id, end_id + 1))
            chunk_size = 100
            print(f"DEBUG FETCH: Range start_id={start_id}, end_id={end_id}, total_ids={len(total_ids)}")
            for i in range(0, len(total_ids), chunk_size):
                chunk = total_ids[i:i + chunk_size]
                msgs = await user_bot.get_messages(chat_id, chunk)
                if not isinstance(msgs, list):
                    msgs = [msgs]
                import json
                try:
                    debug_data = []
                    for m in msgs:
                        if m:
                            try:
                                debug_data.append(json.loads(str(m)))
                            except Exception as je:
                                debug_data.append({"id": getattr(m, "id", None), "error": str(je)})
                    with open("debug_messages.json", "w", encoding="utf-8") as df:
                        json.dump(debug_data, df, indent=4, ensure_ascii=False)
                    print("DEBUG: Saved fetched chunk messages to debug_messages.json")
                except Exception as ex:
                    print(f"DEBUG: Failed to write debug_messages.json: {ex}")
                print(f"DEBUG FETCH: Chunk starting {chunk[0]} returned {len(msgs)} messages.")
                for m in msgs:
                    if m:
                        print(f"DEBUG FETCH: Msg ID={m.id}, empty={getattr(m, 'empty', None)}")
                        if not m.empty:
                            text_val = m.text or m.caption or ""
                            rtm = getattr(m, 'reply_to_message', None)
                            quote = getattr(m, 'quote', None)
                            fwd_text = ""
                            if hasattr(m, 'forward_from_chat') and m.forward_from_chat:
                                fwd_text = "(has forward_from_chat)"
                            print(f"DEBUG FETCH FIELDS: "
                                  f"text={repr(text_val[:80]) if text_val else 'EMPTY'} | "
                                  f"reply_to_message={'YES text='+repr((rtm.text or rtm.caption or '')[:60]) if rtm else 'NONE'} | "
                                  f"quote={'YES text='+repr(getattr(quote,'text','')[:60]) if quote else 'NONE'} | "
                                  f"fwd={fwd_text} | "
                                  f"links_found={get_all_bot_links(m)}")
                        if m.media_group_id:
                            if m.media_group_id in processed_media_groups:
                                continue
                            processed_media_groups.add(m.media_group_id)
                            try:
                                group_msgs = await user_bot.get_media_group(chat_id, m.id)
                                print(f"DEBUG MEDIA GROUP: fetched {len(group_msgs)} messages for ID {m.id}")
                                for gm in group_msgs:
                                    gm_text = gm.text or gm.caption or ""
                                    gm_rtm = getattr(gm, 'reply_to_message', None)
                                    gm_quote = getattr(gm, 'quote', None)
                                    print(f"DEBUG MEDIA GROUP MSG: ID={gm.id} | "
                                          f"text={repr(gm_text[:60]) if gm_text else 'EMPTY'} | "
                                          f"reply_to={'YES text='+repr((gm_rtm.text or gm_rtm.caption or '')[:50]) if gm_rtm else 'NONE'} | "
                                          f"quote={'YES text='+repr(getattr(gm_quote,'text','')[:50]) if gm_quote else 'NONE'} | "
                                          f"links={get_all_bot_links(gm)}")
                            except Exception as e:
                                print(f"DEBUG: Failed to get media group {m.media_group_id}: {e}")
                                group_msgs = [m]
                            
                            has_links = False
                            for gm in group_msgs:
                                if get_all_bot_links(gm):
                                    has_links = True
                                    break
                            
                            if has_links:
                                all_messages.append(group_msgs)
                        else:
                            if get_all_bot_links(m):
                                all_messages.append(m)
            
            total = len(all_messages)
            if total == 0:
                return await status_msg.edit("❌ No posts with file links found in the specified range.")
            
            await status_msg.edit(f"✅ Found {total} posts. Processing sequentially...")
            
            success_count = 0
            skip_count = 0
            async with interaction_lock:
                for i, msg in enumerate(all_messages, 1):
                    msg_id_display = msg[0].id if isinstance(msg, list) else msg.id
                    await status_msg.edit(
                        f"⏳ <b>Processing:</b> [{i}/{total}]\n"
                        f"<b>Msg ID:</b> <code>{msg_id_display}</code>\n"
                        f"<b>✅ Success:</b> {success_count} | <b>❌ Skipped:</b> {skip_count}"
                    )
                    res = await process_single_post(status_msg, chat_id, msg, fs_bot, i, total)
                    if res: success_count += 1
                    else: skip_count += 1
                    await asyncio.sleep(1)
            
            await status_msg.edit(f"🏁 <b>Done!</b>\nTotal: {total}\nSuccess: {success_count}\nSkipped: {skip_count}")
        except Exception as e:
            await status_msg.edit(f"❌ Error while fetching/processing: {e}")
        return

    # default behavior (add channel)
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
    is_media_group = isinstance(msg, list)
    if is_media_group:
        text_msg = None
        for m in msg:
            if m.text or m.caption:
                text_msg = m
                break
        if not text_msg:
            # Check reply_to_message for any group member
            for m in msg:
                if getattr(m, 'reply_to_message', None):
                    replied = m.reply_to_message
                    if replied.text or replied.caption:
                        text_msg = m
                        break
        if not text_msg:
            text_msg = msg[0]
    else:
        text_msg = msg

    links = get_all_bot_links(text_msg)
    if not links:
        print(f"DEBUG: No links found in post {index} (including reply_to_message).")
        return False

    # Determine where the text lives - main message or reply_to_message
    main_text = text_msg.text or text_msg.caption or ""
    replied_msg = getattr(text_msg, 'reply_to_message', None)
    replied_text = (replied_msg.text or replied_msg.caption or "") if replied_msg else ""
    
    # Track where each link was found for correct replacement
    new_text = main_text if main_text else replied_text
    new_reply_markup, processed_any = text_msg.reply_markup, False
    
    for raw_match, bot_username, start_param in links:
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
        if raw_match and raw_match in new_text:
            new_text = new_text.replace(raw_match, new_bot_link.replace("https://", ""))
        elif raw_match and replied_text and raw_match in replied_text:
            # Link is inside the quote/reply - rebuild new_text from replied text
            new_text = replied_text.replace(raw_match, new_bot_link.replace("https://", ""))
        if new_reply_markup:
            for row in new_reply_markup.inline_keyboard:
                for btn in row:
                    if btn.url and raw_match and raw_match in btn.url:
                        btn.url = new_bot_link

    if processed_any:
        try:
            sent_msg = None
            if is_media_group:
                sent_msg = await robust_copy_media_group(user_bot, LOG_CHANNEL, msg, caption=new_text, reply_markup=new_reply_markup)
            else:
                if msg.text or (not msg.text and not msg.caption and not any([msg.photo, msg.video, msg.document, msg.audio])):
                    sent_msg = await bot.send_message(LOG_CHANNEL, new_text, reply_markup=new_reply_markup)
                else: 
                    sent_msg = await robust_copy(user_bot, LOG_CHANNEL, msg, caption=new_text, reply_markup=new_reply_markup)
            
            if sent_msg:
                await add_to_queue(sent_msg.id)
                print(f"DEBUG: Success for post index {index}. Added to scheduler queue.")
            try:
                if is_media_group:
                    await user_bot.edit_message_caption(ch_id, text_msg.id, new_text, reply_markup=new_reply_markup)
                else:
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

class ProgressTracker:
    def __init__(self, action="Progress"):
        self.action = action
        self.last_percent = -1
        
    async def __call__(self, current, total):
        if total == 0 or total is None:
            return
        percent = int((current / total) * 10) * 10
        if percent != self.last_percent:
            self.last_percent = percent
            print(f"DEBUG: {self.action}: {percent}% ({current}/{total} bytes)")

async def robust_copy(client, chat_id, msg, caption=None, reply_markup=None):
    """Tries to copy a message; if restricted, downloads and uploads it."""
    try:
        return await msg.copy(chat_id, caption=caption, reply_markup=reply_markup)
    except Exception as e:
        print(f"DEBUG: Copy failed ({e}). Falling back to download/upload...")
        try:
            # Download the media with progress tracking
            dl_tracker = ProgressTracker("Downloading")
            file_path = await client.download_media(msg, progress=dl_tracker)
            if not file_path:
                print("DEBUG: Download failed (returned None).")
                return None
            
            # Use provided caption/markup or fall back to msg defaults
            final_caption = caption if caption is not None else (msg.caption or "")
            final_markup = reply_markup if reply_markup is not None else msg.reply_markup
            
            print(f"DEBUG: Starting upload to {chat_id}...")
            ul_tracker = ProgressTracker("Uploading")
            if msg.document:
                res = await client.send_document(chat_id, file_path, caption=final_caption, reply_markup=final_markup, progress=ul_tracker)
            elif msg.video:
                res = await client.send_video(chat_id, file_path, caption=final_caption, reply_markup=final_markup, progress=ul_tracker)
            elif msg.audio:
                res = await client.send_audio(chat_id, file_path, caption=final_caption, reply_markup=final_markup, progress=ul_tracker)
            elif msg.photo:
                res = await client.send_photo(chat_id, file_path, caption=final_caption, reply_markup=final_markup, progress=ul_tracker)
            elif msg.voice:
                res = await client.send_voice(chat_id, file_path, caption=final_caption, reply_markup=final_markup, progress=ul_tracker)
            elif msg.video_note:
                res = await client.send_video_note(chat_id, file_path, reply_markup=final_markup, progress=ul_tracker)
            elif msg.animation:
                res = await client.send_animation(chat_id, file_path, caption=final_caption, reply_markup=final_markup, progress=ul_tracker)
            elif msg.sticker:
                res = await client.send_sticker(chat_id, file_path, reply_markup=final_markup, progress=ul_tracker)
            else:
                res = await client.send_document(chat_id, file_path, caption=final_caption, reply_markup=final_markup, progress=ul_tracker)
            
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
            print("DEBUG: Upload completed successfully.")
            return res
        except Exception as err:
            print(f"DEBUG: Fallback failed: {err}")
            return None

async def robust_copy_media_group(client, chat_id, messages, caption=None, reply_markup=None):
    """Tries to copy a media group; if restricted, downloads and uploads it."""
    caption_index = 0
    for idx, m in enumerate(messages):
        if m.caption or m.text:
            caption_index = idx
            break
            
    try:
        captions = ["" for _ in messages]
        if caption is not None:
            captions[caption_index] = caption
        else:
            for idx, m in enumerate(messages):
                captions[idx] = m.caption or ""
        
        copied_msgs = await client.copy_media_group(
            chat_id=chat_id,
            from_chat_id=messages[0].chat.id,
            message_id=messages[0].id,
            captions=captions
        )
        if copied_msgs:
            return copied_msgs[caption_index] if len(copied_msgs) > caption_index else copied_msgs[0]
    except Exception as e:
        print(f"DEBUG: copy_media_group failed ({e}). Falling back to download/upload media group...")
        
    file_paths = []
    try:
        media_items = []
        for idx, m in enumerate(messages):
            dl_tracker = ProgressTracker(f"Downloading media group item {idx+1}")
            file_path = await client.download_media(m, progress=dl_tracker)
            if not file_path:
                print(f"DEBUG: Failed to download media group item {idx+1}")
                for path in file_paths:
                    if os.path.exists(path):
                        os.remove(path)
                return None
            file_paths.append(file_path)
            
            item_caption = caption if idx == caption_index else ""
            
            if m.photo:
                media_items.append(InputMediaPhoto(file_path, caption=item_caption))
            elif m.video:
                media_items.append(InputMediaVideo(file_path, caption=item_caption))
            elif m.audio:
                media_items.append(InputMediaAudio(file_path, caption=item_caption))
            elif m.animation:
                media_items.append(InputMediaAnimation(file_path, caption=item_caption))
            else:
                media_items.append(InputMediaDocument(file_path, caption=item_caption))
                
        print(f"DEBUG: Uploading media group with {len(media_items)} items...")
        sent_msgs = await client.send_media_group(chat_id, media_items)
        if sent_msgs:
            return sent_msgs[caption_index] if len(sent_msgs) > caption_index else sent_msgs[0]
    except Exception as err:
        print(f"DEBUG: Media group fallback failed: {err}")
    finally:
        for path in file_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print(f"DEBUG: Error cleaning up file {path}: {e}")
                
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
                    found = extract_bot_links(text)
                    if found:
                        _, bot_username, start_param = found[0]
                        return f"https://t.me/{bot_username}?start={start_param}"
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
                        found = extract_bot_links(text)
                        if found:
                            _, bot_username, start_param = found[0]
                            return f"https://t.me/{bot_username}?start={start_param}"
    except Exception as e:
        print(f"Error in get_batch: {e}")
    return None

@bot.on_message(filters.command("scheduler") & filters.user(ADMINS))
async def scheduler_menu_cmd(client, message):
    settings = await get_scheduler_settings()
    text, markup = get_scheduler_menu_content(settings)
    await message.reply_text(text, reply_markup=markup)

def get_scheduler_menu_content(settings):
    status = "🟢 Active" if settings["active"] else "🔴 Inactive"
    target = settings["target_channel"] or "Not Set"
    batch_size = settings["batch_size"]
    times_str = ", ".join(settings["times"]) or "None"
    
    # Days map
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    days_str = ", ".join([day_names[d] for d in settings["days"]]) or "None"
    
    text = (
        f"📅 **Banana Scheduler Settings**\n\n"
        f"• **Status**: {status}\n"
        f"• **Target Channel**: <code>{target}</code>\n"
        f"• **Batch Size**: `{batch_size}` posts\n"
        f"• **Posting Times**: `{times_str}`\n"
        f"• **Posting Days**: `{days_str}`\n"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("Toggle Status", callback_data="sched_toggle"),
            InlineKeyboardButton("Set Target Channel", callback_data="sched_set_chan")
        ],
        [
            InlineKeyboardButton("Set Batch Size", callback_data="sched_set_batch"),
            InlineKeyboardButton("Set Times", callback_data="sched_set_times")
        ],
        [
            InlineKeyboardButton("Set Days", callback_data="sched_set_days"),
            InlineKeyboardButton("Trigger Now", callback_data="sched_trigger_now")
        ]
    ]
    return text, InlineKeyboardMarkup(keyboard)

@bot.on_message(filters.command("queue") & filters.user(ADMINS))
async def queue_cmd(client, message):
    count = await get_queue_count()
    text = f"📦 **Scheduler Queue**\n\nTotal posts waiting in queue: `{count}`"
    keyboard = [
        [
            InlineKeyboardButton("Post 1 Batch Now", callback_data="sched_trigger_now"),
            InlineKeyboardButton("Clear Queue", callback_data="sched_clear_queue")
        ]
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@bot.on_message(filters.command("q") & filters.user(ADMINS))
async def q_cmd_handler(client, message):
    user_states[message.from_user.id] = {"state": "AWAITING_Q_MSG"}
    await message.reply_text("Forward the ready-made post (or send the text) you want to add directly to the scheduler queue.")

@bot.on_message(filters.text & filters.private & filters.user(ADMINS))
async def handle_admin_text(client, message):
    if message.text.startswith("/"):
        return
    user_id = message.from_user.id
    state_info = user_states.get(user_id)
    if not state_info:
        return
        
    state = state_info.get("state")
    if state == "AWAITING_Q_MSG":
        user_states.pop(user_id, None)
        status_msg = await message.reply_text("⏳ Storing post to LOG_CHANNEL and queueing...")
        sent_msg = await bot.send_message(LOG_CHANNEL, message.text, reply_markup=message.reply_markup)
        if sent_msg:
            await add_to_queue(sent_msg.id)
            await status_msg.edit("✅ Successfully added your ready-made post to the scheduler queue!")
        else:
            await status_msg.edit("❌ Failed to save post to LOG_CHANNEL.")
        return

    elif state == "SET_CHAN":
        chan = message.text.strip()
        settings = await get_scheduler_settings()
        settings["target_channel"] = chan
        await update_scheduler_settings(settings)
        user_states.pop(user_id, None)
        await message.reply_text(f"✅ Target channel updated to `{chan}`.")
        
    elif state == "SET_BATCH":
        try:
            batch = int(message.text.strip())
            settings = await get_scheduler_settings()
            settings["batch_size"] = batch
            await update_scheduler_settings(settings)
            user_states.pop(user_id, None)
            await message.reply_text(f"✅ Batch size updated to `{batch}`.")
        except ValueError:
            await message.reply_text("❌ Invalid number. Please enter an integer.")
            
    elif state == "SET_TIMES":
        times = [t.strip() for t in message.text.split(",") if t.strip()]
        valid = []
        for t in times:
            if re.match(r"^\d{2}:\d{2}$", t):
                valid.append(t)
        if not valid:
            return await message.reply_text("❌ No valid times found. Format should be: `09:00, 18:00`.")
        
        settings = await get_scheduler_settings()
        settings["times"] = valid
        await update_scheduler_settings(settings)
        user_states.pop(user_id, None)
        await message.reply_text(f"✅ Posting times updated to: `{', '.join(valid)}`.")
        
    elif state == "SET_DAYS":
        try:
            days = [int(d.strip()) for d in message.text.split(",") if d.strip()]
            valid = [d for d in days if 0 <= d <= 6]
            if not valid:
                return await message.reply_text("❌ No valid days found. Enter numbers 0-6 separated by commas.")
            
            settings = await get_scheduler_settings()
            settings["days"] = sorted(list(set(valid)))
            await update_scheduler_settings(settings)
            user_states.pop(user_id, None)
            await message.reply_text(f"✅ Posting days updated.")
        except ValueError:
            await message.reply_text("❌ Invalid format. Use numbers 0 to 6 separated by commas.")

@bot.on_callback_query(filters.user(ADMINS))
async def handle_callbacks(client, query):
    data = query.data
    user_id = query.from_user.id
    
    if data == "sched_toggle":
        settings = await get_scheduler_settings()
        settings["active"] = not settings["active"]
        await update_scheduler_settings(settings)
        text, markup = get_scheduler_menu_content(settings)
        await query.message.edit_text(text, reply_markup=markup)
        
    elif data == "sched_set_chan":
        user_states[user_id] = {"state": "SET_CHAN"}
        await query.message.reply_text("Please send the target channel ID or username (e.g. `@mychannel` or `-100xxxxxxx`).")
        await query.answer()
        
    elif data == "sched_set_batch":
        user_states[user_id] = {"state": "SET_BATCH"}
        await query.message.reply_text("Please send the batch size (number of posts) to send in each interval.")
        await query.answer()
        
    elif data == "sched_set_times":
        user_states[user_id] = {"state": "SET_TIMES"}
        await query.message.reply_text("Please send the posting times separated by commas (e.g. `09:00, 18:00, 21:00`).")
        await query.answer()
        
    elif data == "sched_set_days":
        user_states[user_id] = {"state": "SET_DAYS"}
        await query.message.reply_text(
            "Please send the posting days as numbers separated by commas:\n"
            "• `0` = Monday\n• `1` = Tuesday\n• `2` = Wednesday\n• `3` = Thursday\n• `4` = Friday\n• `5` = Saturday\n• `6` = Sunday\n\n"
            "For everyday send: `0,1,2,3,4,5,6`"
        )
        await query.answer()
        
    elif data == "sched_trigger_now":
        await query.answer("Triggering scheduler batch run...")
        run_res = await trigger_scheduler_batch()
        await query.message.reply_text(run_res)
        
    elif data == "sched_clear_queue":
        from database import queue_col
        await queue_col.delete_many({})
        await query.message.edit_text("✅ Queue cleared successfully.")
        await query.answer()

async def trigger_scheduler_batch():
    settings = await get_scheduler_settings()
    if not settings["target_channel"]:
        return "❌ Error: Target channel not set in scheduler settings."
    
    msg_ids = await pop_queue_batch(settings["batch_size"])
    if not msg_ids:
        return "ℹ️ Queue is empty. No posts to send."
    
    success = 0
    for mid in msg_ids:
        try:
            msg = await bot.get_messages(LOG_CHANNEL, mid)
            if msg and not msg.empty:
                if msg.media_group_id:
                    try:
                        group_msgs = await bot.get_media_group(LOG_CHANNEL, msg.id)
                    except Exception as e:
                        print(f"DEBUG: Failed to get media group {msg.media_group_id} from LOG: {e}")
                        group_msgs = [msg]
                    copied = await robust_copy_media_group(bot, settings["target_channel"], group_msgs)
                else:
                    copied = await robust_copy(bot, settings["target_channel"], msg)
                if copied:
                    success += 1
                await asyncio.sleep(2)
        except Exception as e:
            print(f"Error posting scheduled msg {mid}: {e}")
            
    return f"🏁 **Scheduler Run Completed**\n• Successfully posted: `{success}/{len(msg_ids)}`"

async def scheduler_loop():
    print("Scheduler loop started...")
    while True:
        try:
            await asyncio.sleep(60)
            settings = await get_scheduler_settings()
            if not settings["active"] or not settings["target_channel"]:
                continue
                
            now = datetime.now()
            current_day = now.weekday()
            if current_day not in settings["days"]:
                continue
                
            current_time_str = now.strftime("%H:%M")
            if current_time_str in settings["times"]:
                last_run_date = settings.get("last_run_date")
                last_run_time = settings.get("last_run_time")
                today_str = now.strftime("%Y-%m-%d")
                
                if last_run_date == today_str and last_run_time == current_time_str:
                    continue
                    
                print(f"Triggering scheduled posting batch for {current_time_str}...")
                await trigger_scheduler_batch()
                
                settings["last_run_date"] = today_str
                settings["last_run_time"] = current_time_str
                await update_scheduler_settings(settings)
                
        except Exception as e:
            print(f"Error in scheduler loop: {e}")

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
    # Start scheduler loop
    asyncio.create_task(scheduler_loop())
            
    print("Banana Bot Strict Sequential Ready!")
    await idle()

if __name__ == "__main__":
    bot.run(main())
