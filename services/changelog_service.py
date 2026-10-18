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

    BASE_VERSION = "v4.0"
    # Commit base del hito v4.0 (Pirámide Semántica L0-L3, DeepSeek Web Search/Fetch, Proactive AI & SHA-256 Guard)
    BASE_MILESTONE_COMMIT = "4815b25"
    FALLBACK_PATCH = 0
    REPO_URL = "https://github.com/Janlhx/Dalet-Proyect"

    _cached_version: str | None = None
    _cached_commits: list[dict] | None = None
    _last_cache_time: float = 0.0
    _CACHE_TTL: float = 60.0  # 1 minuto de caché en memoria

    @classmethod
    def get_version(cls) -> str:
        """Calcula dinámicamente la versión semántica (v4.0.<patch>) a partir de los commits."""
        now = time.time()
        if cls._cached_version and (now - cls._last_cache_time < cls._CACHE_TTL):
            return cls._cached_version

        patch_number = cls.FALLBACK_PATCH
        try:
            cmd = ["git", "rev-list", "--count", f"{cls.BASE_MILESTONE_COMMIT}..HEAD"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3.0)
            if res.returncode == 0 and res.stdout.strip().isdigit():
                patch_number = max(0, int(res.stdout.strip()) - 1)
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
                            glyph = "✦"
                            category = "feat"
                        elif lower_msg.startswith("fix"):
                            glyph = "▪"
                            category = "fix"
                        elif lower_msg.startswith("perf"):
                            glyph = "»"
                            category = "perf"
                        elif lower_msg.startswith("docs"):
                            glyph = "◈"
                            category = "docs"
                        elif lower_msg.startswith("refactor"):
                            glyph = "⟡"
                            category = "refactor"
                        elif lower_msg.startswith("test"):
                            glyph = "◎"
                            category = "test"
                        else:
                            glyph = "▫"
                            category = "chore"

                        commits.append({
                            "hash": chash,
                            "url": f"{cls.REPO_URL}/commit/{chash}",
                            "message": raw_msg,
                            "date": date_str,
                            "glyph": glyph,
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
            ("v4.0.0", "feat(v4): integrate DeepSeek native Web Search & Fetch, overhaul /proactive & emoji reactions, and redesign /help", "✦"),
            ("4815b25", "feat(memory): implement L0-L3 Semantic Pyramid memory architecture and dashboard view", "✦"),
            ("a4dbb6a", "feat(resumen): overhaul /resumir with discord live history, dual tone styles, and structured tl;dr embeds", "✦"),
            ("13e2ace", "fix(moderation): resolve single channel id parsing bug and calibrate duplicate flood thresholds", "▪"),
            ("476f4a8", "feat(admin): add d.memories and d.dbtables for database inspection", "✦"),
            ("cb6fa04", "feat(mod): add granular per-module channel exemptions to /mod ignore", "✦"),
        ]
        return [
            {
                "hash": h,
                "url": f"{cls.REPO_URL}/commit/{h}",
                "message": msg,
                "date": "2026-10-18",
                "glyph": glyph,
                "category": "update",
            }
            for h, msg, glyph in raw_fallback
        ]

    @classmethod
    def build_embed(cls, server_lang: str = "es", custom_banner: str | None = None):
        """Construye un Embed enriquecido de Discord con el hito mayor y los últimos commits usando glifos tipográficos."""
        import discord
        from ui.atoms import DaletAtoms
        from ui.molecules import DaletMolecules

        version = cls.get_version()
        commits = cls.get_recent_commits(limit=6)
        is_es = server_lang == "es"

        title = f"{DaletAtoms.EMOJI_DALET} Dalet {version} {DaletAtoms.GLYPH_PIPE} {'Novedades y Registro de Cambios' if is_es else 'Updates & Changelog'}"
        embed = discord.Embed(title=title, color=DaletAtoms.COLOR_PRIMARY)

        if custom_banner:
            embed.description = f'> *"{custom_banner}"*\n'

        # Sección del Hito Mayor (v4.0)
        if is_es:
            milestone_title = f"{DaletAtoms.GLYPH_POINTER} Hito {cls.BASE_VERSION}: DeepSeek Web Search/Fetch, Pirámide L0–L3 & IA Proactiva"
            milestone_desc = (
                f"{DaletAtoms.GLYPH_SUB} **DeepSeek Web Search & Fetch**: Búsqueda web en vivo (`/v1/tools/search`) y lectura de URLs (`/v1/tools/fetch`) autónomas sin depender de Gemini.\n"
                f"{DaletAtoms.GLYPH_SUB} **Pirámide Semántica (L0–L3) + TypeSafe Jev**: Memoria jerárquica (Episodios, Grafo Social y Dossier) enrutada en sub-50ms.\n"
                f"{DaletAtoms.GLYPH_SUB} **IA Proactiva, Reply Nativo & Seguridad**: Modo observadora autónoma en `/proactive`, reacciones con emojis, reply visual (`╭─`) y blacklist SHA-256 a `0ms`."
            )
            commits_header = f"{DaletAtoms.GLYPH_POINTER} Últimos Cambios (Git Commits)"
        else:
            milestone_title = f"{DaletAtoms.GLYPH_POINTER} Milestone {cls.BASE_VERSION}: DeepSeek Web Search/Fetch, L0–L3 Pyramid & Proactive AI"
            milestone_desc = (
                f"{DaletAtoms.GLYPH_SUB} **DeepSeek Web Search & Fetch**: Autonomous live web search (`/v1/tools/search`) and URL reading (`/v1/tools/fetch`) without Gemini dependency.\n"
                f"{DaletAtoms.GLYPH_SUB} **L0–L3 Semantic Pyramid + TypeSafe Jev**: Hierarchical memory (Episodes, Social Graph & Dossier) gated in sub-50ms.\n"
                f"{DaletAtoms.GLYPH_SUB} **Proactive AI, Native Reply & Security**: Autonomous observer framing in `/proactive`, emoji reactions, visual reply (`╭─`), and 0ms SHA-256 image blacklist."
            )
            commits_header = f"{DaletAtoms.GLYPH_POINTER} Recent Commits & Patches"

        embed.add_field(name=milestone_title, value=milestone_desc, inline=False)

        commit_lines = []
        for c in commits:
            glyph = c.get("glyph") or c.get("icon") or DaletAtoms.GLYPH_SUB
            commit_lines.append(f"{glyph} [`{c['hash']}`]({c['url']}) {c['message']}")

        if commit_lines:
            embed.add_field(name=commits_header, value="\n".join(commit_lines), inline=False)

        footer_text = f"Dalet {version} {DaletAtoms.GLYPH_PIPE} github.com/Janlhx/Dalet-Proyect"
        DaletMolecules.add_standard_footer(embed, context_text=footer_text)
        return embed
