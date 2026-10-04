# Project Overview — omaishort

## Tổng quan

**omaishort** là một Story Video Engine chạy local-first, cho phép người dùng dán (paste) một câu chuyện, URL tin tức, chủ đề kiến thức, hoặc GitHub README để tạo ra video ngắn **1080×1920 @ 30fps** hoàn chỉnh với voiceover, hình ảnh, phụ đề karaoke và nhạc nền.

## Sản phẩm

Ba loại video (kind):

| Kind | Mô tả | Hình ảnh | Giọng / Motion |
| --- | --- | --- | --- |
| `drama` | Video truyện ngắn với khuôn mặt nhất quán (Character Bible) | Passport faces, I2V khi có key | Dialogue hoặc narrator; I2V hoặc Ken Burns |
| `news` | Ảnh ghép từ bài báo + Ken Burns | Ảnh bài báo, Wikimedia | Narrator + Ken Burns |
| `knowledge` | Ảnh ghép editorial + Ken Burns, VO viết trước | Editorial stills theo beat | Narrator + Ken Burns |

## Pipeline

```
kind=drama|news|knowledge
  → analyze (bible + five beats)
  → plan (1 still / scene, 1–3 Ken Burns shots)
  → refs → stills → tts → rescale to real audio
  → karaoke ASS + optional BGM duck
  → I2V when keyed, else Ken Burns → 1080×1920 MP4
```

## Tech Stack hiện tại

| Layer | Công nghệ |
| --- | --- |
| Frontend (Studio) | Vite + React 19 + TypeScript |
| Backend (API + Engine) | Python 3.11 + FastAPI + Pydantic v2 |
| Database | PostgreSQL (production) / SQLite (test) |
| Schema | `packages/schema` — Pydantic v2 models |
| Rendering | FFmpeg (Ken Burns, ASS captions, BGM) |
| TTS | ElevenLabs → edge-tts → silence |
| Image | Pollinations → Gemini → Grok → OpenAI → placeholder |
| Video (I2V) | Grok → HF Spaces → WaveSpeed → Pollinations → Ken Burns |
| Auth | JWT + HttpOnly Cookie + scrypt |
| CI | GitHub Actions (pytest + tsc --noEmit) |

## Repository Layout

```
omaishort/
├── apps/
│   ├── api/          # FastAPI backend + engine + CLI
│   ├── web/          # Vite React studio
│   └── remotion/     # Future preview scaffold
├── packages/schema/  # Pydantic v2 + JSON Schema
├── prompts/          # LLM prompt templates
├── assets/music/     # BGM tracks
├── samples/          # Test story inputs
├── tests/            # pytest suite
├── scripts/          # DB init, skill sync
├── docs/             # Requirements, Research, Roadmap, Auth
└── .cursor/          # Agent skills + rules
```

## Trạng thái hiện tại

- **Branch:** `docs/chuong-03-prd`
- **Commit gần nhất:** `b704c6c docs(course): add chapter 3 PRD`
- **Studio (apps/web):** Functional — auth, job creation, stage polling, storyboard preview, MP4 download
- **Landing Page:** ❌ Chưa có. Hiện tại `apps/web` chỉ là studio nội bộ
- **i18n:** ❌ Chưa có framework i18n cho UI (video output hỗ trợ en/vi)
- **SEO:** ❌ Không có meta tags, OG, structured data, sitemap, robots.txt

## Mục tiêu Landing Page

Xây dựng Landing Page giới thiệu sản phẩm omaishort:
- Modern SaaS / Premium Product style
- Đa ngôn ngữ (vi, en, ja)
- Chuẩn SEO (Lighthouse 90+)
- Responsive (mobile-first)
- Tái sử dụng design tokens và visual identity hiện có
