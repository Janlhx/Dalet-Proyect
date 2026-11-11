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
    FALLBACK_PATCH = 10
    REPO_URL = "https://github.com/Janlhx/Dalet-Proyect"

    _FALLBACK_COMMITS = [
        ("HEAD", "feat(osu,compare): add d.c / /compare beatmap score comparison with Bathbot/owo embed detection and /usercompare", "✦"),
        ("298c27a", "feat(osu,pp): integrate rosu-pp fail/if-fc simulation, enhanced play cards, and d.m / /map command", "✦"),
        ("7f14f28", "fix(osu,link): enforce strict composite key isolation for multi-server linking and unlink", "✦"),
        ("7919495", "feat(commands,ui): implement Spec-006 legacy cleanup, glyph UI standardization, and slash parity", "✦"),
        ("9454526", "fix(commands): resolve prefix alias collision between d.language and d.lang", "✦"),
        ("bffa5ff", "feat(security,tests): implement Spec-005 SSRF guard, constant-time auth, OWASP headers, and security test suite", "✦"),
        ("74f88f7", "feat(osu,ux): add Akatsuki/Gatari multi-server support, user language cascade, spacious cards, and adaptive verdicts", "✦"),
        ("0458106", "feat(osu): overhaul legacy commands data accuracy, add /progress, /firsts, /unlink, and skills v2", "✦"),
        ("42e78ed", "feat(persona,chat): add PersonaInsights self-calibration and 180s reaction cooldown", "✦"),
        ("f4c84ec", "feat(osu,memory): add /top & /recent filters (d.rb, d.rp) and selective memory with 14d L2 decay", "✦"),
        ("v4.0.0", "feat(v4): integrate DeepSeek native Web Search & Fetch, overhaul /proactive & emoji reactions, and redesign /help", "✦"),
        ("4815b25", "feat(memory): implement L0-L3 Semantic Pyramid memory architecture and dashboard view", "✦"),
    ]

    _MILESTONES_ES = {
        "v4": (
            "Hito v4.0: Compare por Mapas (`d.c`), Motor rosu-pp, Multi-Servidor osu!, UI en Glifos & Seguridad",
            "▫ **Compare por Mapas (`d.c` / `/compare`) & Lectura de Otros Bots (Spec-008)**: Compara todas tus mejores jugadas guardadas (con mods o `+NM`) en un mapa leyendo Reply directo o embeds recientes de Bathbot, owo y Dalet en el canal (`d.c` y `d.m`); duelos 1v1 ahora en `/usercompare` (`d.vs`, `d.uc`).\n"
            "▫ **Simulación Exacta rosu-pp & Comando `/map` (`d.m`) (Spec-007)**: Cálculo real de PP alcanzado en fails/unranked (`passed_objects`), proyección `if FC` visible en todas las jugadas con fallos o chokes (`/recent`, `/top`, `/firsts`), atributos escalados a mods y ficha `/map` (`d.m`) con tabla `95/98/99/100% SS`.\n"
            "▫ **Modernización Legacy & UI en Glifos (Spec-006)**: Estandarización total de Discord UI con glifos tipográficos (cero emojis), bloqueo anti-ping en `/say` (`d.say`), paridad `/channelstatus` (`d.cs`), unificación `d.ping` (`d.ms`), cascada híbrida de idioma y retiro de comandos obsoletos (`d.memories`, `d.chatlog`, `d.ver_resumenes`).\n"
            "▫ **Endurecimiento de Seguridad & Suite Automatizada (Spec-005)**: Guardia SSRF en `web_fetch`, comparación *constant-time* (`hmac.compare_digest`), cabeceras HTTP OWASP, allowlist/límites en Dashboard y suite `test_security_and_moderation.py`.\n"
            "▫ **Soporte Multi-Servidor & Prefijos Bathbot/owo (Spec-004)**: Soporte completo para `Bancho`, `Akatsuki` (Vanilla/Relax/Autopilot) y `Gatari`, vinculación independiente por servidor (`/link`, `d.link -aka -rx -gatari`) y atajos rápidos (`d.opm`, `d.rsm`, `d.topm`).\n"
            "▫ **Tarjetas Espaciadas, Veredictos Conscientes de Nivel & Cascada de Idioma**: Tarjetas con aire visual y enlaces clickables, arquetipos `APEX_TITAN` / `ALL_ROUNDER` / `SPECIALIST` / `RISING_GRINDER` en `/skills`, e idioma híbrido `Usuario > Servidor > Default` (`/language`, `d.lang`).\n"
            "▫ **Exactitud Total en osu! & Pirámide L0–L3 (Spec-001..003)**: Radar 5D anclado a PP, duelos de mapas en común en `/compare`, `/progress`, `/firsts`, y memoria `L0–L3` con `PersonaInsights`."
        )
    }

    _MILESTONES_EN = {
        "v4": (
            "Milestone v4.0: Beatmap Compare (`d.c`), rosu-pp Engine, Multi-Server osu!, Glyph UI & Security",
            "▫ **Beatmap Score Compare (`d.c` / `/compare`) & Cross-Bot Embed Detection (Spec-008)**: Compares your saved mod/NM scores on a beatmap directly from a Reply or recent channel embeds by Bathbot, owo, or Dalet (reused in `d.m`); 1v1 player comparison moved cleanly to `/usercompare` (`d.vs`, `d.uc`).\n"
            "▫ **Exact rosu-pp Simulation & `/map` (`d.m`) Command (Spec-007)**: Real PP achieved on failed/unranked scores (`passed_objects`), inline `if FC` estimates across every play card (`/recent`, `/top`, `/firsts`), mod-scaled map attributes, and `/map` (`d.m`) with `95/98/99/100% SS` PP table.\n"
            "▫ **Legacy Cleanup & Glyph UI Standardization (Spec-006)**: Pure typographic glyph UI across all Discord embeds/views (zero emojis), mention-safe `/say` (`d.say`), `/channelstatus` (`d.cs`) parity, `d.ping` (`d.ms`) unification, hybrid language cascade, and removal of deprecated commands (`d.memories`, `d.chatlog`, `d.ver_resumenes`).\n"
            "▫ **Security Hardening & Automated Test Suite (Spec-005)**: SSRF guard on `web_fetch`, constant-time auth (`hmac.compare_digest`), OWASP HTTP security headers, Dashboard allowlist/clamping, and `test_security_and_moderation.py`.\n"
            "▫ **Multi-Server Support & Bathbot/owo Prefix Ergonomics (Spec-004)**: Full support for `Bancho`, `Akatsuki` (Vanilla/Relax/Autopilot), and `Gatari`, per-server account linking (`/link`, `d.link -aka -rx -gatari`), and mode shortcuts (`d.opm`, `d.rsm`, `d.topm`).\n"
            "▫ **Spacious Cards, Level-Aware Verdicts & Language Cascade**: Spacious clickable cards, `APEX_TITAN` / `ALL_ROUNDER` / `SPECIALIST` / `RISING_GRINDER` archetypes in `/skills`, and `User > Server > Default` language cascade (`/language`, `d.lang`).\n"
            "▫ **osu! Data Accuracy & L0–L3 Pyramid (Spec-001..003)**: PP-anchored 5D radar, shared top map duels in `/compare`, `/progress`, `/firsts`, and `L0–L3` memory with `PersonaInsights`."
        )
    }

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
        return [
            {
                "hash": h,
                "url": f"{cls.REPO_URL}/commit/{h}",
                "message": msg,
                "date": "2026-11-05",
                "glyph": glyph,
                "category": "update",
            }
            for h, msg, glyph in cls._FALLBACK_COMMITS
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
            m_title, m_desc = cls._MILESTONES_ES["v4"]
            milestone_title = f"{DaletAtoms.GLYPH_POINTER} {m_title}"
            milestone_desc = m_desc
            commits_header = f"{DaletAtoms.GLYPH_POINTER} Últimos Cambios (Git Commits)"
        else:
            m_title, m_desc = cls._MILESTONES_EN["v4"]
            milestone_title = f"{DaletAtoms.GLYPH_POINTER} {m_title}"
            milestone_desc = m_desc
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
