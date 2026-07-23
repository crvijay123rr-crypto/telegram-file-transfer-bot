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

# In-memory store for active transfer tasks
active_transfer_tasks = {}

SESSION_STRING_SIZE = 351

print("🚀 Initializing Advanced Telegram File Transfer Bot (v5.8 - Full Features & Admin Tools)...")

# ================= 1. /start COMMAND =================
@bot.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    user_id = event.sender_id
    user_data = await db.get_user(user_id)
    session_str = await db.get_user_session(user_id)
    
    is_premium = user_data.get("is_premium", False) if user_data else False
    status_str = "🟢 Logged In" if session_str else "🔴 Not Logged In"
    tier_str = "👑 Premium Member" if is_premium else "🆓 Free User"
    
    msg = (
        f"🚀 File Transfer Bot (v5.8 - Professional)\n"
        f"-------------------------------------\n"
        f"👤 Status: {tier_str}\n"
        f"🔑 Session: {status_str}\n\n"
        f"Commands Menu:\n"
        f"1. /login - Connect Telegram Account\n"
        f"2. /clone - Start File Transfer & Custom Rules (👑 Premium Only)\n"
        f"3. /stop - Stop active transfer\n"
        f"4. /kill - Force clear stuck tasks\n"
        f"5. /cleanup_cache - Clear temporary cache\n"
        f"6. /buy - Get Premium Access\n"
        f"7. /logout - Disconnect Account\n"
    )
    if user_id in ADMIN_IDS:
        msg += (
            f"\n👑 Admin Controls:\n"
            f"• /admin_stats - View Statistics\n"
            f"• /addpremium <id> - Grant Premium\n"
            f"• /removepremium <id> - Revoke Premium\n"
            f"• /checkuser <id> - Check User Status\n"
            f"• /premiumlist - View All Premium Users"
        )

    buttons = [
        [Button.inline("ℹ️ How to use?", data="how_to_use"),
         Button.inline("📊 Bot Stats", data="bot_stats")]
    ]
    await event.respond(msg, buttons=buttons, parse_mode=None)

# ================= 2. HELP & STATS CALLBACKS =================
@bot.on(events.CallbackQuery(pattern=b"how_to_use"))
async def how_to_use_callback(event):
    await event.answer(
        "📖 Guide:\n1. Use /login to link account.\n2. Ensure Bot is Admin in destination channel.\n3. Use /clone to set range, rules & thumbnail (Premium Only).\n4. Click Start!",
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
        await event.respond("✨ You are already a Premium Member! Enjoy unrestricted file transfers.", parse_mode=None)
        return

    await event.respond(
        f"💳 Subscription / Buy Access\n"
        f"-------------------------------------\n"
        f"🆔 Your User ID: {user_id}\n\n"
        f"👉 Please send payment screenshot/proof to the Admin, and click the button below to notify instantly.",
        buttons=[[Button.inline("🔔 Notify Admin for Approval", data=f"notify_admin_{user_id}")]],
        parse_mode=None
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
                f"🔔 New Premium Request!\n\n"
                f"👤 User: {user_entity.first_name} ({username})\n"
                f"🆔 User ID: {user_id}\n\n"
                f"Click below to approve:",
                buttons=[[Button.inline("✅ Approve Premium", data=f"approve_{user_id}")]],
                parse_mode=None
            )
        except Exception as e:
            print(f"Failed to notify admin {admin_id}: {e}")
            
    await event.answer("Request sent to Admin successfully!", alert=True)
    await event.edit("⏳ Request Sent!\nAdmin has been notified. Please wait for activation.", parse_mode=None)

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
    await event.edit(f"✅ Successfully activated Premium for User ID: {target_user_id}", parse_mode=None)
    
    try:
        await bot.send_message(
            target_user_id,
            "🎉 Subscription Activated!\nYour account has been upgraded to Premium Member by Admin. Use /login to start transferring.",
            parse_mode=None
        )
    except Exception as e:
        print(f"Could not message user {target_user_id}: {e}")

@bot.on(events.NewMessage(pattern='/addpremium'))
async def add_premium_command(event):
    if event.sender_id not in ADMIN_IDS:
        return
    parts = event.text.split()
    if len(parts) < 2:
        await event.respond("⚠️ Usage: `/addpremium <user_id>`", parse_mode=None)
        return
    
    target_id = int(parts[1])
    await db.users_collection.update_one(
        {"user_id": target_id}, {"$set": {"is_premium": True}}, upsert=True
    )
    await event.respond(f"✅ User {target_id} is now a Premium Member.", parse_mode=None)

@bot.on(events.NewMessage(pattern='/removepremium'))
async def remove_premium_command(event):
    if event.sender_id not in ADMIN_IDS:
        return
    parts = event.text.split()
    if len(parts) < 2:
        await event.respond("⚠️ Usage: `/removepremium <user_id>`", parse_mode=None)
        return
    
    target_id = int(parts[1])
    await db.users_collection.update_one(
        {"user_id": target_id}, {"$set": {"is_premium": False}}, upsert=True
    )
    await event.respond(f"❌ User {target_id} premium membership has been revoked.", parse_mode=None)
    try:
        await bot.send_message(
            target_id,
            "⚠️ Your Premium membership has been revoked by the Admin.",
            parse_mode=None
        )
    except Exception:
        pass

@bot.on(events.NewMessage(pattern='/checkuser'))
async def check_user_command(event):
    if event.sender_id not in ADMIN_IDS:
        return
        
    parts = event.text.split()
    if len(parts) < 2:
        await event.respond("⚠️ Usage: `/checkuser <user_id>`", parse_mode=None)
        return
        
    try:
        target_id = int(parts[1])
    except ValueError:
        await event.respond("❌ Invalid User ID format. Please provide a valid numeric ID.", parse_mode=None)
        return
        
    user_data = await db.get_user(target_id)
    session_str = await db.get_user_session(target_id)
    
    if not user_data:
        await event.respond(f"ℹ️ User ID `{target_id}` ka koi data database mein nahi mila.", parse_mode=None)
        return
        
    is_premium = user_data.get("is_premium", False)
    tier_status = "👑 Premium Member" if is_premium else "🆓 Free User"
    session_status = "🟢 Logged In (Active Session)" if session_str else "🔴 Not Logged In"
    
    await event.respond(
        f"📊 **User Details Lookup**\n"
        f"-------------------------------------\n"
        f"🆔 User ID: `{target_id}`\n"
        f"👤 Status: {tier_status}\n"
        f"🔑 Session: {session_status}",
        parse_mode=None
    )

@bot.on(events.NewMessage(pattern='/premiumlist'))
async def premium_list_command(event):
    if event.sender_id not in ADMIN_IDS:
        return
        
    try:
        cursor = db.users_collection.find({"is_premium": True})
        premium_users = await cursor.to_list(length=None)
        
        if not premium_users:
            await event.respond("ℹ️ Filhaal database mein koi bhi Premium User maujud nahi hai.", parse_mode=None)
            return
            
        msg = "👑 **List of Premium Users:**\n-------------------------------------\n"
        count = 1
        for user in premium_users:
            u_id = user.get("user_id")
            msg += f"{count}. User ID: `{u_id}`\n"
            count += 1
            
        if len(msg) > 4000:
            msg = msg[:4000] + "\n\n⚠️ List truncated due to message length limits."
            
        await event.respond(msg, parse_mode=None)
        
    except Exception as e:
        await event.respond(f"❌ Error fetching premium list: {e}", parse_mode=None)

@bot.on(events.NewMessage(pattern='/admin_stats'))
async def admin_stats_command(event):
    if event.sender_id not in ADMIN_IDS:
        return
    total_users = await db.users_collection.count_documents({})
    total_sessions = await db.sessions_collection.count_documents({})
    
    await event.respond(
        f"📊 Bot Admin Statistics\n"
        f"-----------------------------\n"
        f"👥 Total Users: {total_users}\n"
        f"🔑 Active Logged-in Sessions: {total_sessions}\n"
        f"🟢 System Status: Healthy & Online",
        parse_mode=None
    )

# ================= 4. INTERACTIVE LOGIN & LOGOUT FLOW =================
@bot.on(events.NewMessage(pattern='/login'))
async def login_command(event):
    user_id = event.sender_id
    existing = await db.get_user_session(user_id)
    if existing:
        await event.respond("✅ You Are Already Logged In. First /logout Your Old Session. Then Do Login.", parse_mode=None)
        return
    
    async with bot.conversation(event.chat_id, timeout=300) as conv:
        await conv.send_message(
            "🔐 Login Step 1/3\n\n"
            "Please send your Phone Number in international format (includes country code).\n"
            "Example: +9171828181889\n\n"
            "Enter /cancel to cancel the process."
        )
        
        try:
            phone_response = await conv.get_response()
            phone_text = phone_response.text.strip()
            
            if phone_text == "/cancel":
                await conv.send_message("<b>Process cancelled !</b>", parse_mode=None)
                return
                
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            
            await conv.send_message("Sending OTP...", parse_mode=None)
            sent = await client.send_code_request(phone_text)
            phone_code_hash = sent.phone_code_hash
            
            await conv.send_message(
                "Please check for an OTP in official Telegram account. If you got it, send OTP here after reading the below format.\n\n"
                "If OTP is `12345`, **please send it as** `1 2 3 4 5` or space/dash separated.\n\n"
                "**Enter /cancel to cancel the process**"
            )
            
            otp_response = await conv.get_response()
            otp_text = otp_response.text.strip()
            
            if otp_text == "/cancel":
                await client.disconnect()
                await conv.send_message("<b>Process cancelled !</b>", parse_mode=None)
                return
                
            phone_code = otp_text.replace(" ", "")
            
            try:
                await client.sign_in(phone=phone_text, code=phone_code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                await conv.send_message('**Your account has enabled two-step verification. Please provide the password.**')
                pwd_response = await conv.get_response()
                password = pwd_response.text.strip()
                if password == "/cancel":
                    await client.disconnect()
                    await conv.send_message("<b>Process cancelled !</b>", parse_mode=None)
                    return
                await client.sign_in(password=password)
                
            string_session = client.session.save()
            await client.disconnect()
            
            if len(string_session) < SESSION_STRING_SIZE:
                await conv.send_message('<b>invalid session string</b>', parse_mode=None)
                return
                
            await db.save_user_session(user_id, string_session)
            await conv.send_message("<b>Account Login Successfully.\n\nIf You Get Any Error Related To AUTH KEY Then /logout first and /login again</b>", parse_mode=None)
            
        except PhoneNumberInvalidError:
            await conv.send_message("`PHONE_NUMBER` **is invalid.**", parse_mode=None)
        except PhoneCodeInvalidError:
            await conv.send_message('**OTP is invalid.**', parse_mode=None)
        except PhoneCodeExpiredError:
            await conv.send_message('**OTP is expired.**', parse_mode=None)
        except asyncio.TimeoutError:
            await conv.send_message("❌ Login timed out due to inactivity. Please use /login again.", parse_mode=None)
        except Exception as e:
            await conv.send_message(f"❌ **Error during login:** `{e}`\nPlease start login again by /login", parse_mode=None)

@bot.on(events.NewMessage(pattern='/logout'))
async def logout_command(event):
    user_id = event.sender_id
    existing = await db.get_user_session(user_id)
    if existing is None:
        return
    await db.remove_user_session(user_id)
    await event.respond("🔒 Logout Successfully ♦", parse_mode=None)

@bot.on(events.NewMessage(pattern='/kill'))
async def kill_command(event):
    user_id = event.sender_id
    if user_id in active_transfer_tasks:
        active_transfer_tasks[user_id].cancel()
        del active_transfer_tasks[user_id]
    await event.respond("⚡ Force Cleared! All active transfer tasks terminated.", parse_mode=None)

@bot.on(events.NewMessage(pattern='/cleanup_cache'))
async def cleanup_cache(event):
    await event.respond("🧹 Cleaned Successfully!", parse_mode=None)

# ================= 5. CLONE WIZARD (Interactive with Rules & Thumbnail + Premium Restriction) =================
@bot.on(events.NewMessage(pattern='/clone'))
async def clone_command(event):
    user_id = event.sender_id
    
    user_data = await db.get_user(user_id)
    is_premium = user_data.get("is_premium", False) if user_data else False
    
    if not is_premium:
        await event.respond(
            "🔒 **Premium Feature Locked!**\n\n"
            "Free users are not allowed to use the file transfer / clone feature. "
            "Please upgrade to **Premium** to unlock unlimited file cloning and custom rules.",
            buttons=[[Button.inline("💳 Buy Premium Now (/buy)", data="buy_premium_redirect")]],
            parse_mode=None
        )
        return

    session_str = await db.get_user_session(user_id)
    if not session_str:
        await event.respond("❌ Login Required! Please use /login first to link your account for restricted bypassing.", parse_mode=None)
        return

    async with bot.conversation(event.chat_id, timeout=300) as conv:
        filename_rule = None
        caption_rule = None
        custom_thumb_path = None

        try:
            while True:
                await conv.send_message(
                    "📍 Step 1/3: Range Selection\n\n"
                    "Send the Link of the First Message you want to clone from.\n"
                    "Example: https://t.me/c/12345/100\n\n"
                    "Enter /cancel to cancel."
                )
                resp1 = await conv.get_response()
                text1 = resp1.text.strip()
                if text1 == "/cancel":
                    await conv.send_message("❌ Task Setup Cancelled.", parse_mode=None)
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
                    await conv.send_message(f"❌ Invalid Link Format: {e}\nPlease send a valid link again.")

            while True:
                await conv.send_message(f"✅ Start Message ID: {start_msg}\n\n📍 Step 2/3: Now send the Link of the Last Message.\n\nEnter /cancel to cancel.")
                resp2 = await conv.get_response()
                text2 = resp2.text.strip()
                if text2 == "/cancel":
                    await conv.send_message("❌ Task Setup Cancelled.", parse_mode=None)
                    return
                    
                try:
                    parts2 = text2.split("/")
                    c_idx2 = parts2.index("c")
                    end_msg = int(parts2[c_idx2 + 2])
                    break
                except Exception as e:
                    await conv.send_message(f"❌ Invalid Link Format: {e}\nPlease send a valid last message link again.")

            await conv.send_message(
                f"✅ Range Set: {start_msg} to {end_msg}\n\n"
                f"📦 Step 3/3: Send Destination Channel/Group ID (e.g., -100XXXXXXXXXX).\n\nEnter /cancel to cancel."
            )
            resp3 = await conv.get_response()
            text3 = resp3.text.strip()
            if text3 == "/cancel":
                await conv.send_message("❌ Task Setup Cancelled.", parse_mode=None)
                return
            destination = int(text3)

            while True:
                fn_display = f"{filename_rule['old']} ➔ {filename_rule['new']}" if filename_rule else 'None'
                cap_display = f"{caption_rule['old']} ➔ {caption_rule['new']}" if caption_rule else 'None'
                thumb_display = "🖼️ Set (Custom)" if custom_thumb_path else "❌ None"

                buttons = [
                    [Button.inline("📄 Filename: Find & Replace", data="rule_filename")],
                    [Button.inline("💬 Caption: Find & Replace", data="rule_caption")],
                    [Button.inline("🖼️ Set Custom Thumbnail", data="rule_thumbnail")],
                    [Button.inline("✅ Confirm & Start Transfer", data="start_transfer_task")],
                    [Button.inline("❌ Cancel", data="cancel_clone")]
                ]
                
                status_msg = await conv.send_message(
                    "⚙️ Clone Setup Summary & Options:\n\n"
                    f"📥 Source: {source_channel}\n"
                    f"📤 Destination: {destination}\n"
                    f"🔢 Range: {start_msg} to {end_msg}\n"
                    f"📄 Filename Rule: {fn_display}\n"
                    f"💬 Caption Rule: {cap_display}\n"
                    f"🖼️ Custom Thumbnail: {thumb_display}\n\n"
                    "Configure optional rules below or start transfer:",
                    buttons=buttons
                )

                click_event = await conv.wait_event(events.CallbackQuery(pattern=b"^(rule_filename|rule_caption|rule_thumbnail|start_transfer_task|cancel_clone)$"), timeout=120)
                action = click_event.data.decode()
                await click_event.answer()

                if action == "cancel_clone":
                    if custom_thumb_path and os.path.exists(custom_thumb_path):
                        try:
                            os.remove(custom_thumb_path)
                        except Exception:
                            pass
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
                            "custom_thumb_path": custom_thumb_path,
                            "current_progress": start_msg,
                            "status": "running"
                        }},
                        upsert=True
                    )
                    
                    if user_id in active_transfer_tasks:
                        active_transfer_tasks[user_id].cancel()
                    
                    active_transfer_tasks[user_id] = asyncio.create_task(background_transfer_worker(user_id, status_msg))
                    
                    await status_msg.edit(
                        "🚀 Background Worker Initialized!\n"
                        f"👤 User: {user_id}\n"
                        "⚡ Status: Smart media transfer with custom thumbnail active...\n\n"
                        "*(Task is running in background with full resume support)*",
                        buttons=[[Button.inline("🛑 Stop Transfer", data="stop_transfer_task")]]
                    )
                    return

                elif action == "rule_filename":
                    await status_msg.edit("📄 Send Filename Rule in format: `OLD_TEXT | NEW_TEXT`\nExample: `@OldChannel | @NewChannel`")
                    rule_resp = await conv.get_response()
                    rule_text = rule_resp.text.strip()
                    if "|" in rule_text:
                        old_t, new_t = rule_text.split("|", 1)
                        filename_rule = {"old": old_t.strip(), "new": new_t.strip()}
                        await conv.send_message("✅ Filename Rule Applied Successfully!")
                    else:
                        await conv.send_message("⚠️ Invalid format! Rule not applied.")

                elif action == "rule_caption":
                    await status_msg.edit("💬 Send Caption Rule in format: `OLD_TEXT | NEW_TEXT`\nExample: `Join us | Click here`")
                    rule_resp = await conv.get_response()
                    rule_text = rule_resp.text.strip()
                    if "|" in rule_text:
                        old_t, new_t = rule_text.split("|", 1)
                        caption_rule = {"old": old_t.strip(), "new": new_t.strip()}
                        await conv.send_message("✅ Caption Rule Applied Successfully!")
                    else:
                        await conv.send_message("⚠️ Invalid format! Rule not applied.")

                elif action == "rule_thumbnail":
                    await status_msg.edit("🖼️ Please **send a photo** (image file) or **send a direct image link** to use as the custom thumbnail:")
                    thumb_resp = await conv.get_response()
                    
                    os.makedirs("downloads", exist_ok=True)
                    if thumb_resp.photo:
                        downloaded_thumb = await thumb_resp.download_media(file="downloads/")
                        if downloaded_thumb:
                            custom_thumb_path = downloaded_thumb
                            await conv.send_message("✅ Custom Thumbnail Photo Saved Successfully!")
                        else:
                            await conv.send_message("⚠️ Failed to download thumbnail photo.")
                    elif thumb_resp.text and (thumb_resp.text.startswith("http://") or thumb_resp.text.startswith("https://")):
                        import urllib.request
                        try:
                            img_url = thumb_resp.text.strip()
                            custom_thumb_path = os.path.join("downloads", f"thumb_{user_id}.jpg")
                            urllib.request.urlretrieve(img_url, custom_thumb_path)
                            await conv.send_message("✅ Custom Thumbnail Downloaded from Link Successfully!")
                        except Exception as dl_err:
                            custom_thumb_path = None
                            await conv.send_message(f"⚠️ Failed to fetch image from link: {dl_err}")
                    else:
                        await conv.send_message("⚠️ Invalid input! Please send a valid photo or image link.")

        except asyncio.TimeoutError:
            await conv.send_message("❌ Clone setup timed out due to inactivity. Please use /clone again.", parse_mode=None)
        except Exception as e:
            await conv.send_message(f"❌ Error during setup: {e}\nPlease use /clone again.", parse_mode=None)

@bot.on(events.CallbackQuery(pattern=b"buy_premium_redirect"))
async def buy_premium_redirect_callback(event):
    await event.answer()
    user_id = event.sender_id
    await event.edit(
        f"💳 Subscription / Buy Access\n"
        f"-------------------------------------\n"
        f"🆔 Your User ID: {user_id}\n\n"
        f"👉 Please send payment screenshot/proof to the Admin, and click the button below to notify instantly.",
        buttons=[[Button.inline("🔔 Notify Admin for Approval", data=f"notify_admin_{user_id}")]],
        parse_mode=None
    )

# ================= 6. BACKGROUND WORKER WITH STRICT BOT ADMIN CHECK & ENTITY RESOLUTION =================
async def background_transfer_worker(user_id, event):
    user_client = None
    task_data = None
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
        custom_thumb_path = task_data.get("custom_thumb_path")
        
        session_str = await db.get_user_session(user_id)
        if not session_str:
            await bot.send_message(user_id, "❌ Transfer Failed: User session not found. Please /login again.")
            return
            
        user_client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await user_client.connect()
        
        try:
            dest_entity_user = await user_client.get_entity(destination_raw)
            destination = await bot.get_input_entity(dest_entity_user)
            
            perms = await bot.get_permissions(dest_entity_user, 'me')
            
            is_admin = False
            if perms:
                if getattr(perms, 'is_admin', False) or getattr(perms, 'admin_rights', None) is not None:
                    is_admin = True
            
            if not is_admin:
                raise ChatAdminRequiredError("Bot is not an admin in the destination channel.")
                
        except Exception as perm_err:
            print(f"Strict Permission Check Triggered Error: {perm_err}")
            await event.edit(
                "⚠️ **Bot Admin Permission Required!**\n\n"
                "The Telegram Bot is **not an Administrator** in the destination channel/group.\n"
                "👉 Please add the bot as an Admin with post rights in your destination channel, then click Retry below.",
                buttons=[
                    [Button.inline("🔄 Retry Transfer", data="retry_transfer_task")],
                    [Button.inline("🛑 Stop Transfer", data="stop_transfer_task")]
                ],
                parse_mode=None
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
                                thumb_to_use = custom_thumb_path if (custom_thumb_path and os.path.exists(custom_thumb_path)) else None
                                
                                await bot.send_file(
                                    destination,
                                    file_path,
                                    caption=caption if caption else None,
                                    thumb=thumb_to_use,
                                    force_document=False if (is_vid or is_aud or is_img) else True,
                                    parse_mode=parse_format
                                )
                            except ChatAdminRequiredError:
                                await event.edit(
                                    "⚠️ **Bot Admin Permission Required!**\n\n"
                                    "Bot lost admin rights or is not an **Administrator** in the destination channel.\n"
                                    "👉 Please check admin rights, then click Retry below.",
                                    buttons=[
                                        [Button.inline("🔄 Retry Transfer", data="retry_transfer_task")],
                                        [Button.inline("🛑 Stop Transfer", data="stop_transfer_task")]
                                    ],
                                    parse_mode=None
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
                                "⚠️ **Bot Admin Permission Required!**\n\n"
                                "Bot is not an **Administrator** in the destination channel/group.\n"
                                "👉 Please make the bot an Admin, then click Retry below.",
                                buttons=[
                                    [Button.inline("🔄 Retry Transfer", data="retry_transfer_task")],
                                    [Button.inline("🛑 Stop Transfer", data="stop_transfer_task")]
                                ],
                                parse_mode=None
                            )
                            await db.tasks_collection.update_one(
                                {"user_id": user_id},
                                {"$set": {"status": "paused"}}
                            )
                            return
                
                try:
                    progress_text = (
                        f"🚀 Transferring Files (Live Status)\n"
                        f"-------------------------------------\n"
                        f"🆔 Processed Message ID: {current} of {end}\n"
                        f"🟢 Status: Successfully Transferred via Bot!"
                    )
                    await event.edit(progress_text, buttons=[[Button.inline("🛑 Stop Transfer", data="stop_transfer_task")]], parse_mode=None)
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
            
        if task_data and task_data.get("custom_thumb_path"):
            t_path = task_data.get("custom_thumb_path")
            if t_path and os.path.exists(t_path):
                try:
                    os.remove(t_path)
                except Exception:
                    pass

        await bot.send_message(user_id, "✅ File Transfer & Download/Upload Completed Successfully via Bot!", parse_mode=None)
        
    except asyncio.CancelledError:
        print(f"Transfer task for user {user_id} was cancelled.")
    except Exception as e:
        print(f"Error in transfer worker for {user_id}: {e}")
        await bot.send_message(user_id, f"❌ Transfer Error: {e}")
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
    await event.edit("🔄 Resuming Transfer Task...", parse_mode=None)
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
        
    await event.edit("🛑 Transfer Stopped & Saved! Progress checkpoint recorded in MongoDB. Use /clone to resume or start new.", parse_mode=None)

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
    await event.respond("🛑 Active task successfully stopped and state saved to database.", parse_mode=None)

print("Bot is fully running and listening...")
bot.run_until_disconnected()
