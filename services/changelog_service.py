import os
import subprocess
import time
import logging

logger = logging.getLogger("dalet.services.changelog")


class ChangelogService:
    """
    Servicio de control de versiones y registro de cambios dinámico para Dalet.
    Calcula versiones semánticas automáticamente y lee los últimos commits desde Git.
    """

    BASE_VERSION = "v3.1"
    # Commit base del hito v3.1 (Moderación modular y memoria cognitiva)
    BASE_MILESTONE_COMMIT = "268bce4"
    FALLBACK_PATCH = 10
    REPO_URL = "https://github.com/Janlhx/Dalet-Proyect"

    _cached_version: str | None = None
    _cached_commits: list[dict] | None = None
    _last_cache_time: float = 0.0
    _CACHE_TTL: float = 60.0  # 1 minuto de caché en memoria

    @classmethod
    def get_version(cls) -> str:
        """Calcula dinámicamente la versión semántica (v3.1.<patch>) a partir de los commits."""
        now = time.time()
        if cls._cached_version and (now - cls._last_cache_time < cls._CACHE_TTL):
            return cls._cached_version

        patch_number = cls.FALLBACK_PATCH
        try:
            cmd = ["git", "rev-list", "--count", f"{cls.BASE_MILESTONE_COMMIT}..HEAD"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3.0)
            if res.returncode == 0 and res.stdout.strip().isdigit():
                patch_number = int(res.stdout.strip())
        except Exception as e:
            logger.debug(f"No se pudo consultar conteo de git: {e}")

        version = f"{cls.BASE_VERSION}.{patch_number}"
        cls._cached_version = version
        cls._last_cache_time = now
        return version

    @classmethod
    def get_recent_commits(cls, limit: int = 6) -> list[dict]:
        """Obtiene los últimos commits de Git formateados con su categoría Conventional Commits."""
        now = time.time()
        if cls._cached_commits is not None and (now - cls._last_cache_time < cls._CACHE_TTL):
            return cls._cached_commits[:limit]

        commits = []
        try:
            cmd = ["git", "log", f"-n", str(limit), "--pretty=format:%h|%s|%cd", "--date=short"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3.0)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().split("\n"):
                    parts = line.split("|", 2)
                    if len(parts) >= 2:
                        chash = parts[0].strip()
                        raw_msg = parts[1].strip()
                        date_str = parts[2].strip() if len(parts) > 2 else ""

                        lower_msg = raw_msg.lower()
                        if lower_msg.startswith("feat"):
                            icon = "✨"
                            category = "feat"
                        elif lower_msg.startswith("fix"):
                            icon = "🐛"
                            category = "fix"
                        elif lower_msg.startswith("perf"):
                            icon = "⚡"
                            category = "perf"
                        elif lower_msg.startswith("docs"):
                            icon = "📝"
                            category = "docs"
                        elif lower_msg.startswith("refactor"):
                            icon = "🔨"
                            category = "refactor"
                        elif lower_msg.startswith("test"):
                            icon = "🧪"
                            category = "test"
                        else:
                            icon = "🔧"
                            category = "chore"

                        commits.append({
                            "hash": chash,
                            "url": f"{cls.REPO_URL}/commit/{chash}",
                            "message": raw_msg,
                            "date": date_str,
                            "icon": icon,
                            "category": category,
                        })
        except Exception as e:
            logger.debug(f"No se pudieron leer commits desde git: {e}")

        if not commits:
            commits = cls._get_fallback_commits()

        cls._cached_commits = commits
        cls._last_cache_time = now
        return commits[:limit]

    @classmethod
    def _get_fallback_commits(cls) -> list[dict]:
        """Commits de respaldo si el entorno de ejecución no tiene acceso al binario de git."""
        raw_fallback = [
            ("4e3689f", "fix(mod): calibrate vision prompt for ecchi/waifu art and prioritize model analysis", "🐛"),
            ("3e874f4", "fix(telemetry): prevent NaN latency crash on startup and handle async client close", "🐛"),
            ("a79b380", "fix(db): prevent duplicate column errors and handle libsql KeyError 'result' gracefully", "🐛"),
            ("ff2c89f", "fix(mod): add explicit role names and permission checks to timeout and ban diagnostics", "🐛"),
            ("601ab46", "feat(mod): add channel exemption support and role hierarchy diagnostics", "✨"),
            ("0bf16f9", "fix(moderation): fix missing SPAM_CHANNEL_THRESHOLD and enhance vision safety prompt", "🐛"),
        ]
        return [
            {
                "hash": h,
                "url": f"{cls.REPO_URL}/commit/{h}",
                "message": msg,
                "date": "2026-09-30",
                "icon": icon,
                "category": "update",
            }
            for h, msg, icon in raw_fallback
        ]

    @classmethod
    def build_embed(cls, server_lang: str = "es", custom_banner: str | None = None):
        """Construye un Embed enriquecido de Discord con el hito mayor y los últimos commits."""
        import discord
        from ui.atoms import DaletAtoms
        from ui.molecules import DaletMolecules

        version = cls.get_version()
        commits = cls.get_recent_commits(limit=6)
        is_es = server_lang == "es"

        title = f"{DaletAtoms.EMOJI_DALET} Dalet {version} — {'Novedades y Registro de Cambios' if is_es else 'Updates & Changelog'}"
        embed = discord.Embed(title=title, color=DaletAtoms.COLOR_PRIMARY)

        if custom_banner:
            embed.description = f'> *"{custom_banner}"*\n'

        # Sección del Hito Mayor (v3.1)
        if is_es:
            milestone_title = f"{DaletAtoms.GLYPH_POINTER} Hito {cls.BASE_VERSION}: Auto-Moderación Modular & Memoria Cognitiva"
            milestone_desc = (
                "• **Auto-Moderación**: Detección visual con IA (Gemini Vision), Anti-Flood en memoria, protección anti-phishing y canales exentos (`/mod ignore`).\n"
                "• **Memoria Reflexiva**: Guarda mensajes de usuarios y conclusiones internas (`DaletThought`) para conversaciones naturales.\n"
                "• **Infraestructura**: Migraciones cloud Turso automáticas con fallback offline en SQLite WAL."
            )
            commits_header = f"{DaletAtoms.GLYPH_POINTER} Últimos Cambios (Commits)"
        else:
            milestone_title = f"{DaletAtoms.GLYPH_POINTER} Milestone {cls.BASE_VERSION}: Modular Auto-Moderation & Cognitive Memory"
            milestone_desc = (
                "• **Auto-Moderation**: AI vision content filter (Gemini Vision), in-memory anti-flood, phishing heuristics, and channel exemptions (`/mod ignore`).\n"
                "• **Reflective Memory**: Stores user interactions alongside internal takeaways (`DaletThought`) for natural banter.\n"
                "• **Infrastructure**: Resilient zero-downtime Turso cloud migrations with local SQLite WAL fallback."
            )
            commits_header = f"{DaletAtoms.GLYPH_POINTER} Recent Commits & Patches"

        embed.add_field(name=milestone_title, value=milestone_desc, inline=False)

        commit_lines = []
        for c in commits:
            commit_lines.append(f"• [`{c['hash']}`]({c['url']}) {c['icon']} {c['message']}")

        if commit_lines:
            embed.add_field(name=commits_header, value="\n".join(commit_lines), inline=False)

        footer_text = f"Dalet {version} │ github.com/Janlhx/Dalet-Proyect"
        DaletMolecules.add_standard_footer(embed, context_text=footer_text)
        return embed
