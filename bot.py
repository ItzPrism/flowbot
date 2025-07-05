import discord
from discord.ext import commands
import openai
import json
import os

# Load environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Define intents
intents = discord.Intents.all()

# Setup bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Ensure only admins use commands
def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

# Helper: Call OpenAI to process admin prompt
async def process_prompt(prompt):
    system_prompt = """
You are an AI assistant that helps manage a Discord server using natural language commands. 
You respond with structured JSON describing server actions like changing settings, adding roles, 
configuring verification, or sending messages. Do not explain your reasoning.
Only respond with JSON like: {"action": "create_role", "name": "Member", "permissions": [...]}
Available actions: create_role, delete_role, update_channel, send_message, configure_verification
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return json.loads(response['choices'][0]['message']['content'])

# Command: AI control prompt
@bot.command(name="ai", help="Give a prompt to AI to manage the server")
@is_admin()
async def ai_control(ctx, *, prompt: str):
    await ctx.send("Processing your request...")
    try:
        result = await process_prompt(prompt)
        await handle_action(ctx, result)
    except Exception as e:
        await ctx.send(f"Error: {e}")

# Action handler
async def handle_action(ctx, action_data):
    action = action_data.get("action")

    if action == "create_role":
        name = action_data.get("name", "New Role")
        perms = discord.Permissions.none()
        permissions = action_data.get("permissions", [])
        for p in permissions:
            setattr(perms, p, True)
        await ctx.guild.create_role(name=name, permissions=perms)
        await ctx.send(f"✅ Role '{name}' created.")

    elif action == "send_message":
        channel_name = action_data.get("channel", ctx.channel.name)
        channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        if channel:
            await channel.send(action_data.get("content", "Hello!"))
            await ctx.send("📨 Message sent.")
        else:
            await ctx.send(f"⚠️ Channel '{channel_name}' not found.")

    elif action == "configure_verification":
        # Example: react to a message to assign role
        role_name = action_data.get("role_name", "Verified")
        channel_name = action_data.get("channel", "verification")
        emoji = action_data.get("emoji", "✅")

        # Create role if doesn't exist
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            role = await ctx.guild.create_role(name=role_name)
        
        channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
        if not channel:
            channel = await ctx.guild.create_text_channel(channel_name)

        msg = await channel.send(f"React with {emoji} to get verified!")
        await msg.add_reaction(emoji)

        # Save message ID to verify later (in memory or DB)
        bot.verification_message = {
            "message_id": msg.id,
            "role_id": role.id,
            "emoji": emoji
        }
        await ctx.send("✅ Verification system set up.")

# Reaction add = Verification check
@bot.event
async def on_raw_reaction_add(payload):
    data = getattr(bot, "verification_message", None)
    if not data:
        return

    if payload.message_id == data["message_id"] and str(payload.emoji.name) == data["emoji"]:
        guild = discord.utils.get(bot.guilds, id=payload.guild_id)
        member = guild.get_member(payload.user_id)
        role = discord.utils.get(guild.roles, id=data["role_id"])
        if member and role:
            await member.add_roles(role)
            print(f"Verified {member.display_name}")

# Run the bot
bot.run(BOT_TOKEN)
