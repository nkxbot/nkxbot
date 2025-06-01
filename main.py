from flask import Flask
from threading import Thread
import discord
import os
from discord.ext import commands
from discord.ui import Button, View
from datetime import datetime, timedelta
import re
import asyncio
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

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_verify(ctx):
    embed = discord.Embed(
        title="🔐 Verification",
        description="Click the **Verify** button below to get the Verified role!",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=VerifyButton())

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

# --- SERVER INVITE SYSTEM ---
INVITE_WELCOME_CHANNEL_ID = 1377699765432750272  # Salon pour les messages d'invitation

invites = {}

@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")
    global invites
    for guild in bot.guilds:
        invites[guild.id] = await guild.invites()

@bot.event
async def on_member_join(member):
    await asyncio.sleep(1)  # Delay to ensure invite data is updated
    guild = member.guild
    channel = guild.get_channel(INVITE_WELCOME_CHANNEL_ID)
    if channel is None:
        print("⚠️ Invite welcome channel not found.")
        return

    current_invites = await guild.invites()
    old_invites = invites.get(guild.id, [])

    used_invite = None
    for invite in current_invites:
        old_invite = discord.utils.get(old_invites, code=invite.code)
        if old_invite and invite.uses > old_invite.uses:
            used_invite = invite
            break

    invites[guild.id] = current_invites

    if used_invite:
        embed = discord.Embed(
            title="🎉 A New Member Has Joined!",
            description=(
                f"Thanks {used_invite.inviter.mention} for inviting {member.mention}!\n\n"
                "We hope they enjoy their stay here! 💜"
            ),
            color=0xFF77FF
        )
        embed.set_image(url="https://www.motionworship.com/thumb/Announcements/ColorWaveWelcomeHD.jpg")
        embed.set_footer(text="Motion Worship")

        await channel.send(embed=embed)

# --- ROLE-BASED WELCOME SYSTEM ---
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    ROLE_MEMBER_ID = 1377787579717521481
    ROLE_WELCOME_CHANNEL_ID = 1377786407283724368  # Salon pour message quand un membre devient "Members"

    role_member = after.guild.get_role(ROLE_MEMBER_ID)

    if role_member and role_member not in before.roles and role_member in after.roles:
        channel = after.guild.get_channel(ROLE_WELCOME_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="🌟 Welcome to the server!",
                description=f"Hey {after.mention} 👋\n\nWelcome and thank you for joining **{after.guild.name}**!\nFeel free to explore the channels, meet new people, and enjoy your stay! 🎉",
                color=discord.Color.fuchsia()
            )
            embed.set_image(url="https://www.motionworship.com/thumb/Announcements/ColorWaveWelcomeHD.jpg")
            await channel.send(embed=embed)
# --- INVITE TRACKER SYSTEM ---
INVITE_CHECK_CHANNEL_ID = 1377699780720853024  # Salon réservé à !invite et !topinvites

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == INVITE_CHECK_CHANNEL_ID:
        allowed_commands = ["!invite", "!topinvites"]
        if not any(message.content.startswith(cmd) for cmd in allowed_commands):
            try:
                await message.delete()
                warning = await message.channel.send(f"{message.author.mention} ❌ Only the `!invite` and `!topinvites` commands are allowed in this channel.")
                await asyncio.sleep(3)
                await warning.delete()
            except Exception as e:
                print(f"Failed to delete or warn: {e}")
            return

    await bot.process_commands(message)

@bot.command(name="invite")
async def check_invites(ctx):
    if ctx.channel.id != INVITE_CHECK_CHANNEL_ID:
        return  # Ignore si pas dans le bon salon

    total_invites = 0
    try:
        invites_list = await ctx.guild.invites()
        for invite in invites_list:
            if invite.inviter and invite.inviter.id == ctx.author.id:
                total_invites += invite.uses
    except Exception as e:
        await ctx.send(f"⚠️ Unable to retrieve invites: {e}")
        return

    embed = discord.Embed(
        title="📨 Invite Tracker",
        description=f"Hey {ctx.author.mention}!\n\nYou currently have **{total_invites} invitation(s)** on the server.",
        color=discord.Color.orange()
    )
    embed.set_footer(text="Keep sharing your invite link to gain more!")
    await ctx.send(embed=embed)

@bot.command(name="topinvites")
async def top_invites(ctx):
    try:
        invites = await ctx.guild.invites()
        inviter_stats = {}

        for invite in invites:
            if invite.inviter:
                inviter = invite.inviter
                inviter_stats[inviter] = inviter_stats.get(inviter, 0) + invite.uses

        top_invites = sorted(inviter_stats.items(), key=lambda x: x[1], reverse=True)[:5]

        description = ""
        for i, (inviter, uses) in enumerate(top_invites, 1):
            description += f"**{i}.** {inviter.mention} → **{uses} invite(s)**\n"

        embed = discord.Embed(
            title="🏆 Top Inviters",
            description=description or "No invites found.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"⚠️ Could not fetch top inviters: {e}")
        # Message automatique s'ils atteignent 10 invitations
        if total_invites == 10:
            congrats_embed = discord.Embed(
                title="🎉 Congratulations!",
                description=f"{ctx.author.mention} just reached **10 invites**! You're on fire 🔥",
                color=discord.Color.orange()
            )
            congrats_embed.set_footer(text="Keep it up and reach the next milestone!")
            await ctx.send(embed=congrats_embed)
# --- GIVEAWAY SYSTEM ---
GIVEAWAY_CHANNEL_ID = 1377699770390286417  # Salon des giveaways

class ParticipateButton(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Participate", style=discord.ButtonStyle.green, emoji="🎁", custom_id="giveaway_participate")
    async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ You're now participating in the giveaway!", ephemeral=True)

@bot.command(name="setup_giveaway")
@commands.has_permissions(administrator=True)
async def setup_giveaway(ctx):
    try:
        await ctx.message.delete()
    except:
        pass

    try:
        await ctx.author.send("📨 Let's create a giveaway!\nWhat is the **giveaway message**?")
    except discord.Forbidden:
        return await ctx.send(f"{ctx.author.mention}, I couldn't DM you! Please enable your DMs and try again.")

    def check(m):
        return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)

    try:
        msg_question = await bot.wait_for("message", check=check, timeout=120)
        await ctx.author.send("🎁 What is the **prize**?")
        prize_question = await bot.wait_for("message", check=check, timeout=120)
        await ctx.author.send("⏳ What is the **duration** (e.g., `10m`, `1h`, `2d`) ?")
        duration_question = await bot.wait_for("message", check=check, timeout=120)
        await ctx.author.send("📋 Do participants need to meet any **requirements** to be eligible? (Send `no` if none)")
        requirement_question = await bot.wait_for("message", check=check, timeout=120)
    except asyncio.TimeoutError:
        return await ctx.author.send("⌛ Timeout. Giveaway setup canceled.")

    message = msg_question.content
    prize = prize_question.content
    duration_str = duration_question.content.lower()
    requirements = requirement_question.content

    time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    duration_seconds = 0
    if duration_str[-1] in time_units:
        try:
            duration_seconds = int(duration_str[:-1]) * time_units[duration_str[-1]]
        except ValueError:
            return await ctx.author.send("❌ Invalid duration format.")
    else:
        return await ctx.author.send("❌ Invalid duration format. Use `s`, `m`, `h`, or `d`.")

    description = f"**{message}**\n\n🎁 **Prize:** {prize}\n⏳ Ends in: {duration_str}"
    if requirements.lower() != "no":
        description += f"\n📌 **Requirements:** {requirements}"

    embed = discord.Embed(
        title="🎉 New Giveaway!",
        description=description,
        color=discord.Color.blue()
    )
    embed.set_footer(text="Click the button below to participate!")

    giveaway_channel = bot.get_channel(GIVEAWAY_CHANNEL_ID)
    if giveaway_channel:
        await giveaway_channel.send(embed=embed, view=ParticipateButton())
        await ctx.author.send("✅ Giveaway posted!")
    else:
        await ctx.author.send("❌ I couldn't find the giveaway channel.")

# --- MAIN ---
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)  # 👈 Utilise la variable sécurisée