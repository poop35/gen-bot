
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import time
import json
import os
TOKEN = os.getenv("TOKEN")
GUILD_ID = 1520475502278742237

SUB_ROLE_ID = 1520781371096698972

FREE_ROLE_ID = 1520781264934932490

MOD_ROLE_NAME = "Staff"

ADMIN_ROLE_NAME = "Trusted Staff"

DB_NAME = "database.db" 

GIF_URL = "https://cdn.discordapp.com/attachments/1520710523635896421/1522351273817669753/lp_image.gif" 

with open("config.json", "r") as f: 
    config = json.load(f)

PREMIUM_ROLE_ID = config["premium_role_id"]
FREE_SERVICES = [s.lower() for s in config["free_services"]]
PREMIUM_SERVICES = [s.lower() for s in config["premium_services"]]

FREE_GEN_CHANNEL_ID = config["free_gen_channel_id"]
PREMIUM_GEN_CHANNEL_ID = config["premium_gen_channel_id"]

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix="/",
    intents=intents
)

tree = bot.tree

async def setup_db():

    async with aiosqlite.connect(DB_NAME) as db:

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

        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            expires_at INTEGER
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS cooldown (
            service TEXT PRIMARY KEY,
            seconds INTEGER
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS user_cooldowns (
        user_id INTEGER,
        service TEXT,
        last_used INTEGER,
        PRIMARY KEY (user_id, service)
       )
       """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS custom_user_cooldown (
        user_id INTEGER PRIMARY KEY,
        cooldown_seconds INTEGER
        )
        """)

        await db.execute("""
        INSERT OR IGNORE INTO cooldown (service, seconds)
        VALUES (?, ?)
        """, ("free", 60))

        await db.commit()

def is_admin(member: discord.Member):

    return any(
        role.name in [ADMIN_ROLE_NAME, MOD_ROLE_NAME]
        for role in member.roles
    )

def wrong_channel(interaction):
    return interaction.channel.id not in (
        PREMIUM_GEN_CHANNEL_ID,
        FREE_GEN_CHANNEL_ID
    )

def make_embed(title, description, color):

    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )

    embed.set_footer(
        text="Made by Pf4k"
    )

    embed.set_image(
        url=GIF_URL
    )

    return embed

async def get_cooldown(service):

    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT seconds FROM cooldown WHERE service = ?",
            (service,)
        ) as cursor:

            row = await cursor.fetchone()

            return row[0] if row else 0
        
async def get_stock_count(service):

    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT COUNT(*) FROM stock WHERE service = ?",
            (service,)
        ) as cursor:

            row = await cursor.fetchone()

            return row[0]

def parse_duration(duration):

    duration = duration.strip().lower()

    if duration.isdigit():
        seconds = int(duration)
        return seconds if seconds > 0 else None

    durations = {
        "1day": 86400,
        "3days": 259200,
        "7days": 604800,
        "3weeks": 1814400,
        "1month": 2592000,
        "1year": 31536000
    }

    return durations.get(duration)

async def service_autocomplete(
    interaction: discord.Interaction,
    current: str
):

   async with aiosqlite.connect(DB_NAME) as db:
    async with db.execute(
        "SELECT name FROM services"
    ) as cursor:
        rows = await cursor.fetchall()

    return [
        app_commands.Choice(
            name=row[0],
            value=row[0]
        )
        for row in rows
        if current.lower() in row[0].lower()
    ][:25]

@tasks.loop(seconds=10)
async def check_expired():

    guild = bot.get_guild(GUILD_ID)

    if not guild:
        return

    now = int(time.time())

    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT user_id, expires_at FROM users"
        ) as cursor:

            rows = await cursor.fetchall()

        for user_id, expires_at in rows:

            if now >= expires_at:

                member = guild.get_member(user_id)

                if member:

                    role = guild.get_role(SUB_ROLE_ID)

                    if role in member.roles:

                        try:
                            await member.remove_roles(role)
                        except:
                            pass

                await db.execute(
                    "DELETE FROM users WHERE user_id = ?",
                    (user_id,)
                )

        await db.commit()

@bot.event
async def on_ready():
    await setup_db()

    guild = discord.Object(id=GUILD_ID)

    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)

    check_expired.start()

    print(f"Logged in as {bot.user}")

@tree.command(name="help")
async def helpcmd(interaction: discord.Interaction):

    embed = make_embed(
        "Gen Bot Commands",
        """
`/gen` - Generate account

`/stock` - Check stock

`/services` - View all services

`/time @user` - Subscription time

`/users` - Role user count

ADMIN & MOD:
`/addservice` - Add a service
`/servicedelete` - Delete a service
`/stockadd` - Add stock from .txt file
`/stockclear` - Clear stock for a service
`/addtime` - Add subscription time to user
`/removetime` - Remove subscription time from user
`/customcooldown` - Set user cooldown
        """,
        0x00ff99
    )

    await interaction.response.send_message(
        embed=embed
    )

@tree.command(name="addservice")
async def serviceadd(
    interaction: discord.Interaction,
    name: str
):

    if wrong_channel(interaction):

        return await interaction.response.send_message(
            f"Use <#{PREMIUM_GEN_CHANNEL_ID}> or <#{FREE_GEN_CHANNEL_ID}>",
            ephemeral=True
        )

    if not is_admin(interaction.user):
        return

    async with aiosqlite.connect(DB_NAME) as db:

        try:

            await db.execute(
                "INSERT INTO services (name) VALUES (?)",
                (name,)
            )

            await db.commit()

        except:

            return await interaction.response.send_message(
                "Service already exists.",
                ephemeral=True
            )

    await interaction.response.send_message(
        embed=make_embed(
            "Service Added",
            f"Added `{name}`",
            0x00ff99
        )
    )

@tree.command(name="servicedelete")
@app_commands.autocomplete(
    name=service_autocomplete
)
async def servicedelete(
    interaction: discord.Interaction,
    name: str
):

    if wrong_channel(interaction):

        return await interaction.response.send_message(
            f"Use <#{PREMIUM_GEN_CHANNEL_ID}> or <#{FREE_GEN_CHANNEL_ID}>",
            ephemeral=True
        )

    if not is_admin(interaction.user):
        return

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            "DELETE FROM services WHERE name = ?",
            (name,)
        )

        await db.execute(
            "DELETE FROM stock WHERE service = ?",
            (name,)
        )

        await db.commit()

    await interaction.response.send_message(
        embed=make_embed(
            "Service Deleted",
            f"Deleted `{name}`",
            0xff0000
        )
    )

@tree.command(name="services")
async def services(interaction: discord.Interaction):

    if wrong_channel(interaction):

        return await interaction.response.send_message(
            f"Use <#{PREMIUM_GEN_CHANNEL_ID}> or <#{FREE_GEN_CHANNEL_ID}>",
            ephemeral=True
        )

    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT name FROM services"
        ) as cursor:

            rows = await cursor.fetchall()

    if not rows:

        return await interaction.response.send_message(
            "No services found."
        )

    text = "\n".join(
        [f"• `{row[0]}`" for row in rows]
    )

    await interaction.response.send_message(
        embed=make_embed(
            "Available Services",
            text,
            0x00ff99
        )
    )

@tree.command(name="stockadd")
@app_commands.autocomplete(
    service=service_autocomplete
)
async def stockadd(
    interaction: discord.Interaction,
    service: str,
    file: discord.Attachment
):

    if wrong_channel(interaction):

        return await interaction.response.send_message(
            f"Use <#{PREMIUM_GEN_CHANNEL_ID}> or <#{FREE_GEN_CHANNEL_ID}>",
            ephemeral=True
        )

    if not is_admin(interaction.user):
        return

    if not file.filename.endswith(".txt"):

        return await interaction.response.send_message(
            "Upload .txt file only.",
            ephemeral=True
        )

    await interaction.response.defer()

    content = await file.read()

    lines = content.decode(
        "utf-8",
        errors="ignore"
    ).splitlines()

    added = 0

    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT name FROM services WHERE name = ?",
            (service,)
        ) as cursor:

            exists = await cursor.fetchone()

        if not exists:

            return await interaction.followup.send(
                "Service does not exist."
            )

        for line in lines:

            line = line.strip()

            if line:

                await db.execute(
                    "INSERT INTO stock (service, account) VALUES (?, ?)",
                    (service, line)
                )

                added += 1

        await db.commit()

    await interaction.followup.send(
        embed=make_embed(
            "Stock Added",
            f"Added `{added}` accounts to `{service}`",
            0x00ff99
        )
    )

@tree.command(name="stockclear")
@app_commands.autocomplete(
    service=service_autocomplete
)
async def stockclear(
    interaction: discord.Interaction,
    service: str
):

    if wrong_channel(interaction):

        return await interaction.response.send_message(
            f"Use <#{PREMIUM_GEN_CHANNEL_ID}> or <#{FREE_GEN_CHANNEL_ID}>",
            ephemeral=True
        )

    if not is_admin(interaction.user):
        return

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            "DELETE FROM stock WHERE service = ?",
            (service,)
        )

        await db.commit()

    await interaction.response.send_message(
        embed=make_embed(
            "Stock Cleared",
            f"Cleared `{service}` stock",
            0xff0000
        )
     )  
@tree.command(name="stock")
@app_commands.autocomplete(
    service=service_autocomplete
)
async def stock(
    interaction: discord.Interaction,
    service: str
):

    if wrong_channel(interaction):

        return await interaction.response.send_message(
            f"Use <#{PREMIUM_GEN_CHANNEL_ID}> or <#{FREE_GEN_CHANNEL_ID}>",
            ephemeral=True
        )

    count = await get_stock_count(service)

    await interaction.response.send_message(
        embed=make_embed(
            "Stock Information",
            f"Service: `{service}`\nStock: `{count}`",
            0x00ff99
        )
    )

@tree.command(name="gen")
@app_commands.autocomplete(service=service_autocomplete)
async def gen(interaction: discord.Interaction, service: str):

    if wrong_channel(interaction):
        return await interaction.response.send_message(
            f"Use <#{PREMIUM_GEN_CHANNEL_ID}> or <#{FREE_GEN_CHANNEL_ID}>",
            ephemeral=True
        )

    await interaction.response.defer(thinking=True)

    user_id = interaction.user.id

    service = service.lower()

    if service not in FREE_SERVICES and service not in PREMIUM_SERVICES:
        return await interaction.followup.send("Service not configured.")

    sub_role = interaction.guild.get_role(SUB_ROLE_ID)
    free_role = interaction.guild.get_role(FREE_ROLE_ID)

    member_roles = interaction.user.roles

    is_free = free_role in member_roles
    is_prem = sub_role in member_roles

    if is_free and not is_prem and interaction.channel.id != FREE_GEN_CHANNEL_ID:
        return await interaction.followup.send(
        embed=make_embed(
            "Wrong Channel",
            "Free users can only use `/gen` in the free generation channel.",
            0xff0000
        ),
        ephemeral=True
    )

    if not is_free and not is_prem:
        return await interaction.followup.send(
        embed=make_embed("No Access", "You need the free or premium role.", 0xff0000),
        ephemeral=True
    )

    if is_free and not is_prem:
        if service not in FREE_SERVICES:
            return await interaction.followup.send(
            embed=make_embed(
                "Restricted",
                "Free users can only use free services.",
                0xff0000
            ),
            ephemeral=True
        )

    if is_prem:
        if service not in FREE_SERVICES and service not in PREMIUM_SERVICES:
            return await interaction.followup.send(
            embed=make_embed(
                "Invalid Service",
                "This service is not available.",
                0xff0000
            ),
            ephemeral=True
        )

    now = int(time.time())

    if interaction.channel.id == FREE_GEN_CHANNEL_ID:
        cooldown = 300
    else:
        cooldown = 1800

    async with aiosqlite.connect(DB_NAME) as db:

        # Check for custom user cooldown
        async with db.execute(
            "SELECT cooldown_seconds FROM custom_user_cooldown WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            custom_cooldown_row = await cursor.fetchone()
        
        if custom_cooldown_row:
            cooldown = custom_cooldown_row[0]

        async with db.execute(
            "SELECT last_used FROM user_cooldowns WHERE user_id = ? AND service = ?",
            (user_id, service)
        ) as cursor:
            row = await cursor.fetchone()

        last_used = row[0] if row else 0
        remaining = cooldown - (now - last_used)

        if remaining > 0:
          return await interaction.followup.send(
    embed=make_embed(
        "⏳ Cooldown Active",
        f"You need to wait **{int(remaining)} seconds** before using `/gen` again.",
        0xffcc00
    )
)

        # STOCK FETCH
        async with db.execute(
            "SELECT rowid, account FROM stock WHERE service = ? LIMIT 1",
            (service,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return await interaction.followup.send(
                embed=make_embed("Out Of Stock", f"`{service}` is out of stock.", 0xff0000)
            )

        rowid, account = row

        # DELETE STOCK
        await db.execute(
            "DELETE FROM stock WHERE rowid = ?",
            (rowid,)
        )

        # UPDATE COOLDOWN
        await db.execute("""
            INSERT INTO user_cooldowns (user_id, service, last_used)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, service)
            DO UPDATE SET last_used = excluded.last_used
        """, (user_id, service, now))

        await db.commit()

    try:
        data = json.loads(account)
    except:
        data = {
            "email": account,
            "verified_email": False,
            "verified_phone": False,
            "2fa": False,
            "banned": False,
            "level": 0,
            "credits": 0,
            "renown": 0,
            "items": 0,
            "xbox": False,
            "psn": False,
            "steam": False,
        }

    platforms = []

    if data.get("xbox"):
        platforms.append("🎮 Xbox Linkable")
    if data.get("psn"):
        platforms.append("🎮 PSN Linkable")
    if data.get("steam"):
        platforms.append("💻 Steam Linkable")

    if not platforms:
        platforms.append("None")

    dm_embed = discord.Embed(
        title="Account Generated!",
        color=0x00ff99
    )

    dm_embed.add_field(
        name="❤️ Account Credentials",
        value=f"```{data.get('email')}:{data.get('password')}```",
        inline=False
    )

    dm_embed.set_footer(text="Made by Mist")
    dm_embed.set_image(url=GIF_URL)

    public_embed = make_embed(
        "Product Generated!",
        f"{interaction.user.mention} generated a product. Check DMs.",
        0x00ff99
    )

    try:
        await interaction.user.send(embed=dm_embed)
        await interaction.followup.send(embed=public_embed)
    except:
        await interaction.followup.send(
            embed=make_embed("DMs Disabled", "Enable DMs first.", 0xff0000),
            ephemeral=True
        )

@tree.command(name="users")
async def users(
    interaction: discord.Interaction,
    role: discord.Role
):

    await interaction.response.send_message(
        embed=make_embed(
            "Role Users",
            f"`{role.name}` has `{len(role.members)}` users.",
            0x00ff99
        )
    )

@tree.command(name="time")
async def timeleft(
    interaction: discord.Interaction,
    user: discord.Member
):

    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT expires_at FROM users WHERE user_id = ?",
            (user.id,)
        ) as cursor:

            row = await cursor.fetchone()

    if not row:

        return await interaction.response.send_message(
            f"{user.mention} has no subscription."
        )

    remaining = row[0] - int(time.time())

    if remaining <= 0:

        return await interaction.response.send_message(
            "Subscription expired."
        )

    days = remaining // 86400
    hours = (remaining % 86400) // 3600
    minutes = (remaining % 3600) // 60
    seconds = remaining % 60

    await interaction.response.send_message(
        embed=make_embed(
            "Subscription Time",
            f"{user.mention}: `{days}d {hours}h {minutes}m {seconds}s` remaining.",
            0x00ff99
        )
    )

@tree.command(name="addtime")
async def addtime(
    interaction: discord.Interaction,
    user: discord.Member,
    duration: str
):

    if not is_admin(interaction.user):
        return

    seconds = parse_duration(duration)

    if not seconds:

        return await interaction.response.send_message(
            """
1day
3days
7days
3weeks
1month
1year
            """,
            ephemeral=True
        )

    expires_at = int(time.time()) + seconds

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
        INSERT OR REPLACE INTO users (
            user_id,
            expires_at
        )
        VALUES (?, ?)
        """, (
            user.id,
            expires_at
        ))

        await db.commit()

    role = interaction.guild.get_role(
        SUB_ROLE_ID
    )

    await user.add_roles(role)

    await interaction.response.send_message(
        embed=make_embed(
            "Time Added",
            f"Added `{duration}` to {user.mention}",
            0x00ff99
        )
    )

@tree.command(name="removetime")
async def removetime(
    interaction: discord.Interaction,
    user: discord.Member,
    duration: str
):

    if not is_admin(interaction.user):
        return

    seconds = parse_duration(duration)

    if not seconds:

        return await interaction.response.send_message(
            """
1day
3days
7days
3weeks
1month
1year
            """,
            ephemeral=True
        )

    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT expires_at FROM users WHERE user_id = ?",
            (user.id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return await interaction.response.send_message(
                f"{user.mention} has no active subscription.",
                ephemeral=True
            )

        current_expires_at = row[0]
        new_expires_at = current_expires_at - seconds

        await db.execute("""
        UPDATE users
        SET expires_at = ?
        WHERE user_id = ?
        """, (new_expires_at, user.id))

        await db.commit()

    await interaction.response.send_message(
        embed=make_embed(
            "Time Removed",
            f"Removed `{duration}` from {user.mention}",
            0xff0000
        )
    )

@tree.command(name="customcooldown")
async def customcooldown(
    interaction: discord.Interaction,
    user: discord.Member,
    minutes: int
):

    if not is_admin(interaction.user):
        return

    if minutes < 0:
        return await interaction.response.send_message(
            embed=make_embed(
                "Invalid Input",
                "Minutes cannot be negative.",
                0xff0000
            ),
            ephemeral=True
        )

    cooldown_seconds = minutes * 60

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
        INSERT OR REPLACE INTO custom_user_cooldown (user_id, cooldown_seconds)
        VALUES (?, ?)
        """, (user.id, cooldown_seconds))

        await db.commit()

    cooldown_text = "no cooldown" if minutes == 0 else f"{minutes} minute{'s' if minutes != 1 else ''}"

    await interaction.response.send_message(
        embed=make_embed(
            "Custom Cooldown Set",
            f"Set {user.mention}'s cooldown to: `{cooldown_text}`",
            0x00ff99
        )
    )

print(TOKEN[:10] if TOKEN else "TOKEN IS NONE")
bot.run(TOKEN)
