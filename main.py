import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import json

# ---------------- TOKEN ----------------
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise Exception("DISCORD_TOKEN missing in Railway")

# ---------------- CONFIG ----------------
with open("config.json", "r") as f:
    config = json.load(f)

# ---------------- INTENTS ----------------
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ---------------- DATABASE ----------------
async def setup_db():
    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            service TEXT,
            account TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS services (
            name TEXT UNIQUE
        )
        """)
        await db.commit()


# ---------------- READY ----------------
@bot.event
async def on_ready():
    await setup_db()
    await bot.tree.sync()
    print(f"🔥 Nova Market V2 online as {bot.user}")


# ---------------- ADMIN CHECK ----------------
def is_admin(member: discord.Member):
    return any(role.id in config["admin_role_ids"] for role in member.roles)


# ---------------- STOCK SYSTEM ----------------
async def get_services():
    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT name FROM services") as c:
            rows = await c.fetchall()
    return [r[0] for r in rows]


# ---------------- DROPDOWN ----------------
class ServiceSelect(discord.ui.Select):
    def __init__(self, bot, services):
        self.bot = bot

        options = [
            discord.SelectOption(label=s, value=s)
            for s in services
        ]

        super().__init__(
            placeholder="Select a service to generate",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        service = self.values[0]
        member = interaction.user
        guild = interaction.guild

        free_role = guild.get_role(config["free_role_id"])
        premium_role = guild.get_role(config["premium_role_id"])

        is_free = free_role in member.roles
        is_premium = premium_role in member.roles

        # CHANNEL CHECK
        if is_free and interaction.channel.id != config["free_gen_channel_id"]:
            return await interaction.response.send_message("Use free gen channel.", ephemeral=True)

        if is_premium and interaction.channel.id != config["premium_gen_channel_id"]:
            return await interaction.response.send_message("Use premium gen channel.", ephemeral=True)

        # SERVICE PERMISSION CHECK
        if is_free and service not in config["free_services"]:
            return await interaction.response.send_message(
                "❌ You do not have permission to gen this service.",
                ephemeral=True
            )

        if is_premium and service not in (config["free_services"] + config["premium_services"]):
            return await interaction.response.send_message(
                "❌ You do not have permission to gen this service.",
                ephemeral=True
            )

        # STOCK
        async with aiosqlite.connect("database.db") as db:
            async with db.execute(
                "SELECT account FROM stock WHERE service = ? LIMIT 1",
                (service,)
            ) as c:
                row = await c.fetchone()

            if not row:
                return await interaction.response.send_message("❌ Out of stock.", ephemeral=True)

            account = row[0]

            await db.execute(
                "DELETE FROM stock WHERE account = ?",
                (account,)
            )
            await db.commit()

        try:
            await member.send(f"{service} account:\n{account}")
            await interaction.response.send_message("📩 Sent to DMs!", ephemeral=True)
        except:
            await interaction.response.send_message("Enable DMs.", ephemeral=True)


class GenView(discord.ui.View):
    def __init__(self, bot, services):
        super().__init__(timeout=60)
        self.add_item(ServiceSelect(bot, services))


# ---------------- SLASH COMMANDS ----------------

@bot.tree.command(name="gen")
async def gen(interaction: discord.Interaction):
    services = await get_services()

    if not services:
        return await interaction.response.send_message("No services available.")

    await interaction.response.send_message(
        "Select a service:",
        view=GenView(bot, services),
        ephemeral=True
    )


@bot.tree.command(name="services")
async def services(interaction: discord.Interaction):
    services = await get_services()

    if not services:
        return await interaction.response.send_message("No services found.")

    await interaction.response.send_message("\n".join(services))


@bot.tree.command(name="stock")
async def stock(interaction: discord.Interaction):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT service, COUNT(*) FROM stock GROUP BY service"
        ) as c:
            rows = await c.fetchall()

    if not rows:
        return await interaction.response.send_message("No stock.")

    await interaction.response.send_message(
        "\n".join([f"{r[0]}: {r[1]}" for r in rows])
    )


@bot.tree.command(name="addservice")
async def addservice(interaction: discord.Interaction, name: str):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("No permission.")

    async with aiosqlite.connect("database.db") as db:
        try:
            await db.execute(
                "INSERT INTO services (name) VALUES (?)",
                (name,)
            )
            await db.commit()
            await interaction.response.send_message(f"Added service {name}")
        except:
            await interaction.response.send_message("Service already exists.")


@bot.tree.command(name="addstock")
async def addstock(
    interaction: discord.Interaction,
    service: str,
    file: discord.Attachment
):

    if not is_admin(interaction.user):
        return await interaction.response.send_message("No permission.")

    data = await file.read()
    lines = data.decode().splitlines()

    added = 0

    async with aiosqlite.connect("database.db") as db:
        for line in lines:
            line = line.strip()
            if line:
                await db.execute(
                    "INSERT INTO stock (service, account) VALUES (?, ?)",
                    (service, line)
                )
                added += 1

        await db.commit()

    await interaction.response.send_message(f"Added {added} accounts")


# ---------------- RUN ----------------
bot.run(TOKEN)
