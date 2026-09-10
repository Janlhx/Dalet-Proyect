# 🎨 Dalet Design System (Atomic UI)
 
> Visual style guide, design tokens, typography, and atomic layout standards for Dalet's embeds, interfaces, and cards.

---

## 💎 Design Philosophy

1. **High Information Density**: Present complete statistics and metrics in a structured layout without forcing users to scroll.
2. **Zero Emoji Clutter**: Replace generic Discord emojis with **clean typographic markers and geometric glyphs** (`▸`, `│`, `▫`, `✦`, `★`, `[ ]`).
3. **Strict Visual Hierarchy**:
   - **Hyperlinked Titles**: Clean, clickable beatmap and profile links.
   - **Bold Primary Metrics**: Emphasize PP, Accuracy, Rank, and Combo.
   - **Inline Monospace Blocks**: Format technical data cleanly (`[300/100/50/Miss]`, `AR/OD/HP/CS`, `+HDDT`).
   - **Native Discord Relative Timestamps**: Use standard timestamp formatting (`<t:unix:R>`).
4. **Bilingual Localization (i18n)**: All labels, headers, and tooltips switch seamlessly between English (default) and Spanish via `ui/locales.py`.

---

## 🧱 1. Atoms (`ui/atoms.py`)

Atoms represent indivisible foundation tokens: brand colors, grade tiers, glyph constants, and pure formatting utilities.

### Brand Color Palette

| Token | Hex / RGB | Purpose / Usage |
| :--- | :--- | :--- |
| `COLOR_PRIMARY` | `#FF69B4` (255, 105, 180) | Dalet signature brand pink |
| `COLOR_DARK` | `#18181B` (24, 24, 27) | Dark zinc for neutral backgrounds |
| `COLOR_SUCCESS` | `#22C55E` (34, 197, 94) | Confirmations, success states, Grade A |
| `COLOR_WARNING` | `#F59E0B` (245, 158, 11) | Warnings, cooldown alerts, reminders |
| `COLOR_ERROR` | `#EF4444` (239, 68, 68) | Critical errors, blocked channels, Grade D |
| `COLOR_INFO` | `#0EA5E9` (14, 165, 233) | System information, memories, stats |

### osu! Grade Colors

| Grade | Color | Tier Name |
| :--- | :--- | :--- |
| `XH` / `SH` | `#00E5FF` | Platinum Diamond (Silver SS / S) |
| `X` / `S` | `#FFD700` | Pure Gold (Gold SS / S) |
| `A` | `#22C55E` | Emerald Green |
| `B` | `#3B82F6` | Royal Blue |
| `C` | `#A855F7` | Amethyst Purple |
| `D` | `#EF4444` | Coral Red |
| `F` | `#71717A` | Slate Grey (Failed) |

### Typographic Markers & Glyphs

```python
GLYPH_POINTER = "▸"  # Primary metric bullet
GLYPH_SUB     = "▫"  # Secondary bullet / sub-item
GLYPH_PIPE    = "│"  # Vertical separator
GLYPH_STAR    = "★"  # Star rating indicator
GLYPH_AIM     = "🎯"  # Aim category icon
GLYPH_SPEED   = "⚡"  # Speed category icon
GLYPH_ACC     = "🎯"  # Accuracy category icon
```

---

## 🧪 2. Molecules (`ui/molecules.py`)

Compositions of atoms forming reusable interface components:

- **`add_standard_footer(embed, context_text)`**: Standardized bot footer `Dalet • {context}` with dynamic avatar.
- **`create_progress_bar(percentage, length=8)`**: Clean ASCII progress meter (`[█████░░░]`).
- **`create_button(label, style, disabled)`**: Standard Discord interaction buttons.

---

## 🫀 3. Organisms (`OsuPresenter` & `ui/organisms.py`)

Complete, standalone embed layouts delivered to the user:

### A. Recent Play Card (`/recent` / `d.recent`)
```
[Flag] Recent Play · {Username} (Standard)
─────────────────────────────────────────────────
[Artist - Title [Difficulty]](url)
**+HDDT** │ 6.47★ │ ` SH ` │ 5 minutes ago

▸ Performance             ▸ Score & Hits
▸ PP: **251.79pp**        ▸ Score: `3,912,127`
▸ Accuracy: `98.45%`      ▸ Hits: `[634/54/0/0]`
▸ Combo: `x339/1068`      ▸ Misses: `0`

▸ Beatmap
▸ Length: `2:31` │ BPM: `210`
▸ AR 9.5 · OD 8.6 · HP 5.5 · CS 4.5
─────────────────────────────────────────────────
Thumbnail: Beatmap Cover
Footer: Dalet • Bancho Server
```

### B. Top Plays Card (`/top` / `d.top`)
```
[Flag] Top Scores · {Username} (Standard)
─────────────────────────────────────────────────
1. [Song Title [Extra]](url) +HDDT 7.04★
▸ ` S ` │ **411.94pp** │ `98.33%` │ `x1,150/1,858`
▸ Score: `966,053` │ `[1306/57/0/0]` │ 4 days ago
▸ `3:30` │ `222 BPM` │ `AR 10.0 OD 9.4 HP 6.5 CS 4.0`
...
─────────────────────────────────────────────────
Thumbnail: User Avatar
Footer: Dalet • Bancho Server • Top 5
```

### C. Skill Breakdown Card (`/skills` / `d.skills`)
```
✦ Skill Breakdown — {Username} [Flag]
─────────────────────────────────────────────────
▸ Overall Rating: `6.82★` │ PP: `8,450` │ Rank: `#12,450`
▸ Primary Strength: `Speed` │ Weakest Area: `Reading`

⚡ Speed — `7.45★`
▫ `+DT` [Map 1] • `7.52★` (412pp)
▫ `+DT` [Map 2] • `7.38★` (398pp)

🎯 Aim — `6.90★`
...

⚖️ Dalet's Verdict
> *"Over-inflated numbers in Speed, but your Reading is embarrassing."*
─────────────────────────────────────────────────
Footer: Dalet • ID: 12345678 • osu! Standard
```
