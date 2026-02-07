import discord

class UniversalPaginator(discord.ui.View):
    """Paginador definitivo para el Súper Análisis de Dalet (3 Páginas)."""
    def __init__(self, pages, embed_shell):
        super().__init__(timeout=300)
        self.pages = pages # [Intro, Analysis, Coaching, Footer]
        self.embed = embed_shell
        self.index = 0
        self.update_buttons()

    def update_buttons(self):
        # Deshabilitar botones si estamos en los extremos
        self.children[0].disabled = self.index == 0
        self.children[1].disabled = self.index == 2 # Solo hay 3 páginas principales

    async def update_page(self, interaction: discord.Interaction):
        self.update_buttons()
        
        # Página 1: Intro (ya viene en el embed base, pero aquí actualizamos contenido si es necesario)
        if self.index == 0:
            self.embed.title = "📊 Reporte Dalet: Resumen & Intro"
            self.embed.description = self.pages[0]
            self.embed.clear_fields()
            # Añadir stats básicas de vuelta
            self._add_basic_stats()
        
        # Página 2: Análisis (Diagnóstico)
        elif self.index == 1:
            self.embed.title = "🧠 Reporte Dalet: Diagnóstico Profundo"
            self.embed.description = self.pages[1]
            self.embed.clear_fields()
        
        # Página 3: Coaching (Plan de Acción)
        elif self.index == 2:
            self.embed.title = "🎯 Reporte Dalet: Plan de Entrenamiento"
            self.embed.description = self.pages[2]
            self.embed.clear_fields()

        # Footer siempre visible (es la última parte del split)
        self.embed.set_footer(text=f"{self.pages[3]} | Página {self.index + 1}/3")
        
        await interaction.response.edit_message(embed=self.embed, view=self)

    def _add_basic_stats(self):
        """Re-añade los campos de stats que podrian haberse borrado al limpiar campos."""
        # Esto depende de que guardemos los fields originales en algún sitio si los queremos mantener
        # Por ahora lo dejamos limpio o lo inyectamos desde el comando
        pass

    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
            await self.update_page(interaction)
        else: await interaction.response.defer()

    @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < 2:
            self.index += 1
            await self.update_page(interaction)
        else: await interaction.response.defer()
