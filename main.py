from flask import Flask
from threading import Thread
import discord
import os
from discord.ext import commands
from discord.ui import Button, View
import re
# --- KEEP ALIVE (Flask) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CONFIG ---
TOKEN = os.getenv("DISCORD_TOKEN")  # 🔐 Token sécurisé via Replit Secrets

VERIFY_CHANNEL_ID = 1377699763562221708
ROLE_MEMBER_ID = 1377787579717521481

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- VERIFY BUTTON ---
ROLE_VERIFIED_ID = 1378464100614537378
ROLE_MEMBER_ID = 1377787579717521481
RULES_CHANNEL_ID = 1377699766565343405

class VerifyButton(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild = interaction.guild
        role_verified = guild.get_role(ROLE_VERIFIED_ID)

        if role_verified in member.roles:
            await interaction.response.send_message("You are already verified.", ephemeral=True)
        else:
            try:
                await member.add_roles(role_verified)
                await interaction.response.send_message(
                    "✅ You have received the Verified role! Please go to the #rules channel and react with ✅ to get full access.",
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(f"❌ An error occurred: {e}", ephemeral=True)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.channel_id != RULES_CHANNEL_ID:
        return

    if str(payload.emoji) != "✅":
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)

    if member is None or member.bot:
        return

    role_member = guild.get_role(ROLE_MEMBER_ID)
    if role_member in member.roles:
        return

    try:
        await member.add_roles(role_member)
        await member.send("🎉 You now have full access to the server. Welcome!")
    except Exception as e:
        print(f"Error adding Members role: {e}")

# --- TICKET SYSTEM ---
class TicketView(View):
    def __init__(self, game):
        super().__init__(timeout=None)
        self.add_item(OpenTicketButton(game))

class OpenTicketButton(Button):
    def __init__(self, game):
        self.game = game
        super().__init__(label=f"🎫 Open a Ticket ({game})", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        # Sanitize the game name for channel naming
        sanitized_game = re.sub(r'[^a-zA-Z0-9]', '-', self.game.lower())
        ticket_channel_name = f"ticket-{sanitized_game}-{user.name}".lower()

        # Check if user already has a ticket channel for this game
        existing_channel = discord.utils.get(guild.text_channels, name=ticket_channel_name)
        if existing_channel:
            await interaction.response.send_message(
                f"❗ You already have an open ticket: {existing_channel.mention}", ephemeral=True
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        ticket_channel = await guild.create_text_channel(
            name=ticket_channel_name,
            overwrites=overwrites,
            reason=f"Ticket opened for {self.game}"
        )

        await ticket_channel.send(
            f"{user.mention}, welcome to your ticket for **{self.game}**! A staff member will assist you shortly.",
            view=CloseTicketView()
        )

        await interaction.response.send_message(
            f"✅ Your ticket has been created: {ticket_channel.mention}", ephemeral=True
        )

class CloseTicketButton(Button):
    def __init__(self):
        super().__init__(label="❌ Close Ticket", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        await interaction.channel.delete(reason="Ticket closed")

class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CloseTicketButton())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_tickets(ctx, *, game):
    embed = discord.Embed(
        title=f"🎟️ {game} - Tickets",
        description="Click the button below to create a ticket.\nA staff member will assist you shortly.",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed, view=TicketView(game))

# --- WELCOME SYSTEM ---
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    # IDs
    ROLE_MEMBER_ID = 1377787579717521481
    WELCOME_CHANNEL_ID = 1377786407283724368

    role_member = after.guild.get_role(ROLE_MEMBER_ID)

    # Vérifie si le membre vient de recevoir le rôle "Members"
    if role_member and role_member not in before.roles and role_member in after.roles:
        channel = after.guild.get_channel(WELCOME_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=f"🎉 Welcome {after.name}!",
                description="Welcome and thank you for joining the server!\nFeel free to explore and enjoy your time here 😊",
                color=discord.Color.green()
            )
            embed.set_image(url="https://www.motionworship.com/thumb/Announcements/ColorWaveWelcomeHD.jpg")
            await channel.send(embed=embed)
# --- EVENTS ---
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    # IDs
    ROLE_MEMBER_ID = 1377787579717521481
    WELCOME_CHANNEL_ID = 1377786407283724368

    role_member = after.guild.get_role(ROLE_MEMBER_ID)

    # Vérifie si le membre vient de recevoir le rôle "Members"
    if role_member and role_member not in before.roles and role_member in after.roles:
        channel = after.guild.get_channel(WELCOME_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="🌟 Welcome to the server!",
                description=f"Hey {after.mention} 👋\n\nWelcome and thank you for joining **{after.guild.name}**!\nFeel free to explore the channels, meet new people, and enjoy your stay! 🎉",
                color=discord.Color.fuchsia()
            )
            embed.set_image(url="https://www.motionworship.com/thumb/Announcements/ColorWaveWelcomeHD.jpg")
            await channel.send(embed=embed)

# --- MAIN ---
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)  # 👈 Utilise la variable sécurisée