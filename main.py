import discord
from discord.ext import commands
import json
import os
import aiosqlite

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise Exception("DISCORD_TOKEN is missing in Railway variables")

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


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
    print("🔥 BOT FILE IS RUNNING")
    print(f"Nova Market V2 online as {bot.user}")


# ---------------- HELP ----------------
@bot.command()
async def help(ctx):
    await ctx.send("Commands: !gen, !stock, !services, !addstock")


# ---------------- SERVICES ----------------
@bot.command()
async def services(ctx):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT name FROM services") as c:
            rows = await c.fetchall()

    if not rows:
        return await ctx.send("No services found.")

    await ctx.send("\n".join([r[0] for r in rows]))


# ---------------- STOCK ----------------
@bot.command()
async def stock(ctx):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute("SELECT service, COUNT(*) FROM stock GROUP BY service") as c:
            rows = await c.fetchall()

    if not rows:
        return await ctx.send("No stock found.")

    await ctx.send("\n".join([f"{r[0]}: {r[1]}" for r in rows]))


# ---------------- ADD STOCK ----------------
@bot.command()
async def addstock(ctx, service: str):
    if not ctx.message.attachments:
        return await ctx.send("Upload a .txt file.")

    file = ctx.message.attachments[0]
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

    await ctx.send(f"Added {added} accounts to {service}")


# ---------------- GEN ----------------
@bot.command()
async def gen(ctx, service: str):
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT account FROM stock WHERE service = ? LIMIT 1",
            (service,)
        ) as c:
            row = await c.fetchone()

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
