import os
import asyncio
import time
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError, 
    PhoneCodeInvalidError, 
    PhoneNumberInvalidError,
    PhoneCodeExpiredError,
    ChatAdminRequiredError
)
from config import BOT_TOKEN, ADMIN_IDS
import database as db

# Direct safe hardcoded values
API_ID = 24894984 
API_HASH = "4956e23833905463efb588eb806f9804"

# Bot initialization
bot = TelegramClient('bot_main', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

active_transfer_tasks = {}
user_thumbnails = {}
SESSION_STRING_SIZE = 351

print("🚀 Initializing Advanced Telegram File Transfer Bot (v8.0 - Full DB + Sequential + Live MB + Admin)...")

# ================= 1. /start COMMAND =================
@bot.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    user_id = event.sender_id
    user_data = await db.get_user(user_id)
    session_str = await db.get_user_session(user_id)
    
    is_premium = user_data.get("is_premium", False) if user_data else False
    status_str = "🟢 <b>Logged In</b>" if session_str else "🔴 <b>Not Logged In</b>"
    tier_str = "👑 <b>Premium Member</b>" if is_premium else "🆓 <b>Free User</b>"
    
    msg = (
        f"🚀 <b>Advanced Telegram File Transfer Bot (v8.0)</b>\n"
        f"-------------------------------------\n"
        f"👤 <b>Status:</b> {tier_str}\n"
        f"🔑 <b>Session:</b> {status_str}\n\n"
        f"<b>📋 Commands Menu:</b>\n"
        f"• /login - <i>Connect Telegram Account</i>\n"
        f"• /clone - <i>Start Sequential Transfer with Live MB & Cancel Support</i>\n"
        f"• /stop - <i>Stop active transfer</i>\n"
        f"• /kill - <i>Force clear stuck tasks</i>\n"
        f"• /cleanup_cache - <i>Clear temporary cache</i>\n"
        f"• /buy - <i>Get Premium Access</i>\n"
        f"• /logout - <i>Disconnect Account</i>\n"
    )
    if user_id in ADMIN_IDS:
        msg += (
            f"\n👑 <b>Admin Controls:</b>\n"
            f"• /admin_stats - <i>View Statistics</i>\n"
            f"• /addpremium <code>&lt;id&gt;</code> - <i>Grant Premium</i>\n"
            f"• /premiumlist - <i>List All Premium Users</i>\n"
            f"• /checkpremium <code>&lt;id&gt;</code> - <i>Check User Status</i>"
        )

    buttons = [
        [Button.inline("ℹ️ How to use?", data="how_to_use"),
         Button.inline("📊 Bot Stats", data="bot_stats")]
    ]
    await event.respond(msg, buttons=buttons, parse_mode='html')

@bot.on(events.CallbackQuery(pattern=b"how_to_use"))
async def how_to_use_callback(event):
    await event.answer(
        "📖 Guide:\n1. Use /login to link account.\n2. Ensure Bot is Admin in destination channel.\n3. Use /clone to set range & destination (Type /cancel anytime during setup).\n4. Enjoy sequential error-free transfers with Live MB progress!",
        alert=True
    )

@bot.on(events.CallbackQuery(pattern=b"bot_stats"))
async def bot_stats_callback(event):
    total_users = await db.users_collection.count_documents({})
    total_sessions = await db.sessions_collection.count_documents({})
    await event.answer(f"📊 Total Users: {total_users} | Active Sessions: {total_sessions}", alert=True)

@bot.on(events.NewMessage(pattern='/buy'))
async def buy_command(event):
    user_id = event.sender_id
    user = await db.get_user(user_id)
    is_premium = user.get("is_premium", False) if user else False

    if is_premium:
        await event.respond("✨ <b>You are already a Premium Member!</b>", parse_mode='html')
        return

    await event.respond(
        f"💳 <b>Subscription / Buy Access</b>\n"
        f"-------------------------------------\n"
        f"🆔 <b>Your User ID:</b> <code>{user_id}</code>\n\n"
        f"👉 Please send payment proof to Admin and click below:",
        buttons=[[Button.inline("🔔 Notify Admin for Approval", data=f"notify_admin_{user_id}")]],
        parse_mode='html'
    )

@bot.on(events.CallbackQuery(pattern=b"notify_admin_"))
async def notify_admin_callback(event):
    user_id = event.sender_id
    user_entity = await event.get_sender()
    username = f"@{user_entity.username}" if user_entity.username else "No Username"
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🔔 <b>New Premium Request!</b>\n\n"
                f"👤 <b>User:</b> {user_entity.first_name} ({username})\n"
                f"🆔 <b>User ID:</b> <code>{user_id}</code>",
                buttons=[[Button.inline("✅ Approve Premium", data=f"approve_{user_id}")]],
                parse_mode='html'
            )
        except Exception:
            pass
    await event.answer("Request sent to Admin successfully!", alert=True)
    await event.edit("⏳ <b>Request Sent!</b> Please wait for activation.", parse_mode='html')

@bot.on(events.CallbackQuery(pattern=b"approve_"))
async def approve_premium_callback(event):
    if event.sender_id not in ADMIN_IDS:
        await event.answer("Unauthorized!", alert=True)
        return
    target_user_id = int(event.data.decode().split("_")[1])
    await db.users_collection.update_one(
        {"user_id": target_user_id},
        {"$set": {"is_premium": True}},
        upsert=True
    )
    await event.edit(f"✅ <b>Activated Premium for ID:</b> <code>{target_user_id}</code>", parse_mode='html')
    try:
        await bot.send_message(target_user_id, "🎉 <b>Subscription Activated!</b> Use /login to start.", parse_mode='html')
    except Exception:
        pass

@bot.on(events.NewMessage(pattern='/addpremium'))
async def add_premium_command(event):
    if event.sender_id not in ADMIN_IDS:
        return
    parts = event.text.split()
    if len(parts) < 2:
        await event.respond("⚠️ <b>Usage:</b> <code>/addpremium &lt;user_id&gt;</code>", parse_mode='html')
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await event.respond("❌ <b>Invalid User ID format.</b>", parse_mode='html')
        return

    await db.users_collection.update_one({"user_id": target_id}, {"$set": {"is_premium": True}}, upsert=True)
    await event.respond(f"✅ User <code>{target_id}</code> is now a <b>Premium Member</b>.", parse_mode='html')

@bot.on(events.NewMessage(pattern='/checkpremium'))
async def check_premium_command(event):
    if event.sender_id not in ADMIN_IDS:
        return
    parts = event.text.split()
    if len(parts) < 2:
        await event.respond("⚠️ <b>Usage:</b> <code>/checkpremium &lt;user_id&gt;</code>", parse_mode='html')
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await event.respond("❌ <b>Invalid User ID format.</b>", parse_mode='html')
        return

    user = await db.get_user(target_id)
    is_premium = user.get("is_premium", False) if user else False
    status_text = "👑 <b>Active Premium Member</b>" if is_premium else "🆓 <b>Free User / Not Premium</b>"
    
    await event.respond(
        f"🔍 <b>Premium Status Check</b>\n"
        f"-----------------------------\n"
        f"🆔 <b>User ID:</b> <code>{target_id}</code>\n"
        f"📊 <b>Status:</b> {status_text}",
        parse_mode='html'
    )

@bot.on(events.NewMessage(pattern='/premiumlist'))
async def premium_list_command(event):
    if event.sender_id not in ADMIN_IDS:
        return
    premium_users = await db.users_collection.find({"is_premium": True}).to_list(length=100)
    if not premium_users:
        await event.respond("📂 <b>No Premium Users found in database.</b>", parse_mode='html')
        return
    msg = "👑 <b>Active Premium Members List:</b>\n-----------------------------\n"
    for idx, u in enumerate(premium_users, 1):
        uid = u.get("user_id")
        msg += f"{idx}. ID: <code>{uid}</code>\n"
    await event.respond(msg, parse_mode='html')

@bot.on(events.NewMessage(pattern='/admin_stats'))
async def admin_stats_command(event):
    if event.sender_id not in ADMIN_IDS:
        return
    total_users = await db.users_collection.count_documents({})
    total_sessions = await db.sessions_collection.count_documents({})
    total_premium = await db.users_collection.count_documents({"is_premium": True})
    
    await event.respond(
        f"📊 <b>Bot Admin Statistics</b>\n"
        f"-----------------------------\n"
        f"👥 <b>Total Users:</b> <code>{total_users}</code>\n"
        f"👑 <b>Premium Users:</b> <code>{total_premium}</code>\n"
        f"🔑 <b>Active Logged-in Sessions:</b> <code>{total_sessions}</code>\n"
        f"🟢 <b>System Status:</b> Healthy & Online",
        parse_mode='html'
    )

@bot.on(events.NewMessage(pattern='/login'))
async def login_command(event):
    user_id = event.sender_id
    existing = await db.get_user_session(user_id)
    if existing:
        await event.respond("✅ <b>Already Logged In.</b> Use /logout first.", parse_mode='html')
        return
    
    async with bot.conversation(event.chat_id, timeout=300) as conv:
        await conv.send_message("🔐 <b>Login Step 1/3</b>\nSend your Phone Number (e.g., <code>+91XXXXXXXXXX</code>):\n\n<i>Enter /cancel to abort.</i>", parse_mode='html')
        try:
            phone_response = await conv.get_response()
            if phone_response.text.strip() == "/cancel":
                await conv.send_message("❌ Cancelled.", parse_mode='html')
                return
                
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            sent = await client.send_code_request(phone_response.text.strip())
            
            await conv.send_message("📲 Send the OTP received on Telegram:\n\n<i>Enter /cancel to abort.</i>", parse_mode='html')
            otp_response = await conv.get_response()
            if otp_response.text.strip() == "/cancel":
                await client.disconnect()
                await conv.send_message("❌ Cancelled.", parse_mode='html')
                return
                
            try:
                await client.sign_in(phone=phone_response.text.strip(), code=otp_response.text.strip().replace(" ", ""), phone_code_hash=sent.phone_code_hash)
            except SessionPasswordNeededError:
                await conv.send_message("🔑 <b>Two-step verification password required (or type /cancel):</b>", parse_mode='html')
                pwd_response = await conv.get_response()
                if pwd_response.text.strip() == "/cancel":
                    await client.disconnect()
                    await conv.send_message("❌ Cancelled.", parse_mode='html')
                    return
                await client.sign_in(password=pwd_response.text.strip())
                
            string_session = client.session.save()
            await client.disconnect()
            await db.save_user_session(user_id, string_session)
            await conv.send_message("✅ <b>Logged In Successfully!</b>", parse_mode='html')
        except Exception as e:
            await conv.send_message(f"❌ <b>Error:</b> <code>{e}</code>", parse_mode='html')

@bot.on(events.NewMessage(pattern='/logout'))
async def logout_command(event):
    user_id = event.sender_id
    await db.remove_user_session(user_id)
    if user_id in user_thumbnails:
        try:
            os.remove(user_thumbnails[user_id])
        except Exception:
            pass
        del user_thumbnails[user_id]
    await event.respond("🔒 <b>Logged out successfully.</b>", parse_mode='html')

@bot.on(events.NewMessage(pattern='/kill'))
async def kill_command(event):
    user_id = event.sender_id
    if user_id in active_transfer_tasks:
        active_transfer_tasks[user_id].cancel()
        del active_transfer_tasks[user_id]
    await event.respond("⚡ <b>Force Cleared!</b> All tasks terminated.", parse_mode='html')

@bot.on(events.NewMessage(pattern='/cleanup_cache'))
async def cleanup_cache(event):
    await event.respond("🧹 <b>Cache Cleaned!</b>", parse_mode='html')

# ================= 2. CLONE WIZARD (WITH CANCEL SUPPORT) =================
@bot.on(events.NewMessage(pattern='/clone'))
async def clone_command(event):
    user_id = event.sender_id
    session_str = await db.get_user_session(user_id)
    if not session_str:
        await event.respond("❌ <b>Login Required!</b> Use /login first.", parse_mode='html')
        return

    async with bot.conversation(event.chat_id, timeout=300) as conv:
        filename_rule = None
        caption_rule = None
        thumb_path = user_thumbnails.get(user_id)

        try:
            # --- STEP 1: FIRST MESSAGE LINK ---
            while True:
                await conv.send_message(
                    "📍 <b>Step 1/3: Range Selection</b>\n\n"
                    "Send link of the <b>First Message</b>:\n"
                    "Example: <code>https://t.me/c/12345/100</code>\n\n"
                    "<i>Type /cancel to cancel setup.</i>",
                    parse_mode='html'
                )
                resp1 = await conv.get_response()
                text1 = resp1.text.strip()
                if text1 == "/cancel":
                    await conv.send_message("❌ Task Setup Cancelled.", parse_mode='html')
                    return
                try:
                    parts = text1.split("/")
                    c_idx = parts.index("c")
                    source_channel = int("-100" + parts[c_idx + 1])
                    start_msg = int(parts[c_idx + 2])
                    break
                except Exception:
                    await conv.send_message("❌ <b>Invalid link format.</b> Please send a valid link or type /cancel.", parse_mode='html')

            # --- STEP 2: LAST MESSAGE LINK ---
            while True:
                await conv.send_message(
                    f"✅ <b>Start Message:</b> <code>{start_msg}</code>\n\n"
                    f"📍 <b>Step 2/3:</b> Now send link of the <b>Last Message</b>:\n\n"
                    f"<i>Type /cancel to cancel setup.</i>",
                    parse_mode='html'
                )
                resp2 = await conv.get_response()
                text2 = resp2.text.strip()
                if text2 == "/cancel":
                    await conv.send_message("❌ Task Setup Cancelled.", parse_mode='html')
                    return
                try:
                    parts2 = text2.split("/")
                    c_idx2 = parts2.index("c")
                    end_msg = int(parts2[c_idx2 + 2])
                    break
                except Exception:
                    await conv.send_message("❌ <b>Invalid link format.</b> Please send a valid link or type /cancel.", parse_mode='html')

            # --- STEP 3: DESTINATION ID ---
            while True:
                await conv.send_message(
                    f"✅ <b>Range:</b> <code>{start_msg}</code> to <code>{end_msg}</code>\n\n"
                    f"📦 <b>Step 3/3:</b> Send <b>Destination Channel/Group ID</b> (e.g., <code>-100XXXXXXXXXX</code>):\n\n"
                    f"<i>Type /cancel to cancel setup.</i>",
                    parse_mode='html'
                )
                resp3 = await conv.get_response()
                text3 = resp3.text.strip()
                if text3 == "/cancel":
                    await conv.send_message("❌ Task Setup Cancelled.", parse_mode='html')
                    return
                try:
                    destination = int(text3)
                    break
                except Exception:
                    await conv.send_message("❌ <b>Invalid ID format.</b> Please send a valid channel ID number or type /cancel.", parse_mode='html')

            # --- OPTIONS & CONFIRMATION ---
            while True:
                fn_display = f"{filename_rule['old']} ➔ {filename_rule['new']}" if filename_rule else 'None'
                cap_display = f"{caption_rule['old']} ➔ {caption_rule['new']}" if caption_rule else 'None'
                thumb_display = "Custom Set ✅" if thumb_path and os.path.exists(thumb_path) else 'Default'

                buttons = [
                    [Button.inline("📄 Filename Rule", data="rule_filename")],
                    [Button.inline("💬 Caption Rule", data="rule_caption")],
                    [Button.inline("🖼️ Thumbnail", data="rule_thumbnail")],
                    [Button.inline("✅ Confirm & Start Transfer", data="start_transfer_task")],
                    [Button.inline("❌ Cancel", data="cancel_clone")]
                ]
                
                status_msg = await conv.send_message(
                    "⚙️ <b>Setup Summary:</b>\n"
                    "-------------------------------------\n"
                    f"📥 Source: <code>{source_channel}</code>\n"
                    f"📤 Destination: <code>{destination}</code>\n"
                    f"🔢 Range: <code>{start_msg}</code> to <code>{end_msg}</code>\n"
                    f"⚡ Mode: Sequential (100% Order Safe + Live MB + Speed)",
                    buttons=buttons,
                    parse_mode='html'
                )

                click_event = await conv.wait_event(events.CallbackQuery(pattern=b"^(rule_filename|rule_caption|rule_thumbnail|start_transfer_task|cancel_clone)$"), timeout=120)
                action = click_event.data.decode()
                await click_event.answer()

                if action == "cancel_clone":
                    await status_msg.edit("❌ Setup Cancelled.", buttons=None)
                    return
                elif action == "start_transfer_task":
                    if user_id in active_transfer_tasks:
                        active_transfer_tasks[user_id].cancel()
                    
                    active_transfer_tasks[user_id] = asyncio.create_task(
                        sequential_transfer_worker(user_id, source_channel, start_msg, end_msg, destination, filename_rule, caption_rule, thumb_path, status_msg)
                    )
                    return
                elif action == "rule_filename":
                    await status_msg.edit("📄 Send format: <code>OLD | NEW</code>", parse_mode='html')
                    r = await conv.get_response()
                    if "|" in r.text:
                        o, n = r.text.split("|", 1)
                        filename_rule = {"old": o.strip(), "new": n.strip()}
                elif action == "rule_caption":
                    await status_msg.edit("💬 Send format: <code>OLD | NEW</code>", parse_mode='html')
                    r = await conv.get_response()
                    if "|" in r.text:
                        o, n = r.text.split("|", 1)
                        caption_rule = {"old": o.strip(), "new": n.strip()}
                elif action == "rule_thumbnail":
                    await status_msg.edit("🖼️ Send image for thumbnail:", parse_mode='html')
                    r = await conv.get_response()
                    if r.media:
                        os.makedirs("downloads", exist_ok=True)
                        tp = await r.download_media(file="downloads/")
                        if tp:
                            user_thumbnails[user_id] = tp
                            thumb_path = tp
        except Exception as e:
            await conv.send_message(f"❌ Error: {e}", parse_mode='html')

# ================= 3. SEQUENTIAL WORKER WITH LIVE MB & SPEED =================
async def sequential_transfer_worker(user_id, source_channel, start_msg, end_msg, destination_raw, filename_rule, caption_rule, thumbnail_path, status_msg):
    user_client = None
    try:
        session_str = await db.get_user_session(user_id)
        if not session_str:
            await bot.send_message(user_id, "❌ Session expired. Please /login again.", parse_mode='html')
            return
            
        user_client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await user_client.connect()
        destination = await bot.get_input_entity(destination_raw)
        
        total_files = (end_msg - start_msg) + 1
        processed = 0

        for msg_id in range(start_msg, end_msg + 1):
            msg = await user_client.get_messages(source_channel, ids=msg_id)
            if not msg:
                processed += 1
                continue

            caption = msg.text or msg.caption or ""
            if caption_rule and caption_rule["old"] in caption:
                caption = caption.replace(caption_rule["old"], caption_rule["new"])

            if msg.media:
                last_update_time = [time.time()]
                last_bytes = [0]

                async def progress_callback(current_bytes, total_bytes):
                    now = time.time()
                    if now - last_update_time[0] > 1.0 or current_bytes == total_bytes:
                        elapsed = now - last_update_time[0]
                        speed = (current_bytes - last_bytes[0]) / elapsed if elapsed > 0 else 0
                        last_update_time[0] = now
                        last_bytes[0] = current_bytes

                        cur_mb = current_bytes / (1024 * 1024)
                        tot_mb = total_bytes / (1024 * 1024) if total_bytes else 0
                        pct = int((current_bytes / total_bytes) * 100) if total_bytes > 0 else 0
                        
                        speed_str = f"{speed / (1024*1024):.2f} MB/s" if speed > 1024*1024 else f"{speed / 1024:.2f} KB/s"
                        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))

                        status_txt = (
                            f"📥 <b>Downloading File (ID: {msg_id})</b>\n"
                            f"-------------------------------------\n"
                            f"📊 <b>Progress:</b> [{bar}] {pct}%\n"
                            f"💾 <b>Downloaded:</b> <code>{cur_mb:.1f} MB / {tot_mb:.1f} MB</code>\n"
                            f"⚡ <b>Speed:</b> <code>{speed_str}</code>\n"
                            f"📋 <b>Overall:</b> File {processed+1} of {total_files}"
                        )
                        try:
                            await status_msg.edit(status_txt, buttons=[[Button.inline("🛑 Stop Transfer", data="stop_transfer_task")]], parse_mode='html')
                        except Exception:
                            pass

                file_path = await user_client.download_media(msg, file="downloads/", progress_callback=progress_callback)
                if file_path:
                    orig_name = os.path.basename(file_path)
                    new_name = orig_name
                    if filename_rule and filename_rule["old"] in new_name:
                        new_name = new_name.replace(filename_rule["old"], filename_rule["new"])
                        new_path = os.path.join("downloads", new_name)
                        if orig_name != new_name:
                            os.rename(file_path, new_path)
                            file_path = new_path

                    is_vid = msg.video or any(ext in orig_name.lower() for ext in [".mp4", ".mkv", ".mov"])
                    is_aud = msg.audio or any(ext in orig_name.lower() for ext in [".mp3", ".m4a"])
                    is_img = msg.photo or any(ext in orig_name.lower() for ext in [".jpg", ".jpeg", ".png"])

                    try:
                        await status_msg.edit(f"📤 <b>Uploading File ID {msg_id} to destination...</b>", parse_mode='html')
                    except Exception:
                        pass
                    
                    await bot.send_file(
                        destination,
                        file_path,
                        caption=caption if caption else None,
                        thumb=thumbnail_path if (thumbnail_path and os.path.exists(thumbnail_path)) else None,
                        force_document=False if (is_vid or is_aud or is_img) else True,
                        parse_mode='md'
                    )
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
            elif msg.text or caption:
                await bot.send_message(destination, caption if caption else msg.text, parse_mode='md')
            
            processed += 1

        await bot.send_message(user_id, "✅ <b>Sequential Transfer Completed Successfully!</b>", parse_mode='html')
    except asyncio.CancelledError:
        print("Task cancelled.")
    except Exception as e:
        print(f"Error: {e}")
        await bot.send_message(user_id, f"❌ <b>Error:</b> <code>{e}</code>", parse_mode='html')
    finally:
        if user_client and user_client.is_connected():
            await user_client.disconnect()

@bot.on(events.CallbackQuery(data=b"stop_transfer_task"))
async def stop_transfer_callback(event):
    user_id = event.sender_id
    if user_id in active_transfer_tasks:
        active_transfer_tasks[user_id].cancel()
        del active_transfer_tasks[user_id]
    await event.edit("🛑 <b>Transfer Stopped!</b>", parse_mode='html')

@bot.on(events.NewMessage(pattern='/stop'))
async def stop_command(event):
    user_id = event.sender_id
    if user_id in active_transfer_tasks:
        active_transfer_tasks[user_id].cancel()
        del active_transfer_tasks[user_id]
    await event.respond("🛑 <b>Transfer Stopped Successfully!</b>", parse_mode='html')

print("Bot is fully running with Full Database Support, Sequential Order & Live MB...")
bot.run_until_disconnected()
