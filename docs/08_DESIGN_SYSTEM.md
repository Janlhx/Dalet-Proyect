# 🎨 Dalet Design System (Atomic UI)
 
> Guía de estilo visual, tokens de diseño y componentes atómicos para todas las respuestas, embeds y paneles interactivos de Dalet.

---

## 💎 Filosofía Visual de Dalet

1. **Alta Densidad Informativa**: Presentar estadísticas y datos de forma compacta y estructurada sin requerir scroll innecesario.
2. **Cero Saturación de Emojis**: Reemplazar emojis genéricos por **marcadores tipográficos y geométricos** (`▸`, `│`, `▫`, `★`, `[ ]`).
3. **Jerarquía Visual Clara**:
   - **Títulos con enlaces limpios** a beatmaps/perfiles.
   - **Métricas primarias en negrita** (PP, Acc, Rank, Score).
   - **Bloques técnicos en formato monospace inline** (`[300/100/50/Miss]`, `AR/OD/HP/CS`, `+HDDT`).
   - **Tiempos relativos nativos de Discord** (`<t:unix:R>`).

---

## 🧱 1. Átomos (`ui/atoms.py`)

Los átomos representan los valores base invariables: colores, estilos de texto, glifos y formateadores puros.

### Paleta de Colores

| Token | Hex / RGB | Uso |
| ----- | --------- | --- |
| `COLOR_PRIMARY` | `#FF69B4` (255, 105, 180) | Color de marca de Dalet (Dalet Pink) |
| `COLOR_DARK` | `#18181B` (24, 24, 27) | Zinc oscuro para fondos y tarjetas |
| `COLOR_SUCCESS` | `#22C55E` (34, 197, 94) | Acciones exitosas, confirmaciones y Rank A |
| `COLOR_WARNING` | `#F59E0B` (245, 158, 11) | Advertencias, cooldowns y recordatorios |
| `COLOR_ERROR` | `#EF4444` (239, 68, 68) | Errores, bloqueos y Rank D |
| `COLOR_INFO` | `#0EA5E9` (14, 165, 233) | Información técnica, memorias y servidores |

### Colores de Rango y Tiers (osu!)

| Grade | Color | Nombre |
| ----- | ----- | ------ |
| `XH` / `SH` | `#00E5FF` | Platinum Diamond (Silver SS / S) |
| `X` / `S` | `#FFD700` | Pure Gold (Gold SS / S) |
| `A` | `#22C55E` | Emerald Green |
| `B` | `#3B82F6` | Royal Blue |
| `C` | `#A855F7` | Amethyst Purple |
| `D` | `#EF4444` | Coral Red |
| `F` | `#71717A` | Slate Grey |

### Marcadores Tipográficos

```python
GLYPH_POINTER = "▸"  # Separador principal de métricas
GLYPH_SUB     = "▫"  # Sub-ítem o viñeta secundaria
GLYPH_PIPE    = "│"  # Separador vertical
GLYPH_STAR    = "★"  # Calificación de estrellas de dificultad
```

---

## 🧪 2. Moléculas (`ui/molecules.py`)

Combinaciones de átomos que forman elementos de interfaz reutilizables:

- **`add_standard_footer(embed, context_text)`**: Pie de página estándar `Dalet • {contexto}` con avatar opcional.
- **`create_progress_bar(percentage, length=10)`**: Barra de progreso pura usando bloques ASCII (`[██████░░░░]`).
- **`create_button(label, style, disabled)`**: Generador de botones estandarizados.

---

## 🫀 3. Organismos (`ui/organisms.py` & `OsuPresenter`)

Secciones completas y embeds listos para enviar al usuario:

### A. Jugada Reciente (`/recent`)
```
[Bandera] Recent osu! Standard Play for {Usuario}
─────────────────────────────────────────────────
[Artista - Título [Dificultad]](url) +HDDT [6.47★]
▸ [ A ] ▸ 156.62PP (251.79pp for 94.38% FC) ▸ 93.24%
▸ 3,912,127 ▸ x339/1068 ▸ [634/54/4/8] ▸ hace 5 minutos
▸ ⏱ 2:31 ▸ 🎵 140 BPM ▸ AR 9.5 OD 8.6 HP 5.5 CS 4.5
─────────────────────────────────────────────────
Thumbnail: Beatmap Cover
Footer: Dalet • On osu! Bancho Server
```

### B. Top Scores (`/top`)
```
[Bandera] Top osu! Standard Plays for {Usuario}
─────────────────────────────────────────────────
1) [Endless night [Eternal]](url) +HDDT [7.04★]
▸ [ A ] ▸ 411.94PP ▸ 97.33%
▸ 966,053 ▸ x1,150/1,858 ▸ [1306/57/1/2] ▸ hace 4 días
▸ ⏱ 3:30 ▸ 🎵 222 BPM ▸ AR 10.0 OD 9.4 HP 6.5 CS 4.0

2) [look at me tenderly [(>///<)]](url) +HD [6.51★]
...
─────────────────────────────────────────────────
Thumbnail: Avatar del Usuario
Footer: Dalet • On osu! Bancho Server • Top 5
```

### C. Perfil de Usuario (`/op`)
```
[Bandera] osu! Standard Profile for {Usuario}
─────────────────────────────────────────────────
Rendimiento
▸ PP: 4,520.12pp
▸ Global: #42,105
▸ País (CO): #120

Precisión & Nivel
▸ Precisión: 98.45%
▸ Nivel: 99 (64%)
`[█████░░░]`

Actividad
▸ Partidas: 24,150
▸ Tiempo de juego: 450h

Récords Obtenidos
`SS` 12 │ `S` 145 │ `A` 890
─────────────────────────────────────────────────
Thumbnail: Avatar
Cover: Banner oficial del perfil
Footer: Dalet • ID: 12345678
```
