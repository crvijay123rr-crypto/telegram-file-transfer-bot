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

# Direct safe hardcoded values to completely avoid NoneType config errors
API_ID = 24894984
API_HASH = "4956e23833905463efb588eb806f9804"

# Bot initialization
bot = TelegramClient('bot_main', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# In-memory store for active transfer tasks & active thumbnail file paths
active_transfer_tasks = {}
user_thumbnails = {}

SESSION_STRING_SIZE = 351

print("🚀 Initializing Advanced Telegram File Transfer Bot (v5.7 - Clean HTML Format)...")

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
        f"🚀 <b>Advanced Telegram File Transfer Bot (v5.7)</b>\n"
        f"-------------------------------------\n"
        f"👤 <b>Status:</b> {tier_str}\n"
        f"🔑 <b>Session:</b> {status_str}\n\n"
        f"<b>📋 Commands Menu:</b>\n"
        f"• /login - <i>Connect Telegram Account</i>\n"
        f"• /clone - <i>Start File Transfer & Custom Rules</i>\n"
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

# ================= 2. HELP & STATS CALLBACKS =================
@bot.on(events.CallbackQuery(pattern=b"how_to_use"))
async def how_to_use_callback(event):
    await event.answer(
        "📖 Guide:\n1. Use /login to link account.\n2. Ensure Bot is Admin in destination channel.\n3. Use /clone to set range & destination.\n4. Click Start!",
        alert=True
    )

@bot.on(events.CallbackQuery(pattern=b"bot_stats"))
async def bot_stats_callback(event):
    total_users = await db.users_collection.count_documents({})
    total_sessions = await db.sessions_collection.count_documents({})
    await event.answer(f"📊 Total Users: {total_users} | Active Sessions: {total_sessions}", alert=True)

# ================= 3. BUY & ADMIN SYSTEM =================
@bot.on(events.NewMessage(pattern='/buy'))
async def buy_command(event):
    user_id = event.sender_id
    user = await db.get_user(user_id)
    is_premium = user.get("is_premium", False) if user else False

    if is_premium:
        await event.respond("✨ <b>You are already a Premium Member!</b> Enjoy unrestricted file transfers.", parse_mode='html')
        return

    await event.respond(
        f"💳 <b>Subscription / Buy Access</b>\n"
        f"-------------------------------------\n"
        f"🆔 <b>Your User ID:</b> <code>{user_id}</code>\n\n"
        f"👉 Please send your payment screenshot/proof to the Admin, and click the button below to notify instantly.",
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
                f"🆔 <b>User ID:</b> <code>{user_id}</code>\n\n"
                f"Click below to approve:",
                buttons=[[Button.inline("✅ Approve Premium", data=f"approve_{user_id}")]],
                parse_mode='html'
            )
        except Exception as e:
            print(f"Failed to notify admin {admin_id}: {e}")
            
    await event.answer("Request sent to Admin successfully!", alert=True)
    await event.edit("⏳ <b>Request Sent!</b>\nAdmin has been notified. Please wait for activation.", parse_mode='html')

@bot.on(events.CallbackQuery(pattern=b"approve_"))
async def approve_premium_callback(event):
    if event.sender_id not in ADMIN_IDS:
        await event.answer("Unauthorized action!", alert=True)
        return
        
    target_user_id = int(event.data.decode().split("_")[1])
    await db.users_collection.update_one(
        {"user_id": target_user_id},
        {"$set": {"is_premium": True}},
        upsert=True
    )
    await event.edit(f"✅ <b>Successfully activated Premium for User ID:</b> <code>{target_user_id}</code>", parse_mode='html')
    
    try:
        await bot.send_message(
            target_user_id,
            "🎉 <b>Subscription Activated!</b>\nYour account has been upgraded to Premium Member by Admin. Use /login to start transferring.",
            parse_mode='html'
        )
    except Exception as e:
        print(f"Could not message user {target_user_id}: {e}")

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

    await db.users_collection.update_one(
        {"user_id": target_id}, {"$set": {"is_premium": True}}, upsert=True
    )
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

# ================= 4. INTERACTIVE LOGIN & LOGOUT FLOW =================
@bot.on(events.NewMessage(pattern='/login'))
async def login_command(event):
    user_id = event.sender_id
    existing = await db.get_user_session(user_id)
    if existing:
        await event.respond("✅ <b>You Are Already Logged In.</b> First /logout Your Old Session, Then Do Login.", parse_mode='html')
        return
    
    async with bot.conversation(event.chat_id, timeout=300) as conv:
        await conv.send_message(
            "🔐 <b>Login Step 1/3</b>\n\n"
            "Please send your Phone Number in international format (includes country code).\n"
            "Example: <code>+9171828181889</code>\n\n"
            "<i>Enter /cancel to cancel the process.</i>",
            parse_mode='html'
        )
        
        try:
            phone_response = await conv.get_response()
            phone_text = phone_response.text.strip()
            
            if phone_text == "/cancel":
                await conv.send_message("<b>Process cancelled!</b>", parse_mode='html')
                return
                
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            
            await conv.send_message("Sending OTP...", parse_mode='html')
            sent = await client.send_code_request(phone_text)
            phone_code_hash = sent.phone_code_hash
            
            await conv.send_message(
                "Please check for an OTP in your official Telegram account. Send OTP here in space/dash-separated format if needed (e.g. <code>1 2 3 4 5</code>).\n\n"
                "<i>Enter /cancel to cancel the process.</i>",
                parse_mode='html'
            )
            
            otp_response = await conv.get_response()
            otp_text = otp_response.text.strip()
            
            if otp_text == "/cancel":
                await client.disconnect()
                await conv.send_message("<b>Process cancelled!</b>", parse_mode='html')
                return
                
            phone_code = otp_text.replace(" ", "").replace("-", "")
            
            try:
                await client.sign_in(phone=phone_text, code=phone_code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                await conv.send_message("<b>Your account has enabled two-step verification. Please provide your password.</b>", parse_mode='html')
                pwd_response = await conv.get_response()
                password = pwd_response.text.strip()
                if password == "/cancel":
                    await client.disconnect()
                    await conv.send_message("<b>Process cancelled!</b>", parse_mode='html')
                    return
                await client.sign_in(password=password)
                
            string_session = client.session.save()
            await client.disconnect()
            
            if len(string_session) < SESSION_STRING_SIZE:
                await conv.send_message("<b>Invalid session string generated.</b>", parse_mode='html')
                return
                
            await db.save_user_session(user_id, string_session)
            await conv.send_message("<b>Account Logged In Successfully!</b>\n\n<i>If you experience AUTH KEY errors, please /logout first and /login again.</i>", parse_mode='html')
            
        except PhoneNumberInvalidError:
            await conv.send_message("<code>PHONE_NUMBER</code> <b>is invalid.</b>", parse_mode='html')
        except PhoneCodeInvalidError:
            await conv.send_message("<b>OTP is invalid.</b>", parse_mode='html')
        except PhoneCodeExpiredError:
            await conv.send_message("<b>OTP is expired.</b>", parse_mode='html')
        except asyncio.TimeoutError:
            await conv.send_message("❌ Login timed out due to inactivity. Please use /login again.", parse_mode='html')
        except Exception as e:
            await conv.send_message(f"❌ <b>Error during login:</b> <code>{e}</code>\nPlease start login again using /login", parse_mode='html')

@bot.on(events.NewMessage(pattern='/logout'))
async def logout_command(event):
    user_id = event.sender_id
    existing = await db.get_user_session(user_id)
    if existing is None:
        await event.respond("❌ <b>You are not logged in.</b>", parse_mode='html')
        return
    await db.remove_user_session(user_id)
    if user_id in user_thumbnails:
        try:
            os.remove(user_thumbnails[user_id])
        except Exception:
            pass
        del user_thumbnails[user_id]
    await event.respond("🔒 <b>Logout Successful ♦</b>", parse_mode='html')

@bot.on(events.NewMessage(pattern='/kill'))
async def kill_command(event):
    user_id = event.sender_id
    if user_id in active_transfer_tasks:
        active_transfer_tasks[user_id].cancel()
        del active_transfer_tasks[user_id]
    await event.respond("⚡ <b>Force Cleared!</b> All active transfer tasks terminated.", parse_mode='html')

@bot.on(events.NewMessage(pattern='/cleanup_cache'))
async def cleanup_cache(event):
    await event.respond("🧹 <b>Cache Cleaned Successfully!</b>", parse_mode='html')

# ================= 5. CLONE WIZARD (Interactive with Rules & Thumbnail Support) =================
@bot.on(events.NewMessage(pattern='/clone'))
async def clone_command(event):
    user_id = event.sender_id
    session_str = await db.get_user_session(user_id)
    if not session_str:
        await event.respond("❌ <b>Login Required!</b> Please use /login first to link your account.", parse_mode='html')
        return

    async with bot.conversation(event.chat_id, timeout=300) as conv:
        filename_rule = None
        caption_rule = None
        if user_id in user_thumbnails:
            thumb_path = user_thumbnails[user_id]
        else:
            thumb_path = None

        try:
            while True:
                await conv.send_message(
                    "📍 <b>Step 1/3: Range Selection</b>\n\n"
                    "Send the Link of the <b>First Message</b> you want to clone from.\n"
                    "Example: <code>https://t.me/c/12345/100</code>\n\n"
                    "<i>Enter /cancel to cancel.</i>",
                    parse_mode='html'
                )
                resp1 = await conv.get_response()
                text1 = resp1.text.strip()
                if text1 == "/cancel":
                    await conv.send_message("❌ Task Setup Cancelled.", parse_mode='html')
                    return
                    
                try:
                    parts = text1.split("/")
                    if "c" in parts:
                        c_idx = parts.index("c")
                        source_channel = int("-100" + parts[c_idx + 1])
                        start_msg = int(parts[c_idx + 2])
                    else:
                        raise ValueError("Invalid format link")
                    break
                except Exception as e:
                    await conv.send_message(f"❌ <b>Invalid Link Format:</b> {e}\nPlease send a valid link again.", parse_mode='html')

            while True:
                await conv.send_message(
                    f"✅ <b>Start Message ID:</b> <code>{start_msg}</code>\n\n"
                    f"📍 <b>Step 2/3:</b> Now send the Link of the <b>Last Message</b>.\n\n"
                    f"<i>Enter /cancel to cancel.</i>",
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
                except Exception as e:
                    await conv.send_message(f"❌ <b>Invalid Link Format:</b> {e}\nPlease send a valid last message link again.", parse_mode='html')

            await conv.send_message(
                f"✅ <b>Range Set:</b> <code>{start_msg}</code> to <code>{end_msg}</code>\n\n"
                f"📦 <b>Step 3/3:</b> Send Destination Channel/Group ID (e.g., <code>-100XXXXXXXXXX</code>).\n\n"
                f"<i>Enter /cancel to cancel.</i>",
                parse_mode='html'
            )
            resp3 = await conv.get_response()
            text3 = resp3.text.strip()
            if text3 == "/cancel":
                await conv.send_message("❌ Task Setup Cancelled.", parse_mode='html')
                return
            destination = int(text3)

            while True:
                fn_display = f"{filename_rule['old']} ➔ {filename_rule['new']}" if filename_rule else 'None'
                cap_display = f"{caption_rule['old']} ➔ {caption_rule['new']}" if caption_rule else 'None'
                thumb_display = "Custom Image Set ✅" if thumb_path and os.path.exists(thumb_path) else 'Default'

                buttons = [
                    [Button.inline("📄 Filename: Find & Replace", data="rule_filename")],
                    [Button.inline("💬 Caption: Find & Replace", data="rule_caption")],
                    [Button.inline("🖼️ Thumbnail: Replace/Set", data="rule_thumbnail")],
                    [Button.inline("✅ Confirm & Start Transfer", data="start_transfer_task")],
                    [Button.inline("❌ Cancel", data="cancel_clone")]
                ]
                
                status_msg = await conv.send_message(
                    "⚙️ <b>Clone Setup Summary & Options:</b>\n"
                    "-------------------------------------\n"
                    f"📥 <b>Source:</b> <code>{source_channel}</code>\n"
                    f"📤 <b>Destination:</b> <code>{destination}</code>\n"
                    f"🔢 <b>Range:</b> <code>{start_msg}</code> to <code>{end_msg}</code>\n"
                    f"📄 <b>Filename Rule:</b> <code>{fn_display}</code>\n"
                    f"💬 <b>Caption Rule:</b> <code>{cap_display}</code>\n"
                    f"🖼️ <b>Thumbnail:</b> <code>{thumb_display}</code>\n\n"
                    "Configure optional rules below or start transfer:",
                    buttons=buttons,
                    parse_mode='html'
                )

                click_event = await conv.wait_event(events.CallbackQuery(pattern=b"^(rule_filename|rule_caption|rule_thumbnail|start_transfer_task|cancel_clone)$"), timeout=120)
                action = click_event.data.decode()
                await click_event.answer()

                if action == "cancel_clone":
                    await db.tasks_collection.delete_one({"user_id": user_id})
                    await status_msg.edit("❌ Task Setup Cancelled and Cleared Successfully.", buttons=None)
                    return

                elif action == "start_transfer_task":
                    await db.tasks_collection.update_one(
                        {"user_id": user_id},
                        {"$set": {
                            "source_channel": source_channel,
                            "start_msg": start_msg,
                            "end_msg": end_msg,
                            "destination": destination,
                            "filename_rule": filename_rule,
                            "caption_rule": caption_rule,
                            "thumbnail_path": thumb_path,
                            "current_progress": start_msg,
                            "status": "running"
                        }},
                        upsert=True
                    )
                    
                    if user_id in active_transfer_tasks:
                        active_transfer_tasks[user_id].cancel()
                    
                    active_transfer_tasks[user_id] = asyncio.create_task(background_transfer_worker(user_id, status_msg))
                    
                    await status_msg.edit(
                        "🚀 <b>Background Worker Initialized!</b>\n"
                        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
                        "⚡ <b>Status:</b> Smart media transfer active...\n\n"
                        "<i>(Task is running in background with full resume support)</i>",
                        buttons=[[Button.inline("🛑 Stop Transfer", data="stop_transfer_task")]],
                        parse_mode='html'
                    )
                    return

                elif action == "rule_filename":
                    await status_msg.edit("📄 Send Filename Rule in format: <code>OLD_TEXT | NEW_TEXT</code>\nExample: <code>@OldChannel | @NewChannel</code>", parse_mode='html')
                    rule_resp = await conv.get_response()
                    rule_text = rule_resp.text.strip()
                    if "|" in rule_text:
                        old_t, new_t = rule_text.split("|", 1)
                        filename_rule = {"old": old_t.strip(), "new": new_t.strip()}
                        await conv.send_message("✅ <b>Filename Rule Applied Successfully!</b>", parse_mode='html')
                    else:
                        await conv.send_message("⚠️ <b>Invalid format!</b> Rule not applied.", parse_mode='html')

                elif action == "rule_caption":
                    await status_msg.edit("💬 Send Caption Rule in format: <code>OLD_TEXT | NEW_TEXT</code>\nExample: <code>Join us | Click here</code>", parse_mode='html')
                    rule_resp = await conv.get_response()
                    rule_text = rule_resp.text.strip()
                    if "|" in rule_text:
                        old_t, new_t = rule_text.split("|", 1)
                        caption_rule = {"old": old_t.strip(), "new": new_t.strip()}
                        await conv.send_message("✅ <b>Caption Rule Applied Successfully!</b>", parse_mode='html')
                    else:
                        await conv.send_message("⚠️ <b>Invalid format!</b> Rule not applied.", parse_mode='html')

                elif action == "rule_thumbnail":
                    await status_msg.edit("🖼️ Please send the <b>Image file/photo</b> you want to use as custom thumbnail for transferred files.", parse_mode='html')
                    thumb_resp = await conv.get_response()
                    if thumb_resp.media:
                        os.makedirs("downloads", exist_ok=True)
                        t_path = await thumb_resp.download_media(file="downloads/")
                        if t_path:
                            user_thumbnails[user_id] = t_path
                            thumb_path = t_path
                            await conv.send_message("✅ <b>Custom Thumbnail Set Successfully!</b>", parse_mode='html')
                        else:
                            await conv.send_message("⚠️ <b>Failed to download thumbnail image.</b> Try again.", parse_mode='html')
                    else:
                        await conv.send_message("⚠️ <b>No image media found!</b> Thumbnail not updated.", parse_mode='html')

        except asyncio.TimeoutError:
            await conv.send_message("❌ Clone setup timed out due to inactivity. Please use /clone again.", parse_mode='html')
        except Exception as e:
            await conv.send_message(f"❌ <b>Error during setup:</b> <code>{e}</code>\nPlease use /clone again.", parse_mode='html')

# ================= 6. BACKGROUND WORKER WITH STRICT BOT PERMISSION VALIDATION =================
async def background_transfer_worker(user_id, event):
    user_client = None
    try:
        task_data = await db.tasks_collection.find_one({"user_id": user_id})
        if not task_data:
            return
        
        source_channel = task_data["source_channel"]
        destination_raw = task_data["destination"]
        current = task_data.get("current_progress", task_data["start_msg"])
        end = task_data["end_msg"]
        
        filename_rule = task_data.get("filename_rule")
        caption_rule = task_data.get("caption_rule")
        thumbnail_path = task_data.get("thumbnail_path")
        
        session_str = await db.get_user_session(user_id)
        if not session_str:
            await bot.send_message(user_id, "❌ <b>Transfer Failed:</b> User session not found. Please /login again.", parse_mode='html')
            return
            
        user_client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await user_client.connect()
        
        # Strict validation helper to catch missing admin/posting rights
        try:
            destination_entity = await bot.get_entity(destination_raw)
            destination = await bot.get_input_entity(destination_raw)
            
            perms = await bot.get_permissions(destination_entity, 'me')
            
            if perms and hasattr(perms, 'is_admin') and not perms.is_admin:
                raise ChatAdminRequiredError("Bot is not an admin in the destination channel.")
                
        except Exception as perm_err:
            print(f"Strict Permission Check Triggered Error: {perm_err}")
            await event.edit(
                "⚠️ <b>Bot Admin Permission Required!</b>\n\n"
                "The Telegram Bot is <b>not an Administrator</b> in the destination channel/group, or lacks permissions.\n"
                "👉 Please add the bot as an Admin with post rights in your destination channel, then click Retry below.",
                buttons=[
                    [Button.inline("🔄 Retry Transfer", data="retry_transfer_task")],
                    [Button.inline("🛑 Stop Transfer", data="stop_transfer_task")]
                ],
                parse_mode='html'
            )
            await db.tasks_collection.update_one(
                {"user_id": user_id},
                {"$set": {"status": "paused"}}
            )
            return
        
        while current <= end:
            chk = await db.tasks_collection.find_one({"user_id": user_id})
            if not chk or chk.get("status") == "stopped":
                break
                
            try:
                msg = await user_client.get_messages(source_channel, ids=current)
                
                if msg:
                    caption = msg.text or msg.caption or ""
                    
                    if caption_rule and isinstance(caption_rule, dict):
                        old_str = caption_rule.get("old", "")
                        new_str = caption_rule.get("new", "")
                        if old_str and old_str in caption:
                            caption = caption.replace(old_str, new_str)
                    
                    # Markdown format used for transferred items so source **text** turns bold cleanly
                    parse_format = 'md'

                    if msg.media:
                        file_path = await user_client.download_media(msg, file="downloads/")
                        
                        if file_path:
                            original_filename = os.path.basename(file_path)
                            new_filename = original_filename
                            
                            if filename_rule and isinstance(filename_rule, dict):
                                f_old = filename_rule.get("old", "")
                                f_new = filename_rule.get("new", "")
                                if f_old and f_old in new_filename:
                                    new_filename = new_filename.replace(f_old, f_new)
                                    new_path = os.path.join("downloads", new_filename)
                                    if original_filename != new_filename:
                                        os.rename(file_path, new_path)
                                        file_path = new_path
                            
                            is_vid = msg.video or any(ext in original_filename.lower() for ext in [".mp4", ".mkv", ".mov", ".avi", ".webm"])
                            is_aud = msg.audio or any(ext in original_filename.lower() for ext in [".mp3", ".m4a", ".wav", ".flac", ".ogg"])
                            is_img = msg.photo or any(ext in original_filename.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"])
                            
                            try:
                                await bot.send_file(
                                    destination,
                                    file_path,
                                    caption=caption if caption else None,
                                    thumb=thumbnail_path if (thumbnail_path and os.path.exists(thumbnail_path)) else None,
                                    force_document=False if (is_vid or is_aud or is_img) else True,
                                    parse_mode=parse_format
                                )
                            except ChatAdminRequiredError:
                                await event.edit(
                                    "⚠️ <b>Bot Admin Permission Required!</b>\n\n"
                                    "Bot lost admin rights or is not an <b>Administrator</b> in the destination channel.\n"
                                    "👉 Please check admin rights, then click Retry below.",
                                    buttons=[
                                        [Button.inline("🔄 Retry Transfer", data="retry_transfer_task")],
                                        [Button.inline("🛑 Stop Transfer", data="stop_transfer_task")]
                                    ],
                                    parse_mode='html'
                                )
                                await db.tasks_collection.update_one(
                                    {"user_id": user_id},
                                    {"$set": {"status": "paused"}}
                                )
                                return
                            
                            try:
                                os.remove(file_path)
                            except Exception:
                                pass
                    elif msg.text or caption:
                        try:
                            await bot.send_message(
                                destination, 
                                caption if caption else msg.text, 
                                parse_mode=parse_format
                            )
                        except ChatAdminRequiredError:
                            await event.edit(
                                "⚠️ <b>Bot Admin Permission Required!</b>\n\n"
                                "Bot is not an <b>Administrator</b> in the destination channel/group.\n"
                                "👉 Please make the bot an Admin, then click Retry below.",
                                buttons=[
                                    [Button.inline("🔄 Retry Transfer", data="retry_transfer_task")],
                                    [Button.inline("🛑 Stop Transfer", data="stop_transfer_task")]
                                ],
                                parse_mode='html'
                            )
                            await db.tasks_collection.update_one(
                                {"user_id": user_id},
                                {"$set": {"status": "paused"}}
                            )
                            return
                
                try:
                    progress_text = (
                        f"🚀 <b>Transferring Files (Live Status)</b>\n"
                        f"-------------------------------------\n"
                        f"🆔 <b>Processed Message ID:</b> <code>{current}</code> of <code>{end}</code>\n"
                        f"🟢 <b>Status:</b> Successfully Transferred via Bot!"
                    )
                    await event.edit(progress_text, buttons=[[Button.inline("🛑 Stop Transfer", data="stop_transfer_task")]], parse_mode='html')
                except Exception:
                    pass
                
            except Exception as item_err:
                print(f"Error processing message {current} for user {user_id}: {item_err}")
            
            await db.tasks_collection.update_one(
                {"user_id": user_id},
                {"$set": {"current_progress": current + 1}}
            )
            current += 1
            await asyncio.sleep(1)
            
        await bot.send_message(user_id, "✅ <b>File Transfer & Download/Upload Completed Successfully via Bot!</b>", parse_mode='html')
        
    except asyncio.CancelledError:
        print(f"Transfer task for user {user_id} was cancelled.")
    except Exception as e:
        print(f"Error in transfer worker for {user_id}: {e}")
        await bot.send_message(user_id, f"❌ <b>Transfer Error:</b> <code>{e}</code>", parse_mode='html')
    finally:
        if user_client and user_client.is_connected():
            await user_client.disconnect()

@bot.on(events.CallbackQuery(data=b"retry_transfer_task"))
async def retry_transfer_callback(event):
    user_id = event.sender_id
    await db.tasks_collection.update_one(
        {"user_id": user_id},
        {"$set": {"status": "running"}}
    )
    await event.edit("🔄 Resuming Transfer Task...", parse_mode='html')
    if user_id in active_transfer_tasks:
        active_transfer_tasks[user_id].cancel()
    active_transfer_tasks[user_id] = asyncio.create_task(background_transfer_worker(user_id, event))

@bot.on(events.CallbackQuery(data=b"stop_transfer_task"))
async def stop_transfer_callback(event):
    user_id = event.sender_id
    await db.tasks_collection.update_one(
        {"user_id": user_id},
        {"$set": {"status": "stopped"}}
    )
    if user_id in active_transfer_tasks:
        active_transfer_tasks[user_id].cancel()
        del active_transfer_tasks[user_id]
        
    await event.edit("🛑 <b>Transfer Stopped & Saved!</b> Progress checkpoint recorded in MongoDB. Use /clone to resume or start new.", parse_mode='html')

@bot.on(events.NewMessage(pattern='/stop'))
async def stop_command(event):
    user_id = event.sender_id
    await db.tasks_collection.update_one(
        {"user_id": user_id},
        {"$set": {"status": "stopped"}}
    )
    if user_id in active_transfer_tasks:
        active_transfer_tasks[user_id].cancel()
        del active_transfer_tasks[user_id]
    await event.respond("🛑 <b>Active task successfully stopped and state saved to database.</b>", parse_mode='html')

print("Bot is fully running and listening...")
bot.run_until_disconnected()
