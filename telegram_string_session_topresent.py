from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 'Your IP'
api_hash = 'Your hash'

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print(client.session.save())  # This prints your session string