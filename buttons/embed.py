import traceback
import disnake
from typing import List

from config.messages import Messages
from config.app_config import config
from features.leaderboard import LeaderboardPageSource
import utils


class EmbedView(disnake.ui.View):

    def __init__(
        self,
        author: disnake.User,
        embeds: List[disnake.Embed],
        row: int = 0,
        perma_lock: bool = False,
        roll_arroud: bool = True,
        end_arrow: bool = True,
        page_source: LeaderboardPageSource = None,
        timeout: int = 300
    ):
        """Embed pagination view

        param: disnake.User author: command author, used for locking pagination
        param: List[disnake.Embed] embeds: List of embed to be paginated
        param int row: On which row should be buttons added, defaults to first
        param bool perma_lock: If true allow just message autor to change pages, without dynamic lock button
        param bool roll_arroud: After last page rollaround to first
        param bool end_arrow: If true use also '⏩' button
        param LeaderboardPageSource page_source: Use for long leaderboards, embeds should contain one embed
        param int timeout: Seconds until disabling interaction, use None for always enabled
        """
        self.page = 1
        self.author = author
        self.locked = False
        self.page_source = page_source
        self.roll_arroud = roll_arroud
        self.perma_lock = perma_lock
        if self.page_source is None:
            self.max_page = len(embeds)
        else:
            self.max_page = page_source.get_max_pages()
            end_arrow = False
        self.embeds = embeds
        super().__init__(timeout=timeout)
        if self.max_page <= 1:
            return
        self.add_item(
            disnake.ui.Button(
                emoji="⏪",
                custom_id="embed:start_page",
                row=row,
                style=disnake.ButtonStyle.primary
            )
        )
        self.add_item(
            disnake.ui.Button(
                emoji="◀",
                custom_id="embed:prev_page",
                row=row,
                style=disnake.ButtonStyle.primary
            )
        )
        self.add_item(
            disnake.ui.Button(
                emoji="▶",
                custom_id="embed:next_page",
                row=row,
                style=disnake.ButtonStyle.primary
            )
        )
        if end_arrow:
            self.add_item(
                disnake.ui.Button(
                    emoji="⏩",
                    custom_id="embed:end_page",
                    row=row,
                    style=disnake.ButtonStyle.primary
                )
            )
        if not perma_lock:
            # if permanent lock is applied, dynamic lock is removed from buttons
            self.lock_button = disnake.ui.Button(
                emoji="🔓",
                custom_id="embed:lock",
                style=disnake.ButtonStyle.success
            )
            self.add_item(self.lock_button)

    @property
    def embed(self):
        if self.page_source is None:
            return self.embeds[self.page - 1]
        else:
            page = self.page_source.get_page(self.page - 1)
            return self.page_source.format_page(page)

    @embed.setter
    def embed(self, value):
        self.embeds[self.page-1] = value

    async def interaction_check(self, interaction: disnake.MessageInteraction) -> None:
        if interaction.data.custom_id == "embed:lock":
            if interaction.author.id == self.author.id:
                self.locked = not self.locked
                if self.locked:
                    self.lock_button.style = disnake.ButtonStyle.danger
                    self.lock_button.emoji = "🔒"
                else:
                    self.lock_button.style = disnake.ButtonStyle.success
                    self.lock_button.emoji = "🔓"
                await interaction.response.edit_message(view=self)
            else:
                await interaction.send(Messages.embed_not_author, ephemeral=True)
            return False
        ids = ["embed:start_page", "embed:prev_page", "embed:next_page", "embed:end_page"]
        if interaction.data.custom_id not in ids or self.max_page <= 1:
            return
        if (self.perma_lock or self.locked) and interaction.author.id != self.author.id:
            await interaction.send(Messages.embed_not_author, ephemeral=True)
            return False
        self.page = utils.pagination_next(
            interaction.data.custom_id,
            self.page,
            self.max_page,
            self.roll_arroud
        )
        await interaction.response.edit_message(embed=self.embed)

    async def on_timeout(self):
        self.clear_items()
        await self.message.edit(view=self)

    async def on_error(self, error, item: disnake.ui.Item, interaction: disnake.MessageInteraction):
        channel_out = interaction.bot.get_channel(config.bot_dev_channel)
        embed = disnake.Embed(
            title=f"Ignoring exception in interacion '{interaction.data.custom_id}'",
            color=0xFF0000
        )
        embed.add_field(name="Guild", value=interaction.guild)
        embed.add_field(name="Autor", value=interaction.author.display_name)
        embed.add_field(name="Expirace (UTC)", value=interaction.expires_at.strftime("%Y-%m-%d %H:%M:%S"))
        embed.add_field(name="Exception", value=error)
        embed.add_field(name="Item", value=item)
        embed.add_field(name="Zpráva", value=interaction.message.jump_url, inline=False)
        output = utils.cut_string(str(vars(self)), 1900)
        output[0] = f'View object dump:\n{output[0]}'
        for message in output:
            await channel_out.send(f"```\n{message}```")
        await channel_out.send(embed=embed)
        output = traceback.format_exc()
        output = utils.cut_string(output, 1900)
        for message in output:
            await channel_out.send(f"```\n{message}```")

        # remove interactions because of error
        self.clear_items()
        await self.message.edit(view=self)
