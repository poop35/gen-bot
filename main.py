import discord
from discord.ext import commands
import aiosqlite
import os
import json

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise Exception("DISCORD_TOKEN missing")

with open("config.json", "r") as f:
    config = json.load(f)

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


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


# ---------------- CHECK PERMISSION ----------------

def is_admin(member: discord.Member):
    return any(role.id in config["admin_role_ids"] for role in member.roles)


# ---------------- /HELP ----------------

@bot.tree.command(name="help")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "/gen\n/stock\n/services\n/addstock\n/addservice"
    )


# ---------------- /SERVICES ----------------

@bot.tree.command(name="services")
async def services(interaction: discord.Interaction):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT name FROM services") as c:
            rows = await c.fetchall()

    if not rows:
        return await interaction.response.send_message("No services found.")

    await interaction.response.send_message("\n".join([r[0] for r in rows]))


# ---------------- /ADD SERVICE ----------------

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


# ---------------- /STOCK ----------------

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


# ---------------- /ADD STOCK ----------------

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

    await interaction.response.send_message(
        f"Added {added} accounts to {service}"
    )


# ---------------- /GEN (FULL SYSTEM) ----------------

@bot.tree.command(name="gen")
async def gen(interaction: discord.Interaction, service: str):

    guild = interaction.guild
    member = interaction.user

    free_role = guild.get_role(config["free_role_id"])
    premium_role = guild.get_role(config["premium_role_id"])

    channel_id = interaction.channel.id

    is_premium = premium_role in member.roles
    is_free = free_role in member.roles

    # CHANNEL CHECK
    if is_premium:
        if channel_id != config["premium_gen_channel_id"]:
            return await interaction.response.send_message("Use premium gen channel.")

    if is_free:
        if channel_id != config["free_gen_channel_id"]:
            return await interaction.response.send_message("Use free gen channel.")

    if not is_free and not is_premium:
        return await interaction.response.send_message("No gen role.")

    # STOCK CHECK
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT account FROM stock WHERE service = ? LIMIT 1",
            (service,)
        ) as c:
            row = await c.fetchone()

        if not row:
            return await interaction.response.send_message("Out of stock.")

        account = row[0]

        await db.execute(
            "DELETE FROM stock WHERE account = ?",
            (account,)
        )
        await db.commit()

    try:
        await member.send(f"{service} account:\n{account}")
        await interaction.response.send_message("Sent to DMs.")
    except:
        await interaction.response.send_message("Enable DMs.")


# ---------------- RUN ----------------

bot.run(TOKEN)
