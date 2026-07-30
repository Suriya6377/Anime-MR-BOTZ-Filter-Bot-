import re
import logging
import asyncio
from datetime import datetime, timedelta
from pyrogram import Client, filters, StopPropagation
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, ForceReply
from pyrogram.enums import ChatType, ParseMode
import info
from database.maintenance_db import main_db

# Try to load support_chat_id safely
try:
    support_chat_id = getattr(info, "support_chat_id", None)
except Exception:
    support_chat_id = None

ADMINS = getattr(info, "ADMINS", [])
OWNERID = getattr(info, "OWNERID", None)

# Admin states for conversation flow
ADMIN_STATES = {}

# Store active maintenance state in memory for fast lookup
class MaintenanceState:
    def __init__(self):
        self.enabled = False
        self.reason = ""
        self.end_time = None
        self.initialized = False

MAINTENANCE = MaintenanceState()

async def sync_maintenance_state(bot_id):
    status = await main_db.get_maintenance_status(bot_id)
    MAINTENANCE.enabled = status.get('enabled', False)
    MAINTENANCE.reason = status.get('reason', "")
    MAINTENANCE.end_time = status.get('end_time', None)
    MAINTENANCE.initialized = True

    # Check expiration
    if MAINTENANCE.enabled and MAINTENANCE.end_time:
        if datetime.now() >= MAINTENANCE.end_time:
            # Expired
            await main_db.clear_maintenance_data(bot_id)
            await main_db.update_maintenance(bot_id, enabled=False)
            MAINTENANCE.enabled = False
            MAINTENANCE.reason = ""
            MAINTENANCE.end_time = None

def get_maintenance_message(user_mention):
    msg = f"<b>🛠 Maintenance Break!</b>\n\n"
    msg += f"Hello {user_mention},\n"
    msg += "The bot is currently under maintenance. Please try again later.\n\n"

    if MAINTENANCE.reason:
        msg += f"<b>Reason:</b> {MAINTENANCE.reason}\n"

    if MAINTENANCE.end_time:
        # Calculate remaining time
        now = datetime.now()
        if MAINTENANCE.end_time > now:
            remaining = MAINTENANCE.end_time - now
            hours, remainder = divmod(remaining.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)

            hours = int(hours)
            minutes = int(minutes)

            time_parts = []

            if hours > 0:
                if hours == 1:
                    time_parts.append("1 Hour")
                else:
                    time_parts.append(f"{hours} Hours")

            if minutes > 0:
                if minutes == 1:
                    time_parts.append("1 Minute")
                else:
                    time_parts.append(f"{minutes} Minutes")

            if not time_parts:
                time_parts.append("Less than a minute")

            remaining_str = " ".join(time_parts)
            msg += f"<b>Remaining Time:</b> {remaining_str}\n"
        else:
            msg += f"<b>Remaining Time:</b> Should be finishing up now...\n"

    return msg

def parse_duration(duration_str):
    duration_str = duration_str.lower().strip()
    match = re.match(r'^(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?$', duration_str)
    if not match:
        return None

    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0

    if hours == 0 and minutes == 0:
        return None

    return timedelta(hours=hours, minutes=minutes)

# Hook to capture admin input
@Client.on_message(filters.user(ADMINS) & filters.private, group=-3)
async def admin_input_hook(client: Client, message: Message):
    if not message.text:
        return

    user_id = message.from_user.id
    if user_id not in ADMIN_STATES:
        return

    state = ADMIN_STATES[user_id]

    if message.text and message.text.startswith("/cancel"):
        del ADMIN_STATES[user_id]
        try:
            await message.delete()
        except:
            pass
        if state.get("prompt_msg_id"):
            try:
                await client.delete_messages(chat_id=user_id, message_ids=state["prompt_msg_id"])
            except:
                pass
        raise StopPropagation

    if state["action"] == "reason":
        reason = message.text
        if not reason:
            msg = await message.reply_text("Please provide a valid text reason, or send /cancel.")
            await asyncio.sleep(2)
            try:
                await msg.delete()
                await message.delete()
            except:
                pass
            raise StopPropagation

        await main_db.update_maintenance(client.me.id, reason=reason)
        await sync_maintenance_state(client.me.id)

        # update panel
        text, reply_markup = get_maintenance_panel(client.me.id)
        if state["msg_id"]:
            try:
                await client.edit_message_text(
                    chat_id=user_id,
                    message_id=state["msg_id"],
                    text=text,
                    reply_markup=reply_markup
                )
            except Exception:
                pass

        try:
            await message.delete()
        except:
            pass
        if state.get("prompt_msg_id"):
            try:
                await client.delete_messages(chat_id=user_id, message_ids=state["prompt_msg_id"])
            except:
                pass

        success_msg = await message.reply_text("✅ Maintenance reason updated.")
        await asyncio.sleep(2)
        try:
            await success_msg.delete()
        except:
            pass

        del ADMIN_STATES[user_id]
        raise StopPropagation

    elif state["action"] == "time":
        duration_str = message.text
        delta = parse_duration(duration_str)

        if not delta:
            err_msg = await message.reply_text("Invalid format. Examples: `30m`, `1h`, `1h 30m` or /cancel")
            await asyncio.sleep(2)
            try:
                await err_msg.delete()
                await message.delete()
            except:
                pass
            raise StopPropagation

        end_time = datetime.now() + delta
        await main_db.update_maintenance(client.me.id, end_time=end_time)
        await sync_maintenance_state(client.me.id)

        # update panel
        text, reply_markup = get_maintenance_panel(client.me.id)
        if state["msg_id"]:
            try:
                await client.edit_message_text(
                    chat_id=user_id,
                    message_id=state["msg_id"],
                    text=text,
                    reply_markup=reply_markup
                )
            except Exception:
                pass

        try:
            await message.delete()
        except:
            pass
        if state.get("prompt_msg_id"):
            try:
                await client.delete_messages(chat_id=user_id, message_ids=state["prompt_msg_id"])
            except:
                pass

        success_msg = await message.reply_text(f"✅ Maintenance end time set to:\n`{end_time.strftime('%Y-%m-%d %H:%M')}`")
        await asyncio.sleep(2)
        try:
            await success_msg.delete()
        except:
            pass

        del ADMIN_STATES[user_id]
        raise StopPropagation


# Global hook before all other plugins
@Client.on_message(group=-2)
async def maintenance_hook(client: Client, message: Message):
    if not message:
        return

    if not MAINTENANCE.initialized:
        await sync_maintenance_state(client.me.id)

    if not MAINTENANCE.enabled:
        return

    # Periodic check for expiration on messages but without calling DB unless it expired
    if MAINTENANCE.end_time and datetime.now() >= MAINTENANCE.end_time:
        await sync_maintenance_state(client.me.id)
        if not MAINTENANCE.enabled:
            return

    user_id = message.from_user.id if message.from_user else None
    chat_id = message.chat.id

    # Allow admins and owner
    if (ADMINS and user_id in ADMINS) or (OWNERID and user_id == OWNERID):
        return

    # Allow support chat
    try:
        support_id = int(support_chat_id) if support_chat_id else None
    except:
        support_id = None

    if support_id and chat_id == support_id:
        return

    # Block normal users
    if message.chat.type == ChatType.PRIVATE:
        user_mention = message.from_user.mention if message.from_user else "User"
        try:
            await message.reply_text(get_maintenance_message(user_mention), parse_mode=ParseMode.HTML)
        except:
            pass

    raise StopPropagation

@Client.on_callback_query(group=-2)
async def maintenance_callback_hook(client: Client, query: CallbackQuery):
    if not MAINTENANCE.initialized:
        await sync_maintenance_state(client.me.id)

    if not MAINTENANCE.enabled:
        return

    # Periodic check for expiration
    if MAINTENANCE.end_time and datetime.now() >= MAINTENANCE.end_time:
        await sync_maintenance_state(client.me.id)
        if not MAINTENANCE.enabled:
            return

    user_id = query.from_user.id

    # Allow admins and owner
    if (ADMINS and user_id in ADMINS) or (OWNERID and user_id == OWNERID):
        return

    try:
        await query.answer("The bot is currently under maintenance. Please try again later.", show_alert=True)
    except:
        pass
    raise StopPropagation

def get_maintenance_panel(bot_id):
    status = "🟢 Maintenance Enabled" if MAINTENANCE.enabled else "🔴 Maintenance Disabled"
    text = f"**🛠 Maintenance Control Panel**\n\n**Status:** {status}\n"
    if MAINTENANCE.reason:
        text += f"**Reason:** `{MAINTENANCE.reason}`\n"
    else:
        text += f"**Reason:** `Not set`\n"

    if MAINTENANCE.end_time:
        text += f"**End Time:** `{MAINTENANCE.end_time.strftime('%Y-%m-%d %H:%M')}`\n"
    else:
        text += f"**End Time:** `Not set`\n"

    buttons = [
        [InlineKeyboardButton("🟢 Enable", callback_data="maint_enable"),
         InlineKeyboardButton("🔴 Disable", callback_data="maint_disable")],
        [InlineKeyboardButton("Set Reason", callback_data="maint_reason"),
         InlineKeyboardButton("Set End Time", callback_data="maint_time")],
        [InlineKeyboardButton("Clear Reason & Time", callback_data="maint_clear")],
        [InlineKeyboardButton("⇋ ʙᴀᴄᴋ ⇋", callback_data="about")]
    ]

    return text, InlineKeyboardMarkup(buttons)


@Client.on_message(filters.command("maintenance") & filters.user(ADMINS))
async def maintenance_command(client: Client, message: Message):
    if not MAINTENANCE.initialized:
        await sync_maintenance_state(client.me.id)

    if len(message.command) > 1:
        cmd = message.command[1].lower()
        if cmd == "on":
            await main_db.update_maintenance(client.me.id, enabled=True)
            await sync_maintenance_state(client.me.id)
            await message.reply_text("✅ Maintenance mode **ENABLED**.")
            return
        elif cmd == "off":
            await main_db.update_maintenance(client.me.id, enabled=False)
            await sync_maintenance_state(client.me.id)
            await message.reply_text("❌ Maintenance mode **DISABLED**.")
            return
        elif cmd == "reason":
            reason = " ".join(message.command[2:])
            if not reason:
                await message.reply_text("Please provide a reason. Usage: `/maintenance reason <text>`")
                return
            await main_db.update_maintenance(client.me.id, reason=reason)
            await sync_maintenance_state(client.me.id)
            await message.reply_text(f"✅ Maintenance reason updated to:\n`{reason}`")
            return
        elif cmd in ["for", "until"]:
            duration_str = " ".join(message.command[2:])
            delta = parse_duration(duration_str)
            if not delta:
                await message.reply_text("Invalid duration format. Usage: `/maintenance for 1h 30m` or `30m`")
                return

            end_time = datetime.now() + delta
            await main_db.update_maintenance(client.me.id, end_time=end_time)
            await sync_maintenance_state(client.me.id)
            await message.reply_text(f"✅ Maintenance end time set to:\n`{end_time.strftime('%Y-%m-%d %H:%M')}`")
            return

    # Show panel
    text, reply_markup = get_maintenance_panel(client.me.id)
    await message.reply_text(text, reply_markup=reply_markup)


@Client.on_callback_query(filters.regex(r"^maint_") & filters.user(ADMINS))
async def maint_callbacks(client: Client, query: CallbackQuery):
    bot_id = client.me.id
    user_id = query.from_user.id

    data = query.data

    if data == "maint_panel":
        text, reply_markup = get_maintenance_panel(bot_id)
        try:
            await query.message.edit_text(text, reply_markup=reply_markup)
        except:
            pass
        return

    if data == "maint_enable":
        await main_db.update_maintenance(bot_id, enabled=True)
        await sync_maintenance_state(bot_id)
        await query.answer("Maintenance enabled.", show_alert=True)

    elif data == "maint_disable":
        await main_db.update_maintenance(bot_id, enabled=False)
        await sync_maintenance_state(bot_id)
        await query.answer("Maintenance disabled.", show_alert=True)

    elif data == "maint_clear":
        await main_db.clear_maintenance_data(bot_id)
        await sync_maintenance_state(bot_id)
        await query.answer("Cleared reason and end time.", show_alert=True)

    elif data == "maint_reason":
        prompt_msg = await query.message.reply_text("✏️ Please send the **maintenance reason** text below, or send /cancel to abort.", reply_markup=ForceReply(True))
        ADMIN_STATES[user_id] = {"action": "reason", "msg_id": query.message.id, "prompt_msg_id": prompt_msg.id}
        await query.answer()
        return

    elif data == "maint_time":
        prompt_msg = await query.message.reply_text("⏰ Please send the **maintenance duration** (e.g. `30m`, `1h`, `1h 30m`), or send /cancel to abort.", reply_markup=ForceReply(True))
        ADMIN_STATES[user_id] = {"action": "time", "msg_id": query.message.id, "prompt_msg_id": prompt_msg.id}
        await query.answer()
        return

    text, reply_markup = get_maintenance_panel(bot_id)
    try:
        await query.message.edit_text(text, reply_markup=reply_markup)
    except:
        pass
