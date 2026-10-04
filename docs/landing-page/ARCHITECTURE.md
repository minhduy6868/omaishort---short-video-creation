# Architecture — Landing Page

## Kiến trúc hiện tại

### Frontend Stack

| Thành phần | Chi tiết |
| --- | --- |
| Framework | Vite 6 + React 19 |
| Language | TypeScript 5.7 (strict mode) |
| Build | `tsc --noEmit && vite build` |
| Dev server | `vite` on port 5173, proxy → API :8765 |
| Fonts | Fraunces (heading, serif) + Public Sans (body, sans-serif) via Google Fonts |
| CSS | Vanilla CSS with CSS custom properties |

### Cấu trúc thư mục `apps/web/`

```
apps/web/
├── index.html          # SPA entry point (minimal, no SEO)
├── package.json        # React 19, Vite 6, TypeScript 5.7
├── vite.config.ts      # Dev proxy to API :8765
├── tsconfig.json       # ES2022, strict, bundler resolution
└── src/
    ├── main.tsx        # ReactDOM.createRoot render
    ├── App.tsx         # Monolithic studio component (~696 lines)
    ├── App.css         # Studio-specific styles (~303 lines)
    ├── index.css       # Design tokens + reset (~32 lines)
    ├── api.ts          # HTTP client with auth token refresh (~178 lines)
    ├── types.ts        # TypeScript types matching schema (~81 lines)
    └── vite-env.d.ts   # Vite type reference
```

### Design Tokens (index.css)

```css
:root {
  color-scheme: dark;
  --bg: #14110e;        /* Deep charcoal background */
  --panel: #1c1814;     /* Panel background */
  --line: #3a3229;      /* Border/divider */
  --ink: #f3ece3;       /* Primary text (warm white) */
  --muted: #b7a99a;     /* Secondary text */
  --accent: #c45c26;    /* Terracotta orange (brand) */
  --ok: #c9d4a3;        /* Success green */
}
```

### Vấn đề kiến trúc hiện tại

1. **Monolithic component:** `App.tsx` là 696 dòng, chứa tất cả logic + UI
2. **Không có routing:** Single-page studio, không có route cho landing page
3. **Không có i18n:** Tất cả string hardcode trong component
4. **Không có SEO:** `index.html` chỉ có `<title>omaishort</title>`
5. **Không có public folder:** Không có `robots.txt`, `sitemap.xml`, favicon

### Kiến trúc đề xuất cho Landing Page

```
apps/web/
├── index.html                    # Enhanced with SEO meta
├── public/
│   ├── robots.txt
│   ├── sitemap.xml
│   ├── favicon.ico
│   └── og-image.png
├── src/
│   ├── main.tsx                  # Router entry
│   ├── i18n/
│   │   ├── index.ts              # i18n setup
│   │   └── locales/
│   │       ├── en.json
│   │       ├── vi.json
│   │       └── ja.json
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Footer.tsx
│   │   │   └── LanguageSwitcher.tsx
│   │   ├── landing/
│   │   │   ├── HeroSection.tsx
│   │   │   ├── FeaturesSection.tsx
│   │   │   ├── HowItWorksSection.tsx
│   │   │   ├── DemoSection.tsx
│   │   │   ├── UseCasesSection.tsx
│   │   │   ├── FAQSection.tsx
│   │   │   └── CTASection.tsx
│   │   ├── studio/               # Existing studio (extracted from App.tsx)
│   │   │   ├── StudioApp.tsx
│   │   │   ├── AuthPanel.tsx
│   │   │   ├── JobForm.tsx
│   │   │   ├── StageTracker.tsx
│   │   │   ├── StoryboardView.tsx
│   │   │   └── VideoPlayer.tsx
│   │   └── ui/
│   │       ├── Button.tsx
│   │       ├── Card.tsx
│   │       └── Section.tsx
│   ├── pages/
│   │   ├── LandingPage.tsx
│   │   └── StudioPage.tsx
│   ├── hooks/
│   │   ├── useI18n.ts
│   │   └── useSEO.ts
│   ├── styles/
│   │   ├── index.css             # Global tokens + reset
│   │   ├── landing.css           # Landing page styles
│   │   └── studio.css            # Studio styles (from App.css)
│   ├── api.ts
│   ├── types.ts
│   └── vite-env.d.ts
```

### Dependencies mới cần thiết

| Package | Mục đích | Lý do chọn |
| --- | --- | --- |
| `react-router-dom` | Client-side routing (landing ↔ studio) | Standard React router, nhẹ |
| `react-i18next` + `i18next` | Internationalization | Ecosystem lớn nhất, hỗ trợ React 19 |
| `react-helmet-async` | Dynamic `<head>` management (SEO) | Lightweight, async-safe |

### Nguyên tắc

- **Không phá vỡ studio hiện có.** Studio code di chuyển nguyên vẹn vào `StudioPage`
- **Giữ nguyên design tokens.** Mở rộng palette, không thay đổi
- **CSS vanilla.** Không thêm Tailwind/CSS-in-JS
- **TypeScript strict.** `npx tsc --noEmit` phải pass
