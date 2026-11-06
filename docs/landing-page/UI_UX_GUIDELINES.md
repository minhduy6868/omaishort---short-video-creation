# UI/UX Guidelines — omaishort Landing Page

## Brand Identity

### Color Palette

Màu và font là token theo theme trong `apps/web/src/index.css`, gắn bằng `data-theme` trên `<html>`. Admin (role `operator`) chọn theme cho toàn site ở trang Tài khoản (`PUT /site/theme`); mọi người đọc `GET /site/theme`. `?theme=soft` chỉ xem thử, không lưu. Viền, bóng và độ nổi của từng theme nằm ở `apps/web/src/styles/skins.css`. CSS chỉ đọc token, không ghi hex trực tiếp (trừ khung video luôn tối). Nền phẳng, không gradient.

| Theme | Mặc định | Nền / khối | Accent | Font | Chiều sâu |
| --- | --- | --- | --- | --- | --- |
| `brutal` (Khối thô) | có | `#fff4d6` kem / `#ffffff`, nhấn `#ffe14d` vàng | `#ff5c39` cam | Space Grotesk | viền đen 2–3px, bóng cứng 4px |
| `soft` (Gối mềm) | | `#e4e8ee` một màu xám | `#2f5bea` xanh | Manrope | bóng mềm hai chiều, ô nhập lõm |

Token dùng chung: `--bg`, `--surface-0` (trang, ô nhập), `--surface-1` (panel), `--surface-2` (hover, badge), `--surface-3` (active), `--line`, `--line-strong`, `--ink`, `--muted`, `--muted-2`, `--accent`, `--accent-ink`, `--on-accent`, `--ok`, `--ok-strong`, `--warn`, `--danger`, `--hero-from`, `--hero-to`, `--font-display`, `--font-ui`, `--font-mono`.

### Typography

| Element | Font | Weight | Size | Letter-spacing |
| --- | --- | --- | --- | --- |
| H1 (Hero) | `--font-display` | 500 | 56px (desktop) / 40px (mobile) | -0.03em |
| H2 (Section) | `--font-display` | 500 | 40px / 32px | -0.02em |
| H3 (Card) | `--font-display` | 500 | 24px / 20px | -0.01em |
| Kicker | `--font-ui` | 500 | 12px | 0.18em (uppercase) |
| Body | `--font-ui` | 400 | 16px / 15px | normal |
| Small / Meta | `--font-ui` | 400 | 13px | normal |
| Button | `--font-ui` | 500 (`brutal`: 700) | 14px | 0.02em |

Cả hai font đều hỗ trợ tiếng Việt (dấu) tốt.

### Spacing Scale

```
4px  8px  12px  16px  20px  24px  32px  48px  64px  80px  96px  128px
```

Section padding: `96px 24px` (desktop), `64px 16px` (mobile).

## Design Principles

### 1. Dark Premium Feel
- Dark background tạo cảm giác premium, cinematic — phù hợp với sản phẩm video
- Sử dụng subtle gradient và glassmorphism cho depth
- Không dùng pure black (#000), luôn dùng warm dark tones

### 2. Motion & Animation
- **Entrance animations:** Fade-in + slight translate-up khi scroll vào viewport (Intersection Observer)
- **Hover effects:** Subtle scale (1.02), border glow, color transition
- **Duration:** 300ms–500ms cho transitions, ease-out timing
- **Không lạm dụng:** Chỉ animate elements quan trọng, không animate mọi thứ

### 3. Responsive Design (Mobile-First)

| Breakpoint | Width | Layout |
| --- | --- | --- |
| Mobile | < 640px | Single column |
| Tablet | 640px – 1024px | 2 columns |
| Desktop | > 1024px | Multi-column, max-width 1200px |

### 4. Accessibility
- Contrast ratio ≥ 4.5:1 cho body text, ≥ 3:1 cho large text
- Focus-visible outlines trên tất cả interactive elements
- Alt text cho tất cả images
- Semantic HTML: `<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`
- Skip-to-content link

## Landing Page Sections

### Header / Navigation
- Sticky header, transparent → solid on scroll
- Logo + nav links + language switcher + CTA button
- Mobile: hamburger menu
- Height: 64px

### Hero Section
- Full-viewport height (100vh - header)
- Headline (Fraunces), subtitle (Public Sans), primary CTA
- Background: subtle gradient hoặc animated grid
- Demo video thumbnail có thể embed

### Features Section
- Grid 3 columns (desktop), 1 column (mobile)
- Icon + title + description cho mỗi feature
- Subtle card với border và hover effect

### How It Works
- Step-by-step flow (3–4 steps)
- Visual connection giữa các steps (line/arrow)
- Mỗi step: number + icon + title + description

### Demo / Screenshots
- Video player (9:16 aspect ratio, existing style)
- Carousel hoặc grid cho screenshots
- Real demo videos từ `docs/demo/`

### Use Cases
- Cards cho drama / news / knowledge
- Mỗi card: icon + title + description + sample output

### FAQ
- Accordion pattern
- Animate open/close

### CTA Section
- Background gradient hoặc accent color
- Headline + CTA button
- Không lặp lại quá nhiều info

### Footer
- Logo + links + language switcher
- Copyright
- Social links (nếu có)

## Interaction States

```css
/* Button states */
button:hover     { background: var(--accent-hover); transform: translateY(-1px); }
button:active    { transform: translateY(0); }
button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
button:disabled  { opacity: 0.5; cursor: not-allowed; }

/* Card hover */
.card:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }

/* Link hover */
a:hover { color: var(--accent-hover); text-decoration-color: var(--accent); }
```

## Không làm

- ❌ Emoji trong UI chính thức
- ❌ Nội dung placeholder giả (lorem ipsum)
- ❌ Quá nhiều animation gây rối
- ❌ Auto-play video với âm thanh
- ❌ Pop-up / modal không cần thiết
- ❌ Gradient quá sặc sỡ, neon
