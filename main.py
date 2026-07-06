import discord
from discord.ext import commands
import aiosqlite
import os
import json

# ---------------- TOKEN ----------------
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise Exception("DISCORD_TOKEN missing in Railway variables")


# ---------------- CONFIG ----------------
with open("config.json", "r") as f:
    config = json.load(f)


# ---------------- INTENTS ----------------
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)


# ---------------- DB ----------------
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


# ---------------- HELP ----------------
@bot.tree.command(name="help")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "/gen\n/services\n/stock\n/addservice\n/addstock",
        ephemeral=True
    )


# ---------------- SERVICES ----------------
@bot.tree.command(name="services")
async def services(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT name FROM services") as c:
            rows = await c.fetchall()

    if not rows:
        return await interaction.followup.send("No services found.")

    await interaction.followup.send("\n".join([r[0] for r in rows]))


# ---------------- STOCK ----------------
@bot.tree.command(name="stock")
async def stock(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT service, COUNT(*) FROM stock GROUP BY service"
        ) as c:
            rows = await c.fetchall()

    if not rows:
        return await interaction.followup.send("No stock.")

    await interaction.followup.send(
        "\n".join([f"{r[0]}: {r[1]}" for r in rows])
    )


# ---------------- ADD SERVICE ----------------
@bot.tree.command(name="addservice")
async def addservice(interaction: discord.Interaction, name: str):

    await interaction.response.defer(ephemeral=True)

    if not is_admin(interaction.user):
        return await interaction.followup.send("No permission.")

    async with aiosqlite.connect("database.db") as db:
        try:
            await db.execute(
                "INSERT INTO services (name) VALUES (?)",
                (name,)
            )
            await db.commit()

            await interaction.followup.send(f"Added service: {name}")

        except:
            await interaction.followup.send("Service already exists.")


# ---------------- ADD STOCK ----------------
@bot.tree.command(name="addstock")
async def addstock(
    interaction: discord.Interaction,
    service: str,
    file: discord.Attachment
):

    await interaction.response.defer(ephemeral=True)

    if not is_admin(interaction.user):
        return await interaction.followup.send("No permission.")

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

    await interaction.followup.send(f"Added {added} accounts to {service}")


# ---------------- GEN (DROPDOWN SAFE VERSION) ----------------
class GenSelect(discord.ui.Select):
    def __init__(self, services):
        options = [
            discord.SelectOption(label=s, value=s)
            for s in services
        ]

        super().__init__(
            placeholder="Select a service",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        service = self.values[0]

        async with aiosqlite.connect("database
