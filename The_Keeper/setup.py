import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os

# ---------------- DATABASE CONFIG ----------------

DB_PATH = "/home/pi8gb/docker/haven-ui/Master-Haven/The_Keeper/Data/guild.db"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ---------------- DATABASE SETUP ----------------

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS command_config (
    guild_id INTEGER NOT NULL,
    command_name TEXT NOT NULL,
    channel_id INTEGER NOT NULL,
    role_id INTEGER,
    PRIMARY KEY (guild_id, command_name, channel_id)
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLES_SQL)
        await db.commit()

# ---------------- COMMAND FETCHER ----------------

def get_all_commands(bot: commands.Bot):
    cmds = []

    # Slash Commands
    for cmd in bot.tree.get_commands():
        desc = cmd.description or "No description"
        cmds.append((f"/{cmd.name}", desc))

    # Prefix Commands
    for cmd in bot.commands:
        if cmd.hidden:
            continue

        name = f"!{cmd.name}"
        desc = cmd.help or "No description"
        cmds.append((name, desc))

    return cmds

# ---------------- DATABASE HELPERS ----------------

async def save_command_config(
    guild_id: int,
    command_name: str,
    channel_ids: list[int],
    role_id: int | None
):
    async with aiosqlite.connect(DB_PATH) as db:

        # Remove old config first
        await db.execute(
            """
            DELETE FROM command_config
            WHERE guild_id = ?
            AND command_name = ?
            """,
            (guild_id, command_name)
        )

        # Insert new config
        for channel_id in channel_ids:
            await db.execute(
                """
                INSERT INTO command_config (
                    guild_id,
                    command_name,
                    channel_id,
                    role_id
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    guild_id,
                    command_name,
                    channel_id,
                    role_id
                )
            )

        await db.commit()


async def get_command_config(guild_id: int, command_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT channel_id, role_id
            FROM command_config
            WHERE guild_id = ?
            AND command_name = ?
            """,
            (guild_id, command_name)
        )

        rows = await cursor.fetchall()

    if not rows:
        return None

    channels = [row[0] for row in rows]
    role_id = rows[0][1]

    return {
        "channels": channels,
        "role_id": role_id
    }

# ---------------- UI: COMMAND SELECT ----------------

class CommandSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        options = [
            discord.SelectOption(
                label=name,
                value=name,
                description=desc[:100]
            )
            for name, desc in get_all_commands(bot)
        ]

        super().__init__(
            placeholder="Select a command to configure...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        command_name = self.values[0]

        await interaction.response.edit_message(
            content=(
                f"✅ Selected command: **{command_name}**\n"
                f"Now select allowed channels:"
            ),
            view=ChannelSelectView(command_name)
        )


class CommandSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=180)
        self.add_item(CommandSelect(bot))

# ---------------- UI: CHANNEL SELECT ----------------

class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, command_name: str):
        self.command_name = command_name

        super().__init__(
            placeholder="Select allowed channels...",
            min_values=1,
            max_values=10,
            channel_types=[discord.ChannelType.text]
        )

    async def callback(self, interaction: discord.Interaction):

        selected_channels = self.values

        await interaction.response.edit_message(
            content=(
                f"✅ Channels selected for **{self.command_name}**.\n"
                f"Now select an optional role restriction."
            ),
            view=RoleSelectView(
                self.command_name,
                selected_channels
            )
        )


class ChannelSelectView(discord.ui.View):
    def __init__(self, command_name: str):
        super().__init__(timeout=180)
        self.add_item(ChannelSelect(command_name))

# ---------------- UI: ROLE SELECT ----------------

class RoleSelect(discord.ui.RoleSelect):
    def __init__(
        self,
        command_name: str,
        channels: list[discord.abc.GuildChannel]
    ):
        self.command_name = command_name
        self.channels = channels

        super().__init__(
            placeholder="Optional: Select a role restriction...",
            min_values=0,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):

        if not interaction.guild:
            return

        guild_id = interaction.guild.id

        role_id = None
        role_mention = "None"

        if self.values:
            role = self.values[0]
            role_id = role.id
            role_mention = role.mention

        channel_ids = [c.id for c in self.channels]

        await save_command_config(
            guild_id=guild_id,
            command_name=self.command_name,
            channel_ids=channel_ids,
            role_id=role_id
        )

        mentions = ", ".join(c.mention for c in self.channels)

        await interaction.response.edit_message(
            content=(
                f"✅ Configuration saved!\n\n"
                f"**Command:** {self.command_name}\n"
                f"**Channels:** {mentions}\n"
                f"**Role Restriction:** {role_mention}"
            ),
            view=None
        )


class RoleSelectView(discord.ui.View):
    def __init__(
        self,
        command_name: str,
        channels: list[discord.abc.GuildChannel]
    ):
        super().__init__(timeout=180)

        self.add_item(
            RoleSelect(
                command_name,
                channels
            )
        )

# ---------------- MAIN COG ----------------

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="Configure bot commands per server"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(
        self,
        interaction: discord.Interaction
    ):
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ This command only works inside servers.",
                ephemeral=True
            )

        await interaction.response.send_message(
            (
                "🔧 **Setup Wizard**\n"
                "Select a command to configure:"
            ),
            view=CommandSelectView(self.bot),
            ephemeral=True
        )

# ---------------- EXTENSION ENTRYPOINT ----------------

async def setup(bot: commands.Bot):

    await init_db()

    await bot.add_cog(
        SetupCog(bot)
    )