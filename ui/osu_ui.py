import discord

class AnalysisPaginator(discord.ui.View):
    """Paginador para el análisis de 'osuAnalyze' (campos de Embed)."""
    def __init__(self, pages):
        super().__init__(timeout=180)
        self.pages = pages
        self.index = 0
        self.update_buttons()

    def update_buttons(self):
        if len(self.children) > 1:
            self.children[0].disabled = self.index == 0
            self.children[1].disabled = self.index == len(self.pages) - 1

    async def update_embed(self, interaction: discord.Interaction):
        if not interaction.message.embeds: return
        embed = interaction.message.embeds[0]
        if len(embed.fields) > 3:
             embed.set_field_at(
                 index=3, 
                 name=f"🧠 Análisis de Dalet (Página {self.index + 1}/{len(self.pages)})", 
                 value=self.pages[self.index], 
                 inline=False
             )
             self.update_buttons()
             await interaction.response.edit_message(embed=embed, view=self)
        else: await interaction.response.defer()

    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0: 
            self.index -= 1
            await self.update_embed(interaction)
        else: await interaction.response.defer()

    @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.pages) - 1: 
            self.index += 1
            await self.update_embed(interaction)
        else: await interaction.response.defer()

class DescriptionPaginator(discord.ui.View):
    """Paginador para 'osuCoach' (descripción de Embed)."""
    def __init__(self, pages, embed_shell):
        super().__init__(timeout=180)
        self.pages = pages
        self.embed_shell = embed_shell
        self.index = 0
        self.update_view()

    def update_view(self):
         if len(self.children) > 1:
            self.children[0].disabled = self.index == 0
            self.children[1].disabled = self.index == len(self.pages) - 1
            self.embed_shell.set_footer(text=f"Página {self.index + 1} de {len(self.pages)}")

    async def update_message(self, interaction: discord.Interaction):
        self.update_view()
        self.embed_shell.description = self.pages[self.index]
        await interaction.response.edit_message(embed=self.embed_shell, view=self)

    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0: 
            self.index -= 1
            await self.update_message(interaction)
        else: await interaction.response.defer()

    @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.pages) - 1: 
            self.index += 1
            await self.update_message(interaction)
        else: await interaction.response.defer()
