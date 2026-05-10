import discord
from discord import app_commands
from discord.ext import commands
import json
import os


# ---------------- CONFIG ----------------

CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
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
            placeholder="Choose a feature...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        feature = self.values[0]

        await interaction.response.edit_message(
            content=f"✅ Selected: **{FEATURES[feature]}**\nNow pick channel(s):",
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
        channels = self.values

        guild_id = str(interaction.guild.id)
        config = load_config()

        if guild_id not in config:
            config[guild_id] = {}

        config[guild_id][self.feature] = [c.id for c in channels]

        save_config(config)

        mentions = ", ".join(c.mention for c in channels)

        await interaction.response.edit_message(
            content=(
                f"✅ Setup complete!\n\n"
                f"**Feature:** {FEATURES[self.feature]}\n"
                f"**Channels:** {mentions}"
            ),
            view=None
        )


class ChannelSelectView(discord.ui.View):
    def __init__(self, feature: str):
        super().__init__(timeout=180)
        self.add_item(ChannelSelect(feature))


# ---------------- COG ----------------

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Configure bot features per channel")
    async def setup(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command only works in servers.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🔧 **Setup Wizard**\nChoose a feature to configure:",
            view=FeatureSelectView(),
            ephemeral=True
        )


# ---------------- SETUP FUNCTION ----------------

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))