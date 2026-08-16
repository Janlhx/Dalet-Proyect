import discord
from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules

class DaletOrganisms:
    """Componentes complejos que forman una sección completa de la UI."""

    @staticmethod
    def create_simple_embed(title, description, color=DaletAtoms.COLOR_PRIMARY, author_name=None):
        """El organismo más básico: Un embed estándar de Dalet."""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        return DaletMolecules.add_standard_footer(embed, author_name)

    @staticmethod
    def create_osu_card(user_data, mode="osu"):
        """Organismo complejo para mostrar el perfil de osu!."""
        username = user_data.get('username', 'Desconocido')
        user_id = user_data.get('id', 0)
        stats = user_data.get('statistics', {})
        country = user_data.get('country', {})
        
        # Determinar color basado en el rank global (Átomo dinámico)
        rank_val = stats.get('global_rank') or 9999999
        color = DaletAtoms.get_rank_color(rank_val)
        
        embed = discord.Embed(
            title=username,
            url=f"https://osu.ppy.sh/users/{user_id}/{mode}",
            description=f"{country.get('name', '??')} ({country.get('code', '??')}) • Modo: {mode.upper()}",
            color=color
        )
        
        # Imagen de perfil y cover
        embed.set_thumbnail(url=user_data.get("avatar_url", ""))
        if user_data.get("cover_url"):
            embed.set_image(url=user_data.get("cover_url"))

        # --- SECCIÓN 1: RENDIMIENTO (Moléculas) ---
        pp = stats.get('pp', 0)
        global_rank = stats.get('global_rank', 0)
        country_rank = stats.get('country_rank', 0)
        
        embed.add_field(
            name="Rendimiento & Ranking",
            value=f"**{pp:,.2f}pp**\n• Global: `#{global_rank:,}`\n• País: `#{country_rank:,}`",
            inline=False
        )
        
        # --- SECCIÓN 2: PRECISIÓN Y NIVEL ---
        accuracy = stats.get('hit_accuracy', 0)
        level = stats.get('level', {}).get('current', 0)
        progress = stats.get('level', {}).get('progress', 0)
        
        # Barra de progreso (Atomo/Molecula visual)
        filled = int(12 * progress / 100)
        bar = f"[{'█' * filled}{'░' * (12 - filled)}]"
        
        embed.add_field(
            name="Precisión & Progreso",
            value=f"• Precisión: **{accuracy:.2f}%**\n• Nivel **{level}** ({progress}%)\n`{bar}`",
            inline=False
        )
        
        # --- SECCIÓN 3: ACTIVIDAD ---
        play_count = stats.get('play_count', 0)
        hours = (stats.get('play_time', 0) or 0) // 3600
        
        embed.add_field(
            name="Actividad",
            value=f"• plays: **{play_count:,}**\n• tiempo: **{hours:,}h**",
            inline=True
        )
        
        # --- SECCIÓN 4: Récords ---
        grades = stats.get('grade_counts', {})
        ssh, ss = grades.get('ssh', 0), grades.get('ss', 0)
        sh, s = grades.get('sh', 0), grades.get('s', 0)
        a = grades.get('a', 0)

        embed.add_field(
            name="Récords",
            value=f"• **SS+**: {ssh:,} | **SS**: {ss:,}\n• **S+**: {sh:,} | **S**: {s:,}\n• **A**: {a:,}",
            inline=True
        )
            
        return DaletMolecules.add_standard_footer(embed)

    @staticmethod
    def create_memory_list_embed(user_name, memories):
        """Organismo para visualizar los recuerdos guardados."""
        embed = discord.Embed(
            title=f"Archivos sobre {user_name}",
            description="Información registrada en los bancos de datos:",
            color=DaletAtoms.COLOR_INFO
        )
        
        if not memories:
            embed.description = "No hay recuerdos registrados sobre este usuario todavía."
        else:
            memory_text = ""
            for i, m in enumerate(memories):
                # Limitar cantidad para no romper el embed
                if i >= 15:
                    memory_text += "... y algunas cosas más que me reservo."
                    break
                memory_text += f"• {m['content']}\n"
            
            embed.add_field(name="Recuerdos", value=memory_text)
            
        return DaletMolecules.add_standard_footer(embed)

    @staticmethod
    def create_user_stats_card(user_name, stats, avatar_url=None):
        """Organismo para mostrar estadísticas sociales del usuario."""
        embed = discord.Embed(
            title=f"Actividad Social · {user_name}",
            color=DaletAtoms.COLOR_PRIMARY,
            description="Resumen de actividad registrada en mis bases de datos."
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
            
        embed.add_field(name="Mensajes", value=f"`{stats.get('total_messages', 0)}`", inline=True)
        embed.add_field(name="Días Activo", value=f"`{stats.get('days_active', 0)}`", inline=True)
        embed.add_field(name="Letras/Msg", value=f"`{stats.get('avg_len', 0):.1f}`", inline=True)
        
        return DaletMolecules.add_standard_footer(embed)
