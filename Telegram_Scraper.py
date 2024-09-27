import boto3
import json
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

s3 = boto3.client('s3')
bucket_name = os.environ.get('S3_BUCKET_NAME')
api_id = os.environ.get("TELEGRAM_APP_API_ID")
api_hash = os.environ.get("TELEGRAM_APP_API_HASH")
string_session = os.environ.get("TELEGRAM_STRING_SESSION")  # Your session string stored in an environment variable
channel_username = 'PikudHaOref_all'

def lambda_handler(event, context):
    # Use StringSession to create a client
    with TelegramClient(StringSession(string_session), api_id, api_hash) as client:
        # Fetch the channel entity using its username
        channel = client.get_entity(channel_username)

        # Get the message history
        messages = []
        for message in client.iter_messages(channel, limit=80):
            messages.append(message.text)

    # Save messages to S3 as JSON
    bytes_ = json.dumps(messages, ensure_ascii=False).encode('utf-8')
    s3.put_object(Bucket=bucket_name, Key='telegram_messages.json', Body = bytes_)

    return {
        'statusCode': 200,
        'body': 'Messages saved to S3'
    }