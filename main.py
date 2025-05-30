from flask import Flask
from threading import Thread
import discord
import os
from discord.ext import commands
from discord.ui import Button, View

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
class VerifyButton(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild = interaction.guild
        role_member = guild.get_role(ROLE_MEMBER_ID)

        if role_member in member.roles:
            await interaction.response.send_message("You are already verified.", ephemeral=True)
        else:
            try:
                await member.add_roles(role_member)
                await interaction.response.send_message("✅ You have been verified and granted access!", ephemeral=True)
                try:
                    await member.send(f"Welcome to {guild.name}! You are now verified.")
                except:
                    pass
            except Exception as e:
                await interaction.response.send_message(f"❌ An error occurred: {e}", ephemeral=True)

# --- TICKET SYSTEM ---
class TicketView(View):
    def __init__(self, jeu):
        super().__init__(timeout=None)
        self.add_item(OpenTicketButton(jeu))


class OpenTicketButton(Button):
    def __init__(self, jeu):
        self.jeu = jeu
        super().__init__(label=f"🎫 Open a Ticket ({jeu})", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        # Nettoie le nom du jeu pour en faire un nom de salon valide
        sanitized_game = re.sub(r'[^a-zA-Z0-9]', '-', self.jeu.lower())
        ticket_channel_name = f"ticket-{sanitized_game}-{user.name}".lower()

        # Vérifie si l'utilisateur a déjà un ticket pour ce jeu
        existing_channel = discord.utils.get(guild.text_channels, name=ticket_channel_name)
        if existing_channel:
            await interaction.response.send_message(
                f"❗ Tu as déjà un ticket ouvert : {existing_channel.mention}", ephemeral=True
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
            reason=f"Ticket ouvert pour {self.jeu}"
        )

        await ticket_channel.send(
            f"{user.mention}, bienvenue dans ton ticket pour **{self.jeu}** ! Un membre du staff va bientôt t'aider.",
            view=CloseTicketView()
        )

        await interaction.response.send_message(
            f"✅ Ton ticket a été créé : {ticket_channel.mention}", ephemeral=True
        )


class CloseTicketButton(Button):
    def __init__(self):
        super().__init__(label="❌ Fermer le ticket", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        await interaction.channel.delete(reason="Ticket fermé")


class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CloseTicketButton())


@bot.command()
@commands.has_permissions(administrator=True)
async def setup_tickets(ctx, *, jeu):
    embed = discord.Embed(
        title=f"🎟️ {jeu} - Tickets",
        description="Clique sur le bouton ci-dessous pour créer un ticket.\nUn membre du staff te répondra bientôt.",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed, view=TicketView(jeu))

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}!")

    bot.add_view(VerifyButton())

    channel = bot.get_channel(VERIFY_CHANNEL_ID)
    if channel is None:
        print("⚠️ Verify channel not found.")
        return

    async for message in channel.history(limit=50):
        if message.author == bot.user and message.components:
            print("✅ Verification message already exists.")
            break
    else:
        view = VerifyButton()
        await channel.send(
            "Please verify yourself by clicking the button below to gain full access to the server.",
            view=view
        )
        print("✅ Verification message sent.")

# --- MAIN ---
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)  # 👈 Utilise la variable sécurisée