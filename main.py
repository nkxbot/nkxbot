from flask import Flask
from threading import Thread
import discord
import os
import time
import random
from collections import defaultdict
from discord import app_commands
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
TOKEN = os.getenv("DISCORD_TOKEN")

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

# IDs à personnaliser si nécessaire
RULES_CHANNEL_ID = 1377699766565343405
MEMBERS_ROLE_ID = 1377787579717521481

class AcceptRulesView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Accept Rules", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(MEMBERS_ROLE_ID)
        if role in interaction.user.roles:
            await interaction.response.send_message("You already have access to the server.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ You have accepted the rules and now have full access!", ephemeral=True)

@bot.command()
async def setup_rules(ctx):
    if ctx.channel.id != RULES_CHANNEL_ID:
        await ctx.send(f"❌ Please use this command in <#{RULES_CHANNEL_ID}>.")
        return

    embed = discord.Embed(
        title="📜 Server Rules",
        description="By clicking the button below, you agree to follow all server rules.\n\nClick the green button to gain full access to the server.",
        color=discord.Color.green()
    )
    embed.set_footer(text="Thank you for respecting the rules.")

    await ctx.send(embed=embed, view=AcceptRulesView())

# Obligatoire pour que le bouton soit actif même après redémarrage
@bot.event
async def on_ready():
    bot.add_view(AcceptRulesView())
    print(f"Bot connecté en tant que {bot.user}")

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
        embed.set_image(url="https://media.tenor.com/vJuESVyU34YAAAAM/you-are-invited-invitation.gif")
        
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
        allowed_commands = ["!invite", "!topinvites", "!checkinvites"]  # Ajout de !checkinvites ici
        if not any(message.content.startswith(cmd) for cmd in allowed_commands):
            try:
                await message.delete()
                warning = await message.channel.send(f"{message.author.mention} ❌ Only the `!invite`, `!topinvites` and `!checkinvites` commands are allowed in this channel.")
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
OWNER_ID = 1197161364913913918

@bot.command(name="checkinvites")
async def check_invites_of_user(ctx, member: discord.Member = None):
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ You are not authorized to use this command.")

    if not member:
        return await ctx.send("⚠️ Please mention a member to check their invites.")

    total_invites = 0
    invited_users = []

    try:
        invites_list = await ctx.guild.invites()
        for invite in invites_list:
            if invite.inviter and invite.inviter.id == member.id:
                total_invites += invite.uses
                if invite.uses > 0:
                    # Impossible de récupérer les noms directs via l'invite, donc on ajoute juste une info texte
                    invited_users.append(f"🔗 Code `{invite.code}` → **{invite.uses}** uses")

    except Exception as e:
        return await ctx.send(f"⚠️ Unable to retrieve invites: {e}")

    description = f"{member.mention} currently has **{total_invites} invitation(s)**."
    if invited_users:
        description += "\n\n**Invite usage breakdown:**\n" + "\n".join(invited_users)
    else:
        description += "\n\nNo invite usage data found."

    embed = discord.Embed(
        title="🔎 Invite Check",
        description=description,
        color=discord.Color.orange()
    )
    embed.set_footer(text="Invite checker (admin only)")
    await ctx.send(embed=embed)
# --- GIVEAWAY SYSTEM ---
GIVEAWAY_CHANNEL_ID = 1377699770390286417  # Salon des giveaways
OWNER_ID = 1197161364913913918

giveaways = {}  # Stocke les giveaways avec leur data : {message_id: {"end": timestamp, "participants": set(), "prize": str}}

class ParticipateButton(View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="Participate", style=discord.ButtonStyle.green, emoji="🎁", custom_id="giveaway_participate")
    async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if self.message_id in giveaways:
            giveaways[self.message_id]["participants"].add(user_id)
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
    if duration_str[-1] not in time_units:
        return await ctx.author.send("❌ Invalid duration format. Use `s`, `m`, `h`, or `d`.")
    try:
        duration_seconds = int(duration_str[:-1]) * time_units[duration_str[-1]]
    except ValueError:
        return await ctx.author.send("❌ Invalid duration format.")

    end_time = datetime.utcnow() + timedelta(seconds=duration_seconds)
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
    if not giveaway_channel:
        return await ctx.author.send("❌ I couldn't find the giveaway channel.")
    giveaway_message = await giveaway_channel.send(embed=embed, view=ParticipateButton(None))
    giveaways[giveaway_message.id] = {
        "end": end_time,
        "participants": set(),
        "prize": prize,
        "channel": giveaway_channel.id
    }
    view = ParticipateButton(giveaway_message.id)
    await giveaway_message.edit(view=view)

    await ctx.author.send(f"✅ Giveaway successfully created in {giveaway_channel.mention}!")


    # Lancer la tâche de fin de giveaway
    async def end_giveaway(message_id):
        await asyncio.sleep(duration_seconds)
        data = giveaways.get(message_id)
        if not data:
            return

        participants = data["participants"]
        prize = data["prize"]
        channel = bot.get_channel(data["channel"])

        if participants:
            winner_id = random.choice(list(participants))
            winner = channel.guild.get_member(winner_id)
            result_embed = discord.Embed(
                title="🎉 Giveaway Ended!",
                description=f"🏆 **Winner:** {winner.mention if winner else 'Unknown'}\n🎁 **Prize:** {prize}",
                color=discord.Color.purple()
            )
            await channel.send(embed=result_embed)
        else:
            await channel.send("😕 No participants. No winner this time.")

        del giveaways[message_id]

    bot.loop.create_task(end_giveaway(giveaway_message.id))

@bot.command(name="timer")
async def check_timer(ctx):
    if ctx.author.id != OWNER_ID:
        return
    now = datetime.utcnow()
    for msg_id, data in giveaways.items():
        remaining = data["end"] - now
        if remaining.total_seconds() > 0:
            minutes, seconds = divmod(int(remaining.total_seconds()), 60)
            hours, minutes = divmod(minutes, 60)
            await ctx.author.send(f"⏳ Giveaway `{msg_id}` ends in {hours}h {minutes}m {seconds}s.")
        else:
            await ctx.author.send(f"⏳ Giveaway `{msg_id}` is already over.")

@bot.command(name="reroll")
async def reroll_giveaway(ctx, message_id: int):
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ You are not authorized to reroll giveaways.", delete_after=5)

    data = giveaways.get(message_id)
    if not data or not data["participants"]:
        return await ctx.send("❌ No participants found or invalid message ID.", delete_after=5)

    winner_id = random.choice(list(data["participants"]))
    winner = ctx.guild.get_member(winner_id)
    if winner:
        await ctx.send(f"🔄 New winner for giveaway `{message_id}`: {winner.mention} 🏆")
    else:
        await ctx.send("❌ Could not find the new winner.", delete_after=5)

@bot.command(name="entries")
async def entries(ctx, message_id: int):
            if message_id not in giveaways:
                return await ctx.send("❌ No giveaway found with that message ID.")

            participant_count = len(giveaways[message_id]["participants"])
            prize = giveaways[message_id]["prize"]

            embed = discord.Embed(
                title="🎟️ Giveaway Entries",
                description=f"**Prize:** {prize}\n👥 **Entries:** {participant_count}",
                color=discord.Color.blurple()
            )
            await ctx.send(embed=embed)
async def giveaway_checker():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.utcnow().timestamp()
        to_remove = []

        for message_id, data in giveaways.items():
            if now >= data["end"]:
                channel = bot.get_channel(GIVEAWAY_CHANNEL_ID)
                try:
                    message = await channel.fetch_message(message_id)
                except:
                    continue

                participants = list(data["participants"])
                if participants:
                    winner_id = random.choice(participants)
                    winner = await bot.fetch_user(winner_id)
                    result_text = f"🎉 Congratulations {winner.mention}! You won **{data['prize']}**!"
                else:
                    result_text = "❌ No participants. Giveaway cancelled."

                result_embed = discord.Embed(
                    title="🎁 Giveaway Ended",
                    description=result_text,
                    color=discord.Color.red()
                )
                await channel.send(embed=result_embed)
                to_remove.append(message_id)

        for message_id in to_remove:
            del giveaways[message_id]

        await asyncio.sleep(30)  # Vérifie toutes les 30 secondes

# --- DELETE SYSTEM ---
OWNER_ID = 1197161364913913918

@bot.command(name="delete")
async def delete_message(ctx, message_id: int):
            if ctx.author.id != OWNER_ID:
                await ctx.send("❌ You are not authorized to use this command.", delete_after=5)
                return

            found = False
            for channel in ctx.guild.text_channels:
                try:
                    msg = await channel.fetch_message(message_id)
                    await msg.delete()
                    confirmation = await ctx.send(f"✅ Message `{message_id}` deleted from #{channel.name}.", delete_after=5)
                    found = True
                    break
                except discord.NotFound:
                    continue
                except discord.Forbidden:
                    continue
                except Exception as e:
                    print(f"Error in {channel.name}: {e}")
                    continue

            if not found:
                await ctx.send("❌ Message not found or I don't have access to delete it.", delete_after=5)

            # Supprime la commande elle-même
            try:
                await ctx.message.delete()
            except Exception as e:
                print(f"Could not delete command message: {e}")
@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")
    global invites
    for guild in bot.guilds:
        invites[guild.id] = await guild.invites()

    bot.loop.create_task(giveaway_checker())
    
# --- UTILITARY SYSTEM ---
@bot.command(name="ping")
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: `{latency}ms`")

OWNER_ID = 1197161364913913918  # Ton ID

@bot.command(name="userinfo")
async def userinfo(ctx, member: discord.Member = None):
    # Si l'utilisateur n'est pas le propriétaire et tente de mentionner quelqu'un
    if member and ctx.author.id != OWNER_ID:
        await ctx.send("❌ You are not authorized to view info about other users.")
        return

    member = member or ctx.author
    roles = [role.mention for role in member.roles if role != ctx.guild.default_role]

    embed = discord.Embed(
        title=f"ℹ️ User Info: {member}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="🆔 ID", value=member.id, inline=True)
    embed.add_field(name="💬 Nickname", value=member.display_name, inline=True)
    embed.add_field(name="📅 Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M"), inline=False)
    embed.add_field(name="📅 Created Account", value=member.created_at.strftime("%Y-%m-%d %H:%M"), inline=False)
    embed.add_field(name=f"🎭 Roles [{len(roles)}]", value=", ".join(roles) or "None", inline=False)

    await ctx.send(embed=embed)

# --- MAIN ---
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)  # 👈 Utilise la variable sécurisée