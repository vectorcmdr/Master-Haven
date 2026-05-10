import discord
from discord import app_commands
from discord.ext import commands
import json
import os


# ---------------- GUILD CONFIG SYSTEM ----------------

GUILD_FOLDER = "Data/guilds"
os.makedirs(GUILD_FOLDER, exist_ok=True)


def guild_path(guild_id: int):
    return os.path.join(GUILD_FOLDER, f"{guild_id}.json")


def load_guild_config(guild_id: int):
    path = guild_path(guild_id)
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def save_guild_config(guild_id: int, data: dict):
    path = guild_path(guild_id)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


# ---------------- FEATURES ----------------

FEATURES = {
    "auto_reactions": "Auto Reactions",
    "welcome": "Welcome Messages",
    "mod_logs": "Moderation Logs"
}


# ---------------- UI: FEATURE SELECT ----------------

class FeatureSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=name, value=key)
            for key, name in FEATURES.items()
        ]

        super().__init__(
            placeholder="Choose a feature to configure...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        feature = self.values[0]

        await interaction.response.edit_message(
            content=f"✅ Selected: **{FEATURES[feature]}**\nNow select channel(s):",
            view=ChannelSelectView(feature)
        )


class FeatureSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(FeatureSelect())


# ---------------- UI: CHANNEL SELECT ----------------

class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, feature: str):
        self.feature = feature

        super().__init__(
            placeholder="Select channel(s)...",
            min_values=1,
            max_values=10,
            channel_types=[discord.ChannelType.text]
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command only works in servers.",
                ephemeral=True
            )

        guild_id = interaction.guild.id
        channels = self.values

        config = load_guild_config(guild_id)

        # Save feature → channel IDs
        config[self.feature] = [c.id for c in channels]

        save_guild_config(guild_id, config)

        mentions = ", ".join(c.mention for c in channels)

        await interaction.response.edit_message(
            content=(
                f"✅ Setup saved!\n\n"
                f"**Feature:** {FEATURES[self.feature]}\n"
                f"**Channels:** {mentions}"
            ),
            view=None
        )


class ChannelSelectView(discord.ui.View):
    def __init__(self, feature: str):
        super().__init__(timeout=180)
        self.add_item(ChannelSelect(feature))


# ---------------- MAIN COG ----------------

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="Configure bot features per server"
    )
    async def setup(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ This command only works inside servers.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🔧 **Setup Wizard**\nSelect a feature to configure:",
            view=FeatureSelectView(),
            ephemeral=True
        )


# ---------------- EXTENSION ENTRYPOINT ----------------

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))