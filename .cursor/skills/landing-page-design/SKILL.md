---
name: landing-page-design
description: Designs and builds high-converting landing pages following the elayadesign/ai-design-skills Part A (Strategy & Structure) and Part B (Non-Negotiable Visual System) framework. Use when editing LandingPage.tsx, components/landing/*, or styles/landing.css.
---

# Landing Page Design (`elayadesign/ai-design-skills` adapted for omaishort)

Work through **PART A** before touching **PART B**. Every visual value must resolve through Part B's rules instead of being invented ad hoc.

---

## PART A — Strategy and Structure

### A1. Intake (Single Batch)
Establish or verify the 5 core context pillars before writing copy or layout:
1. **Primary conversion action**: One specific goal (e.g., open local Studio `/work` or copy the CLI run command).
2. **Offer & Mechanism**: What the product produces and how (1080×1920 30fps MP4 with AI voiceover, Character Bible stills, and ASS karaoke captions).
3. **Target ICP**: Independent creators, faceless channel operators, educators, and developers running local-first workflows.
4. **Proof & Assets**: Real CLI-rendered video outputs (`/demo/knowledge-history.mp4`, `/demo/knowledge-skills.mp4`), open-source pipeline stages (`analyze → plan → refs → stills → tts → captions → render`).
5. **Top Objections**: Do I need paid API keys? (No, works with free `edge-tts` + Pollinations). Does character identity drift? (No, Character Bible locks passport stills). Is my data uploaded to a cloud SaaS? (No, 100% local-first).

### A2. Page Structure
1. **Above the fold**:
   - Eyebrow / Kicker badge
   - Headline (capped at 680px width, left-to-right subtle text gradient)
   - Subheadline (concrete mechanism + output format)
   - Single primary CTA + secondary anchor action + proof signal (zero-key local-first badge)
   - Hero Visual: Interactive product showcase / pipeline stage inspector showing the real 7-stage studio engine and 9:16 output preview.
2. **Mid-page**:
   - **Three Formats (Benefits / Solutions)**: Drama (5-beat + Character Bible), News (URL → 5 editorial beats), Knowledge (Topic/README → narrated explainer).
   - **Core Capabilities**: 6 concrete architectural advantages.
   - **How It Works**: 4-step numbered workflow in full-border cards.
   - **Real Output Proof (Demo)**: Real local CLI renders (`9:16` vertical player with custom controls).
   - **Use Cases**: Concrete scenarios with realistic input/output examples.
3. **Bottom**:
   - **FAQ**: Plainly formatted objection-handling accordion.
   - **Final CTA**: Risk-reversal + primary conversion button + CLI quickstart.

### A3. Layout Selection
- **A. Classic hero plus sections**: Split or stacked hero with live product preview + structured grid sections below.

### A4 & A5. Conversion Copywriting Rules
- Headlines use outcome + mechanism clarity (`{Outcome} without {pain}` or `{Category} for {audience}`).
- Action-driven CTA copy (`Open Studio`, `Try the Studio`).
- Zero AI buzzwords (ban *Elevate, Seamless, Unleash, Next-Gen, Game-changer, Delve, Tapestry*).

### A6. Build Order
Work section by section: `Hero → Formats → Capabilities → How It Works → Demo Proof → Use Cases → FAQ → Final CTA`.

### A7. SEO & AEO
- Maintain accurate `title`, `meta description`, OpenGraph tags, and multi-language routes (`/vi`, `/en`, `/ja`).

---

## PART B — Non-Negotiable Visual System

### B1. Typography
- **Project Adaptation**: Text uses `var(--font-display)` / `var(--font-ui)` from the site theme (`brutal`: Space Grotesk; `soft`: Manrope) per `.cursor/rules/frontend.mdc`. Monospace (`ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas`) permitted only for CLI commands, timestamps, resolution badges, and stage codes.
- **No italic fonts** anywhere in the landing page interface.
- **No ultra-bold weights** (800/900). Body caps at `600`; `brutal` display titles and buttons use `700` (set in `styles/skins.css`, not per component).
- **Type scale**: Strictly `12px, 14px, 16px, 18px, 20px, 24px, 32px, 40px, 48px, 64px`.

### B2. Spacing
- **13-step spacing scale (px)**: `0, 2, 4, 8, 12, 16, 24, 32, 40, 48, 64, 80, 96`.
- Do not invent arbitrary spacing values (no `10px`, `14px`, `18px`, `20px`, `28px`, `36px`, `120px`).

### B3. Corner Radius
- **Allowed tokens**: `4px`, `8px`, `12px` (`--radius-sm`), `16px`, `24px`, `9999px` (pills).
- **Nested Radius Formula**: $\text{Inner Radius} = \text{Outer Radius} - \text{Gap (Padding)}$ when gap $< 32\text{px}$ and result $> 2\text{px}$. (Example: Outer card `24px` radius with `8px` padding → inner container `16px` radius; Outer card `16px` radius with `8px` padding → inner container `8px` radius).

### B4. Borders and Backgrounds
- **Borders**: Never apply a border to only one side of a card (no `border-top` or `border-left` only on cards/quotes). Borders must go **all the way around** (`1px solid var(--line)` in component CSS) or not at all. Thickness and shadow come from `styles/skins.css` (`brutal`: 2–3px black + hard offset; `soft`: no visible border, paired soft shadows).
- **Backgrounds**: **Never use gradients in backgrounds.** All page, section, card, and CTA backgrounds must be completely flat theme tokens (`var(--bg)`, `var(--surface-0)` … `var(--surface-3)`), never raw hex. Remove any radial glow blobs or linear-gradient section backdrops.

### B5. Hero Section
- **Max width**: Hero heading and subheading capped at `680px` max-width for clean, natural line breaks.
- **Heading color gradient**: Left-to-right text gradient on the main `h1` hero heading (`var(--hero-from)` → `var(--hero-to)`, set per theme) using `background-clip: text`. `brutal` overrides it to solid uppercase ink.

### B6. Icons
- Clean, consistent `1.5px` stroke vector icons (Phosphor / Solar style). Never use Material Icons or emojis.

### B7. Motion
- **Easing & Duration**: Never ship browser default curves (`ease`, `linear`, `ease-in-out`).
- Layout and scroll reveals use `cubic-bezier(0.22, 1, 0.36, 1)` at `500ms`.
- Hover shifts use `cubic-bezier(0.22, 1, 0.36, 1)` at `300ms` (never shorter than `200ms`).
- **Performance rule**: Animate **only** `transform` and `opacity`.
- **Accessibility**: Respect `prefers-reduced-motion: reduce`.

### B8. Content Realism
- Zero placeholder text, zero fake round stats, zero generic clichés. Use authentic `omaishort` CLI flags (`--kind drama`, `--language vi`, `1080×1920 @ 30fps`), real stage names (`analyze`, `plan`, `refs`, `stills`, `tts`, `captions`, `render`), and real demo videos.

