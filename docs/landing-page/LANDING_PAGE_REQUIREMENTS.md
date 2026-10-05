# Landing Page Requirements — omaishort

## Mục tiêu

Xây dựng Landing Page giới thiệu sản phẩm omaishort, thuyết phục người dùng thử Studio.

## Target Users

| User | Nhu cầu | Hành vi mong đợi |
| --- | --- | --- |
| Content Creator | Tạo video ngắn nhanh từ script | Xem demo → Try Studio |
| News Editor | Tự động hóa video tin tức | Xem features → CTA |
| Developer | Tìm hiểu tool mới | Xem How it Works → GitHub |
| Educator | Tạo video kiến thức | Xem use cases → Try Studio |

## Yêu cầu chức năng

### FR-LP1: Header / Navigation
- Logo (text "omaishort" với Fraunces font)
- Navigation links: Features, How it Works, Demo, FAQ
- Language switcher (vi/en/ja)
- CTA button: "Try Studio" / "Thử Studio"
- Sticky on scroll, transparent → solid background
- Mobile: hamburger menu with slide-in panel

### FR-LP2: Hero Section
- Headline nổi bật (Fraunces, 56px desktop)
- Subtitle mô tả giá trị sản phẩm (1–2 câu)
- Primary CTA: "Try the Studio" → navigate to `/studio`
- Secondary CTA: "See how it works" → scroll to #how-it-works
- Visual: animated gradient background hoặc subtle particle effect
- Badge/kicker: "Story Video Engine" (uppercase, accent color)

### FR-LP3: Product Overview
- 3 cards cho 3 loại video: Drama, News, Knowledge
- Mỗi card: icon/illustration + title + description + example output type
- Hover effect với accent border

### FR-LP4: Key Features
- Grid layout (3 columns desktop)
- Features từ product capabilities:
  - Character Bible (consistent faces)
  - Five-beat storytelling
  - AI voiceover (multi-language)
  - Karaoke captions
  - Ken Burns + I2V motion
  - Local-first / privacy
- Mỗi feature: icon + title + short description

### FR-LP5: How It Works
- 4 steps visual flow:
  1. Paste your story / URL / topic
  2. AI analyzes and plans scenes
  3. Engine generates stills, voice, and captions
  4. Download your 1080×1920 video
- Numbered steps with connecting line/arrows
- Optional: mini animation cho mỗi step

### FR-LP6: Demo Section
- Embed real demo videos từ `docs/demo/`
- 2 videos: Lịch sử (Lý Thường Kiệt) + How-to (skills)
- 9:16 video player (270×480 hoặc responsive)
- Play controls, poster image
- Caption mô tả ngắn cho mỗi demo

### FR-LP7: Use Cases / Benefits
- Cards hoặc tabs cho từng use case
- Drama: "Turn confessions and stories into viral shorts"
- News: "Auto-generate video from any news article"
- Knowledge: "Create explainers from any topic or GitHub repo"

### FR-LP8: FAQ Section
- Accordion (click to expand/collapse)
- Minimum 6 questions:
  - "What is omaishort?" / "omaishort là gì?"
  - "Is it free?" / "Có miễn phí không?"
  - "What languages are supported?" / "Hỗ trợ ngôn ngữ nào?"
  - "Do I need cloud API keys?" / "Có cần API key không?"
  - "What video format?" / "Định dạng video?"
  - "Can I use my own images?" / "Có dùng ảnh riêng được không?"
- Nội dung dịch đầy đủ 3 ngôn ngữ

### FR-LP9: Final CTA
- Section nổi bật với gradient background
- Headline: "Ready to create your first short?"
- CTA button → Studio
- Có thể thêm sub-text: "No sign-up required for local CLI"

### FR-LP10: Footer
- Logo + tagline
- Links: GitHub, Documentation, Studio
- Language switcher (duplicate from header)
- Copyright notice

## Yêu cầu phi chức năng

### NFR-LP1: Performance
- First Contentful Paint < 1.5s
- Largest Contentful Paint < 2.5s
- Cumulative Layout Shift < 0.1
- Total bundle size < 200KB (gzip, excluding fonts)

### NFR-LP2: Responsive
- Mobile (< 640px): single column, hamburger nav
- Tablet (640–1024px): 2-column grids
- Desktop (> 1024px): full layout, max-width 1200px

### NFR-LP3: Accessibility
- WCAG 2.1 Level AA
- Keyboard navigable
- Screen reader compatible
- Color contrast ratios met

### NFR-LP4: SEO
- Xem `SEO_STRATEGY.md`

### NFR-LP5: i18n
- Xem `I18N_STRATEGY.md`

### NFR-LP6: Browser Support
- Chrome 90+, Firefox 90+, Safari 15+, Edge 90+
- Mobile: iOS Safari 15+, Chrome Android 90+
