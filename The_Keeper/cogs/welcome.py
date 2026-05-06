import discord
from discord.ext import commands
from Data.xpdata import PRIMARY_ROLE_MAP


class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------------------- MEMBER JOIN --------------------
    @commands.Cog.listener()
    async def on_member_join(self, member):
        bot = self.bot

        channel_id = getattr(bot, "WELCOME_CHANNEL_ID", None)

        if not channel_id:
            print("[ERROR] WELCOME_CHANNEL_ID not set.")
            return

        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"[ERROR] Channel {channel_id} not found.")
            return

        await self.send_welcome_embed(channel, member)
        print(f"[WELCOME] Sent welcome embed for {member.name}")

    # -------------------- ROLE UPDATE WELCOME --------------------
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        bot = self.bot

        role_messages = getattr(bot, "role_welcome_messages", {})

        new_roles = [role for role in after.roles if role not in before.roles]

        if not new_roles:
            return

        channel_id = getattr(bot, "WELCOME_CHANNEL_ID", None)
        if not channel_id:
            print("[ERROR] WELCOME_CHANNEL_ID not set.")
            return

        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"[ERROR] Channel {channel_id} not found.")
            return

        avatar = after.avatar.url if after.avatar else after.default_avatar.url

        for new_role in new_roles:
            if new_role.id in role_messages:
                try:
                    embed = discord.Embed(
                        title=f"Welcome to The Haven, {after.display_name}!",
                        description=role_messages[new_role.id],
                        color=0x8A00C4
                    )

                    embed.add_field(
                        name="Learn More",
                        value=(
                            "🌐 https://havenmap.online/haven-ui/\n"
                            "📖 https://docs.google.com/document/d/...\n"
                            "💫 https://travelers-exchange.online/"
                        ),
                        inline=False
                    )

                    embed.set_thumbnail(url=avatar)
                    embed.set_image(
                        url="https://cdn.discordapp.com/attachments/1483946204919501030/1483951736187256913/ezgif-36919d2af39654a6.gif"
                    )

                    await channel.send(embed=embed)

                    print(f"[WELCOME] Role welcome sent for {after.name} ({new_role.name})")

                except Exception as e:
                    print(f"[WELCOME ERROR] {e}")

    # -------------------- HELPER --------------------
    async def send_welcome_embed(self, channel, member):
        embed = discord.Embed(
            title=f"Welcome {member.display_name}!",
            description="Welcome to the server ✨",
            color=0x8A00C4
        )

        avatar = member.avatar.url if member.avatar else member.default_avatar.url
        embed.set_thumbnail(url=avatar)

        await channel.send(embed=embed)


# -------------------- SETUP --------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))