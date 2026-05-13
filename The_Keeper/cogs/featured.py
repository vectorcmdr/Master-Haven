import os
import json
import asyncio
from datetime import datetime, timezone
import discord
from discord.ext import commands, tasks

os.makedirs("Data", exist_ok=True)

FEATURED_FILE = "Data/featured_messages.json"


def is_valid_image(filename: str):
    return filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))


class FeaturedCog(commands.Cog):
    def __init__(
        self,
        bot,
        PHOTO_CHANNEL_ID,
        FEATURED_CHANNEL_ID,
        FEATURED_THRESHOLD,
        FEATURED_TIME_LIMIT,
        log_func,
        count_total_reactions_func
    ):
        self.bot = bot
        self.PHOTO_CHANNEL_ID = PHOTO_CHANNEL_ID
        self.FEATURED_CHANNEL_ID = FEATURED_CHANNEL_ID
        self.FEATURED_THRESHOLD = FEATURED_THRESHOLD
        self.FEATURED_TIME_LIMIT = FEATURED_TIME_LIMIT
        self.log = log_func
        self.count_total_reactions = count_total_reactions_func

        self.FEATURED_MESSAGES = self.load_featured_messages()
        self.PROCESSING = set()
        self.bootstrapped = False

    # -------------------- LOAD / SAVE --------------------
    def load_featured_messages(self):
        if not os.path.exists(FEATURED_FILE):
            with open(FEATURED_FILE, "w") as f:
                json.dump([], f, indent=4)

        try:
            with open(FEATURED_FILE, "r") as f:
                content = f.read().strip()
                if not content:
                    return set()
                data = json.loads(content)
                if isinstance(data, list):
                    return set(data)
        except (json.JSONDecodeError, ValueError):
            pass

        with open(FEATURED_FILE, "w") as f:
            json.dump([], f, indent=4)

        return set()

    def save_featured_messages(self):
        try:
            with open(FEATURED_FILE, "w") as f:
                json.dump(list(self.FEATURED_MESSAGES), f, indent=4)
        except Exception as e:
            print(f"Failed saving featured messages: {e}")

    # -------------------- STARTUP --------------------
    @commands.Cog.listener()
    async def on_ready(self):
        if self.bootstrapped:
            return
        self.bootstrapped = True
        await self.bootstrap_recent_photos()

    async def bootstrap_recent_photos(self):
        await self.bot.wait_until_ready()

        channel = self.bot.get_channel(self.PHOTO_CHANNEL_ID)
        if not channel:
            self.log("BOOTSTRAP", "Photo channel not found")
            return

        async for message in channel.history(limit=5):
            await self.try_feature_message(message)
            await asyncio.sleep(0.2)

    # -------------------- FEATURE LOGIC --------------------
    async def try_feature_message(self, message: discord.Message):
        if message.id in self.FEATURED_MESSAGES or message.id in self.PROCESSING:
            return

        if any(r.me for r in message.reactions):
            return

        self.PROCESSING.add(message.id)

        try:
            now = datetime.now(timezone.utc)
            created = message.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)

            if (now - created).total_seconds() > self.FEATURED_TIME_LIMIT:
                return

            if not message.attachments:
                return

            total_reactions = self.count_total_reactions(message)
            if total_reactions < self.FEATURED_THRESHOLD:
                return

            channel = self.bot.get_channel(self.FEATURED_CHANNEL_ID)
            if not channel:
                return

            images = [a for a in message.attachments if is_valid_image(a.filename)]
            if not images:
                return

            for i, image in enumerate(images, start=1):
                embed = discord.Embed(
                    title=f"📸 Featured Photo #{i}",
                    description=f"Featured by {message.author.mention}",
                    color=0x008080
                )
                embed.set_image(url=image.url)
                embed.add_field(
                    name="Original Message",
                    value=f"[Jump]({message.jump_url})",
                    inline=False
                )
                await channel.send(embed=embed)

            self.FEATURED_MESSAGES.add(message.id)
            self.save_featured_messages()

            try:
                await message.add_reaction("🌟")
            except:
                pass

        finally:
            self.PROCESSING.discard(message.id)

    # -------------------- EVENTS --------------------
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        message = reaction.message

        if isinstance(message, discord.PartialMessage):
            message = await message.fetch()

        if message.channel.id != self.PHOTO_CHANNEL_ID:
            return

        await self.try_feature_message(message)

    # -------------------- DATA --------------------
    async def gather_featured_photos(self):
        channel = self.bot.get_channel(self.PHOTO_CHANNEL_ID)
        if not channel:
            return []

        data = []

        for msg_id in self.FEATURED_MESSAGES:
            try:
                msg = await channel.fetch_message(msg_id)
            except:
                continue

            if not msg.attachments:
                continue

            data.append({
                "author": msg.author.mention,
                "reactions": self.count_total_reactions(msg),
                "url": msg.jump_url,
                "image_url": msg.attachments[0].url
            })

            await asyncio.sleep(0.05)

        return data

    async def gather_featured_user_stats(self):
        channel = self.bot.get_channel(self.PHOTO_CHANNEL_ID)
        if not channel:
            return {}

        stats = {}

        for msg_id in self.FEATURED_MESSAGES:
            try:
                msg = await channel.fetch_message(msg_id)
            except:
                continue

            user = msg.author.mention
            reactions = self.count_total_reactions(msg)

            if user not in stats:
                stats[user] = {"photos": 0, "reactions": 0}

            stats[user]["photos"] += 1
            stats[user]["reactions"] += reactions

            await asyncio.sleep(0.05)

        return stats

    # -------------------- COMMANDS --------------------
    @commands.command(name="pictest")
    @commands.has_permissions(administrator=True)
    async def pictest(self, ctx, limit: int = None):
        await self.post_leaderboard(channel=ctx.channel, limit=limit)

    @commands.command(name="picusers")
    @commands.has_permissions(administrator=True)
    async def picusers(self, ctx, limit: int = 10):
        stats = await self.gather_featured_user_stats()

        if not stats:
            return await ctx.send("No featured photos found.")

        sorted_users = sorted(
            stats.items(),
            key=lambda x: (x[1]["photos"], x[1]["reactions"]),
            reverse=True
        )

        embed = discord.Embed(
            title="🏆 Featured Photo User Leaderboard",
            color=0x00AAFF
        )

        for i, (user, s) in enumerate(sorted_users[:limit], start=1):
            embed.add_field(
                name=f"{i}.",
                value=f"{user}\n📸 {s['photos']} photos\n⭐ {s['reactions']} reactions",
                inline=False
            )

        await ctx.send(embed=embed)

    # -------------------- LEADERBOARD --------------------
    async def post_leaderboard(self, channel=None, limit=None):
        channel = channel or self.bot.get_channel(self.PHOTO_CHANNEL_ID)
        data = await self.gather_featured_photos()

        if not channel or not data:
            return

        sorted_data = sorted(data, key=lambda x: x["reactions"], reverse=True)

        if limit:
            sorted_data = sorted_data[:limit]

        embed = discord.Embed(
            title="🏆 Featured Photo Leaderboard",
            color=0xFFD700
        )

        for i, p in enumerate(sorted_data, start=1):
            embed.add_field(
                name=f"{i}.",
                value=f"{p['author']}\n[Jump]({p['url']}) — {p['reactions']}",
                inline=False
            )

            if i == 1:
                embed.set_thumbnail(url=p["image_url"])

        await channel.send(embed=embed)


# -------------------- SETUP --------------------
async def setup(bot: commands.Bot):
    PHOTO_CHANNEL_ID = int(os.getenv("PHOTO_CHANNEL_ID", "0"))
    FEATURED_CHANNEL_ID = int(os.getenv("FEATURED_CHANNEL_ID", "0"))
    FEATURED_THRESHOLD = int(os.getenv("FEATURED_THRESHOLD", "5"))
    FEATURED_TIME_LIMIT = int(os.getenv("FEATURED_TIME_LIMIT", str(7 * 24 * 60 * 60)))

    def log(tag, msg):
        print(f"[{tag}] {msg}")

    def count_total_reactions(message):
        return sum(r.count - (1 if r.me else 0) for r in message.reactions)

    await bot.add_cog(FeaturedCog(
        bot,
        PHOTO_CHANNEL_ID,
        FEATURED_CHANNEL_ID,
        FEATURED_THRESHOLD,
        FEATURED_TIME_LIMIT,
        log,
        count_total_reactions
    ))
    
    await bot.add_cog(cog)