import discord
from discord.ext import commands
import json
import os
import aiosqlite
import time

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise Exception("DISCORD_TOKEN is not set in Railway!")

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


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


# ---------------- EVENTS ----------------
@bot.event
async def on_ready():
    await setup_db()
    print(f"Nova Market V2 is online as {bot.user}")


# ---------------- HELP COMMAND ----------------
@bot.command()
async def help(ctx):
    await ctx.send("""
**Nova Market V2**
Commands:
!gen <service>
!stock
!services
""")


# ---------------- SERVICES ----------------
@bot.command()
async def services(ctx):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT name FROM services") as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return await ctx.send("No services found.")

    text = "\n".join([f"- {r[0]}" for r in rows])
    await ctx.send(f"**Services:**\n{text}")


# ---------------- STOCK ----------------
@bot.command()
async def stock(ctx):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT service, COUNT(*) FROM stock GROUP BY service") as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return await ctx.send("No stock found.")

    text = "\n".join([f"{r[0]}: {r[1]}" for r in rows])
    await ctx.send(f"**Stock:**\n{text}")


# ---------------- ADD STOCK (simple version for now) ----------------
@bot.command()
async def addstock(ctx, service: str):
    if not ctx.message.attachments:
        return await ctx.send("Attach a .txt file.")

    file = ctx.message.attachments[0]
    content = await file.read()
    lines = content.decode().splitlines()

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

    await ctx.send(f"Added {added} accounts to {service}")


# ---------------- GENERATOR (basic safe version) ----------------
@bot.command()
async def gen(ctx, service: str):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT account FROM stock WHERE service = ? LIMIT 1",
            (service,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return await ctx.send("Out of stock.")

        account = row[0]

        await db.execute(
            "DELETE FROM stock WHERE account = ?",
            (account,)
        )

        await db.commit()

    try:
        await ctx.author.send(f"Account: {account}")
        await ctx.send("Check DMs!")
    except:
        await ctx.send("Enable DMs.")


bot.run(TOKEN)
