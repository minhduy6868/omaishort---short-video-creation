# I18N Strategy — omaishort Landing Page

## Thực trạng i18n hiện tại

- **Không có framework i18n** trong `apps/web`
- Tất cả UI strings hardcode trong `App.tsx` (English, một số sample tiếng Việt)
- Video engine hỗ trợ `language: en | vi` cho TTS và content
- Không có translation files
- Không có language switcher
- Không có URL routing theo ngôn ngữ

## Ngôn ngữ hỗ trợ

| Code | Ngôn ngữ | Vai trò |
| --- | --- | --- |
| `vi` | Tiếng Việt | Primary (thị trường chính) |
| `en` | English | Default / fallback |
| `ja` | 日本語 | Secondary |

## Giải pháp kỹ thuật

### Library: `react-i18next` + `i18next`

**Lý do chọn:**
- Hệ sinh thái lớn nhất cho React i18n
- Hỗ trợ React 19
- Lazy loading translation files
- Namespace support (tách landing vs studio)
- Plugin ecosystem (browser detection, localStorage)
- TypeScript support tốt

**Dependencies:**
```json
{
  "i18next": "^24.0.0",
  "react-i18next": "^15.0.0",
  "i18next-browser-languagedetector": "^8.0.0"
}
```

### Cấu trúc Translation Files

```
src/i18n/
├── index.ts                # i18n initialization
└── locales/
    ├── en/
    │   ├── landing.json    # Landing page strings
    │   ├── studio.json     # Studio UI strings
    │   └── common.json     # Shared strings (nav, footer)
    ├── vi/
    │   ├── landing.json
    │   ├── studio.json
    │   └── common.json
    └── ja/
        ├── landing.json
        ├── studio.json
        └── common.json
```

### i18n Configuration

```typescript
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import enLanding from './locales/en/landing.json';
import enCommon from './locales/en/common.json';
import viLanding from './locales/vi/landing.json';
import viCommon from './locales/vi/common.json';
import jaLanding from './locales/ja/landing.json';
import jaCommon from './locales/ja/common.json';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { landing: enLanding, common: enCommon },
      vi: { landing: viLanding, common: viCommon },
      ja: { landing: jaLanding, common: jaCommon },
    },
    fallbackLng: 'en',
    defaultNS: 'common',
    interpolation: { escapeValue: false },
    detection: {
      order: ['path', 'localStorage', 'navigator'],
      lookupFromPathIndex: 0,
      caches: ['localStorage'],
    },
  });

export default i18n;
```

### URL Strategy

**Path-based routing (SEO-friendly):**

| URL | Ngôn ngữ | Trang |
| --- | --- | --- |
| `/` | Redirect to browser language | — |
| `/en` | English | Landing |
| `/vi` | Tiếng Việt | Landing |
| `/ja` | 日本語 | Landing |
| `/en/studio` | English | Studio |
| `/vi/studio` | Tiếng Việt | Studio |
| `/ja/studio` | 日本語 | Studio |

### Language Switcher

```
[VI ▾] → dropdown: Tiếng Việt | English | 日本語
```

- Vị trí: Header navigation (desktop + mobile)
- Lưu lựa chọn: `localStorage('i18nextLng')`
- Chuyển ngôn ngữ: Update URL path + i18n instance
- Không reload trang

### Translation File Example

**`en/landing.json`:**
```json
{
  "hero": {
    "kicker": "Story Video Engine",
    "title": "Turn any story into a short video",
    "subtitle": "Paste a script, news URL, or topic. omaishort creates a 1080×1920 video with AI voiceover, generated stills, and karaoke captions.",
    "cta_primary": "Try the Studio",
    "cta_secondary": "See how it works"
  },
  "features": {
    "title": "What omaishort does",
    "drama": {
      "title": "Drama Stories",
      "description": "Character Bible faces, five-beat arcs, I2V motion. Your characters stay consistent across every scene."
    },
    "news": {
      "title": "News Shorts",
      "description": "Paste an article URL. Five editorial beats cover the full story with narrator voiceover and Ken Burns stills."
    },
    "knowledge": {
      "title": "Knowledge Explainers",
      "description": "Type a topic or paste a GitHub README. AI writes the script, generates editorial stills, and narrates."
    }
  }
}
```

**`vi/landing.json`:**
```json
{
  "hero": {
    "kicker": "Công cụ tạo video từ câu chuyện",
    "title": "Biến mọi câu chuyện thành video ngắn",
    "subtitle": "Dán kịch bản, URL tin tức, hoặc chủ đề. omaishort tạo video 1080×1920 với giọng đọc AI, hình ảnh và phụ đề karaoke.",
    "cta_primary": "Thử Studio",
    "cta_secondary": "Xem cách hoạt động"
  },
  "features": {
    "title": "omaishort làm được gì",
    "drama": {
      "title": "Truyện ngắn",
      "description": "Nhân vật nhất quán qua Character Bible, cốt truyện 5 nhịp, chuyển động I2V. Mỗi nhân vật giữ nguyên diện mạo xuyên suốt."
    },
    "news": {
      "title": "Tin tức",
      "description": "Dán URL bài báo. Năm nhịp editorial bao quát toàn bộ bài viết với giọng đọc và hiệu ứng Ken Burns."
    },
    "knowledge": {
      "title": "Kiến thức",
      "description": "Nhập chủ đề hoặc dán GitHub README. AI viết kịch bản, tạo hình minh họa và thuyết minh."
    }
  }
}
```

### SEO per Language

Mỗi ngôn ngữ cần:
1. `<html lang="{code}">` — update khi chuyển ngôn ngữ
2. `<title>` và `<meta description>` dịch sang ngôn ngữ tương ứng
3. `hreflang` links cho tất cả phiên bản ngôn ngữ
4. `og:locale` phù hợp

### Nguyên tắc dịch

1. **Không dùng Google Translate.** Nội dung phải tự nhiên và chính xác
2. **Thuật ngữ kỹ thuật** giữ nguyên English (pipeline, Ken Burns, I2V, Character Bible)
3. **Tên sản phẩm** luôn là "omaishort" (không dịch)
4. **CTA** phải rõ ràng và hành động trong mỗi ngôn ngữ
5. **Fallback:** Nếu thiếu key, hiển thị English thay vì key path
