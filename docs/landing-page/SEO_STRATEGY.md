# SEO Strategy — omaishort Landing Page

## Thực trạng SEO hiện tại

**Không có SEO.** `apps/web/index.html` chỉ chứa:
- `<title>omaishort</title>` (không mô tả)
- Không có meta description
- Không có Open Graph / Twitter Cards
- Không có canonical URL
- Không có hreflang
- Không có robots.txt, sitemap.xml
- Không có structured data (JSON-LD)
- Không có favicon

## Chiến lược SEO

### 1. On-Page SEO

#### Title Tags (per language)

| Lang | Title |
| --- | --- |
| vi | `omaishort — Tạo Video Ngắn Từ Câu Chuyện Bằng AI` |
| en | `omaishort — AI Story-to-Video Engine` |
| ja | `omaishort — AIストーリー動画エンジン` |

#### Meta Description

| Lang | Description |
| --- | --- |
| vi | `Dán câu chuyện, tin tức hoặc chủ đề — omaishort tạo video ngắn 1080×1920 với voiceover, hình ảnh AI và phụ đề karaoke. Chạy local, miễn phí.` |
| en | `Paste a story, news URL, or topic — omaishort creates 1080×1920 short videos with AI voiceover, generated stills, and karaoke captions. Local-first, free.` |
| ja | `ストーリー、ニュースURL、またはトピックを貼り付けるだけ。omaishortがAIナレーション、画像生成、カラオケ字幕付きの1080×1920ショート動画を作成します。` |

### 2. Technical SEO

#### Canonical URLs & Hreflang

Mỗi trang cần:
```html
<link rel="canonical" href="https://omaishort.com/vi" />
<link rel="alternate" hreflang="vi" href="https://omaishort.com/vi" />
<link rel="alternate" hreflang="en" href="https://omaishort.com/en" />
<link rel="alternate" hreflang="ja" href="https://omaishort.com/ja" />
<link rel="alternate" hreflang="x-default" href="https://omaishort.com/en" />
```

#### Open Graph / Twitter Cards

```html
<meta property="og:type" content="website" />
<meta property="og:title" content="omaishort — AI Story-to-Video Engine" />
<meta property="og:description" content="Paste a story, get a 1080×1920 short video with AI voiceover and captions." />
<meta property="og:image" content="https://omaishort.com/og-image.png" />
<meta property="og:url" content="https://omaishort.com/en" />
<meta property="og:locale" content="en_US" />
<meta property="og:locale:alternate" content="vi_VN" />
<meta property="og:locale:alternate" content="ja_JP" />

<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="omaishort — AI Story-to-Video Engine" />
<meta name="twitter:description" content="Paste a story, get a short video." />
<meta name="twitter:image" content="https://omaishort.com/og-image.png" />
```

#### robots.txt

```
User-agent: *
Allow: /
Disallow: /studio
Disallow: /auth
Disallow: /jobs
Disallow: /files
Disallow: /attachments

Sitemap: https://omaishort.com/sitemap.xml
```

#### sitemap.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <url>
    <loc>https://omaishort.com/en</loc>
    <xhtml:link rel="alternate" hreflang="vi" href="https://omaishort.com/vi" />
    <xhtml:link rel="alternate" hreflang="en" href="https://omaishort.com/en" />
    <xhtml:link rel="alternate" hreflang="ja" href="https://omaishort.com/ja" />
  </url>
  <url>
    <loc>https://omaishort.com/vi</loc>
    <xhtml:link rel="alternate" hreflang="vi" href="https://omaishort.com/vi" />
    <xhtml:link rel="alternate" hreflang="en" href="https://omaishort.com/en" />
    <xhtml:link rel="alternate" hreflang="ja" href="https://omaishort.com/ja" />
  </url>
  <url>
    <loc>https://omaishort.com/ja</loc>
    <xhtml:link rel="alternate" hreflang="vi" href="https://omaishort.com/vi" />
    <xhtml:link rel="alternate" hreflang="en" href="https://omaishort.com/en" />
    <xhtml:link rel="alternate" hreflang="ja" href="https://omaishort.com/ja" />
  </url>
</urlset>
```

### 3. Structured Data (JSON-LD)

```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "omaishort",
  "description": "AI-powered story-to-video engine that creates 1080×1920 short videos with voiceover and karaoke captions",
  "applicationCategory": "MultimediaApplication",
  "operatingSystem": "Windows",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "creator": {
    "@type": "Organization",
    "name": "omaishort"
  }
}
```

### 4. Semantic HTML Structure

```html
<body>
  <a href="#main" class="skip-link">Skip to content</a>
  <header role="banner">
    <nav aria-label="Main navigation">...</nav>
  </header>
  <main id="main" role="main">
    <section id="hero" aria-labelledby="hero-title">...</section>
    <section id="features" aria-labelledby="features-title">...</section>
    <section id="how-it-works" aria-labelledby="how-title">...</section>
    <section id="demo" aria-labelledby="demo-title">...</section>
    <section id="use-cases" aria-labelledby="cases-title">...</section>
    <section id="faq" aria-labelledby="faq-title">...</section>
    <section id="cta" aria-labelledby="cta-title">...</section>
  </main>
  <footer role="contentinfo">...</footer>
</body>
```

### 5. Performance

- **Font loading:** `display=swap` (đã có)
- **Image optimization:** WebP format, lazy loading dưới fold
- **Code splitting:** Vite dynamic import cho Studio page
- **CSS:** Inline critical CSS cho above-the-fold
- **Preconnect:** Google Fonts (đã có)

### 6. Mục tiêu Lighthouse (Production)

| Metric | Target | Ghi chú |
| --- | --- | --- |
| Performance | ≥ 90 | Cần đo thực tế sau deploy |
| Accessibility | ≥ 90 | WCAG 2.1 AA |
| Best Practices | ≥ 90 | HTTPS, no mixed content |
| SEO | ≥ 90 | Meta tags, structured data |

> **Lưu ý:** Đây là mục tiêu. Không tuyên bố đạt nếu chưa đo kiểm thực tế trên production.
