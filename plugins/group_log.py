from pyrogram import Client, filters, enums
from pyrogram.types import ChatMemberUpdated
from info import ADMIN_STATUS_CHANNEL
import html

@Client.on_chat_member_updated(filters.group, group=10)
async def group_member_log(client, chat_member_updated: ChatMemberUpdated):
    if not ADMIN_STATUS_CHANNEL:
        return

    new = chat_member_updated.new_chat_member
    old = chat_member_updated.old_chat_member
    chat = chat_member_updated.chat

    # JOIN
    if new and new.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        # Only log as join if they were previously NOT in the group (None, Left, Banned)
        # If they were RESTRICTED, they were already in the group (just muted/restricted), so unmuting is not a Join.
        if not old or old.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:

            user = new.user
            inviter = None

            # Check for invite link
            if chat_member_updated.invite_link and chat_member_updated.invite_link.creator:
                creator = chat_member_updated.invite_link.creator
                inviter = f"{creator.mention(style='html')} [<code>{creator.id}</code>]"

            # Check for direct add (from_user is the adder, and it's not the user themselves)
            elif chat_member_updated.from_user and chat_member_updated.from_user.id != user.id:
                 adder = chat_member_updated.from_user
                 inviter = f"{adder.mention(style='html')} [<code>{adder.id}</code>]"

            # Construct message
            group_title = html.escape(chat.title)
            msg = f"➕ #JOIN_USER\n"
            msg += f"• Of: {user.mention(style='html')} [<code>{user.id}</code>]\n"
            msg += f"• Group: {group_title} [<code>{chat.id}</code>]\n"
            if inviter:
                msg += f"• Link by: {inviter}\n"
            msg += f"#id{user.id}"

            try:
                await client.send_message(ADMIN_STATUS_CHANNEL, msg, parse_mode=enums.ParseMode.HTML)
            except Exception as e:
                print(f"Error sending log: {e}")

    # LEFT
    elif old and old.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        if not new or new.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:
            # User left or was kicked/banned

            user = old.user
            group_title = html.escape(chat.title)

            msg = f"➖ #USER_LEFT\n"
            msg += f"• Of: {user.mention(style='html')} [<code>{user.id}</code>]\n"
            msg += f"• Group: {group_title} [<code>{chat.id}</code>]\n"
            msg += f"#id{user.id}"

            try:
                await client.send_message(ADMIN_STATUS_CHANNEL, msg, parse_mode=enums.ParseMode.HTML)
            except Exception as e:
                print(f"Error sending log: {e}")
