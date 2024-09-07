import os
import discord
from discord.ext import commands
import json
import random
import string
import time
import re

# Define intents
intents = discord.Intents.default()
intents.message_content = True

# Create the bot with a specific prefix and intents
bot = commands.Bot(command_prefix='.', intents=intents)

# Files to store keys, user data, cooldown data, and used keys
KEYS_FILE = 'keys.json'
USERS_FILE = 'users.json'
HWIDS_FILE = 'hwids.json'
COOLDOWNS_FILE = 'cooldowns.json'
USED_KEYS_FILE = 'usedkeys.json'

# Role IDs
BUYER_ROLE_ID = 1272776413908308041  # Replace with your actual Buyer role ID
ADMIN_ROLE_ID = 1272804155433422931  # Role ID that can reset cooldowns

# New user ID for specific message handling
TARGET_USER_ID = '1281744707323695156'

def load_json(file_path):
    """Load JSON data from a file."""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_json(file_path, data):
    """Save JSON data to a file."""
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

def generate_keys(num_keys):
    """Generate a dictionary of keys with a given number of keys."""
    keys = {}
    for _ in range(num_keys):
        key = ''.join(random.choices(string.digits, k=11))
        keys[key] = "Key not redeemed yet"
    return keys

def generate_hwid(user_id):
    """Generate a unique HWID for a user in the format @<HWID>."""
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"@{user_id}-{random_suffix}"

def redeem_key_without_hwid(key, user_id):
    """Redeem a key for a user but without storing the HWID initially."""
    keys = load_json(KEYS_FILE)
    users = load_json(USERS_FILE)
    used_keys = load_json(USED_KEYS_FILE)

    if key in keys:
        if keys[key] == "Key not redeemed yet":
            # Assign the key to the user but do not store HWID yet
            keys[key] = {
                "redeemed_by": f"@{user_id}",
                "hwid": None  # HWID will be added later
            }
            users[user_id] = key

            # Add the key to used keys
            used_keys.append(key)
            save_json(USED_KEYS_FILE, used_keys)

            # Save updated data
            save_json(KEYS_FILE, keys)
            save_json(USERS_FILE, users)

            return True
        else:
            return False  # Key already redeemed
    return False  # Key does not exist

def update_key_hwid_after_confirmation(key, hwid):
    """Update the HWID for a redeemed key after confirmation by the target user, but only if no HWID is set."""
    keys = load_json(KEYS_FILE)

    if key in keys:
        if isinstance(keys[key], dict):
            current_hwid = keys[key].get('hwid')
            if current_hwid is None:  # Only update if HWID is not set
                keys[key]['hwid'] = hwid
                save_json(KEYS_FILE, keys)
                return True
    return False

def is_buyer(ctx):
    """Check if the user has the 'Buyer' role."""
    role = discord.utils.get(ctx.guild.roles, id=BUYER_ROLE_ID)
    return role in ctx.author.roles

def is_admin(ctx):
    """Check if the user has the admin role."""
    role = discord.utils.get(ctx.guild.roles, id=ADMIN_ROLE_ID)
    return role in ctx.author.roles

def buyer_required():
    """Decorator to require the 'Buyer' role."""
    def predicate(ctx):
        return is_buyer(ctx)
    return commands.check(predicate)

def admin_required():
    """Decorator to require the admin role."""
    def predicate(ctx):
        return is_admin(ctx)
    return commands.check(predicate)

@bot.event
async def on_ready():
    print(f'Logged on as {bot.user}!')

@bot.event
async def on_message(message):
    # Check if the message author is the target user ID
    if str(message.author.id) == TARGET_USER_ID:
        # Respond with "Understood, copied"
        await message.channel.send("Understood, copied")

        # Define regex patterns to match the details
        user_pattern = re.compile(r'User:\s*(\S+)')
        client_id_pattern = re.compile(r'Client ID:\s*([\w-]+)')
        script_key_pattern = re.compile(r'Script Key:\s*(\S+)')

        # Find matches in the message content
        user_match = user_pattern.search(message.content)
        client_id_match = client_id_pattern.search(message.content)
        script_key_match = script_key_pattern.search(message.content)

        # Extract data if matches are found
        if user_match and client_id_match and script_key_match:
            user = user_match.group(1)
            client_id = client_id_match.group(1)
            script_key = script_key_match.group(1)

            # Check if the key is already redeemed and HWID needs to be added
            keys = load_json(KEYS_FILE)
            key_data = keys.get(script_key)

            if key_data and key_data.get("hwid") is None:
                # Add HWID to the key after confirmation
                if update_key_hwid_after_confirmation(script_key, client_id):
                    await message.channel.send(f"HWID for key {script_key} has been updated.")
                else:
                    await message.channel.send(f"Key {script_key} already has a HWID or is not valid.")

    # Process other commands
    await bot.process_commands(message)

@bot.command()
async def hello(ctx):
    """Responds with a greeting."""
    await ctx.send('Hello!')

@bot.command()
@admin_required()
async def clear(ctx, amount: int):
    """Deletes a specified number of messages."""
    if amount < 1 or amount > 100:
        await ctx.send('Please provide a number between 1 and 100.')
        return

    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f'Deleted: {len(deleted)} messages.', delete_after=5)

@bot.command()
@buyer_required()
async def hwid(ctx):
    """Returns the HWID associated with the key redeemed by the user."""
    user_id = str(ctx.author.id)
    users = load_json(USERS_FILE)
    keys = load_json(KEYS_FILE)

    # Check if the user has redeemed a key
    if user_id in users:
        redeemed_key = users[user_id]
        key_data = keys.get(redeemed_key)

        if key_data and key_data.get('hwid'):
            hwid = key_data['hwid']
            await ctx.send(f'Your HWID associated with the key {redeemed_key} is: {hwid}')
        else:
            await ctx.send('No HWID has been set for your redeemed key yet.')
    else:
        await ctx.send('You have not redeemed any keys.')

@bot.command()
@buyer_required()
async def resethwid(ctx):
    """Resets the HWID for the key redeemed by the user."""
    user_id = str(ctx.author.id)
    keys = load_json(KEYS_FILE)
    cooldowns = load_json(COOLDOWNS_FILE)

    current_time = time.time()

    if user_id in cooldowns:
        last_used_time = cooldowns[user_id]
        elapsed_time = current_time - last_used_time
        cooldown_period = 86400  # 1 day in seconds

        if elapsed_time < cooldown_period:
            remaining_time = cooldown_period - elapsed_time
            hours, remainder = divmod(remaining_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            cooldown_message = (
                f"{ctx.author.mention}, you need to wait {int(hours)} hours, {int(minutes)} minutes, and {int(seconds)} seconds "
                "before using this command again."
            )
            await ctx.send(cooldown_message)
            return

    # Update cooldown timestamp
    cooldowns[user_id] = current_time
    save_json(COOLDOWNS_FILE, cooldowns)

    # Reset HWID in the key data
    if user_id in keys:
        redeemed_key = keys[user_id]
        if redeemed_key in keys and isinstance(keys[redeemed_key], dict):
            keys[redeemed_key]['hwid'] = None
            save_json(KEYS_FILE, keys)

    await ctx.send('Your HWID has been reset.')

@bot.command()
@buyer_required()
async def redeem(ctx, key: str):
    """Redeem a script key."""
    user_id = str(ctx.author.id)

    if redeem_key_without_hwid(key, user_id):
        await ctx.send(f'Successfully redeemed key {key}!')
    else:
        await ctx.send('Invalid or already redeemed key.')

@bot.command()
@admin_required()
async def resetcooldown(ctx, member: discord.Member):
    """Allows admins to reset the HWID cooldown for a specific member."""
    cooldowns = load_json(COOLDOWNS_FILE)

    user_id = str(member.id)
    if user_id in cooldowns:
        del cooldowns[user_id]
        save_json(COOLDOWNS_FILE, cooldowns)
        await ctx.send(f'{member.mention}\'s cooldown has been reset.')
    else:
        await ctx.send(f'{member.mention} has no cooldown to reset.')

@bot.command()
@admin_required()
async def generatekeys(ctx, num_keys: int):
    """Generates a number of random script keys."""
    if num_keys < 1:
        await ctx.send("Please provide a valid number of keys to generate.")
        return

    # Generate and save new keys
    new_keys = generate_keys(num_keys)
    keys = load_json(KEYS_FILE)
    keys.update(new_keys)
    save_json(KEYS_FILE, keys)

    # Send the generated keys to the admin
    for key in new_keys.keys():
        await ctx.author.send(f"Generated key: {key}")

@bot.command()
@admin_required()
async def dumpkeys(ctx):
    """Sends the list of all current keys to the admin."""
    keys = load_json(KEYS_FILE)
    message = "\n".join([f"{key}: {value}" for key, value in keys.items()])
    await ctx.author.send(f"Here are the current keys:\n{message}")

@bot.command()
@admin_required()
async def resetkeys(ctx):
    """Resets all keys to 'Key not redeemed yet'."""
    keys = load_json(KEYS_FILE)
    for key in keys:
        keys[key] = "Key not redeemed yet"
    save_json(KEYS_FILE, keys)
    await ctx.send("All keys have been reset.")

# Run the bot with your token
if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_BOT_KEY'))
