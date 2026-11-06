---
name: design-to-motion
description: Translates static UI designs or product concepts into live, purposeful looping showcase animations and interactive micro-interactions following elayadesign/ai-design-skills. Use when building interactive product previews, animated stage showcases, or motion loops.
---

# Design to Motion (`elayadesign/ai-design-skills` adapted for omaishort)

Translates static product interfaces into living, self-demonstrating UI showcases where each component acts out its real function in a smooth, weighted loop.

## Core Principles

1. **Pixel-Exact Structural Fidelity**: Build real HTML/CSS components using the project's exact design tokens (`--bg`, `--surface-*`, `--line`, `--ink`, `--accent`, `--font-display` + Public Sans + `--font-mono` metadata) rather than static images.
2. **Self-Acting Component Loop**:
   - Start from a clean state and step through the real workflow automatically (or on user click).
   - For `omaishort`, animate the 7-stage pipeline (`analyze → plan → refs → stills → tts → captions → render`), showing live Character Bible locking, 5-beat storyboard progress, word-synced karaoke subtitle highlighting, and the `1080×1920` vertical frame preview.
3. **Weighted Motion Physics**:
   - Use `cubic-bezier(0.22, 1, 0.36, 1)` (`500ms` for structural transitions, `300ms` for state/color shifts).
   - Animate only `transform` and `opacity`.
   - Respect `prefers-reduced-motion: reduce`.
4. **Nested Radius & Flat Surface Discipline**:
   - Outer showcase frame (`24px` radius, `8px` padding) → inner viewport (`16px` radius).
   - Flat theme surfaces (`var(--surface-0)` … `var(--surface-3)`) with full `1px solid var(--line)` borders all around; `styles/skins.css` turns them into hard-shadow blocks (`brutal`) or soft extrusions (`soft`).
   - `brutal` motion: press = translate toward the shadow; `soft` motion: press = swap `--soft-out` for `--soft-in`.

