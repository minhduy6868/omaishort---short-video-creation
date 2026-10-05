# Implementation Plan — omaishort Landing Page

## Tổng quan

Chuyển đổi `apps/web` từ studio-only thành landing page + studio, với i18n và SEO chuyên nghiệp, tối ưu hiệu suất và trải nghiệm người dùng.

---

## Các Quyết Định Thiết Kế & Triển Khai (Chính Thức)

### 1. Domain Name & SEO Canonical URLs
- **Domain mặc định:** `https://omaishort.com` được cấu hình làm fallback mặc định trong `src/config/site.ts`.
- **Linh hoạt qua biến môi trường:** Sử dụng `import.meta.env.VITE_SITE_URL` (hoặc `NEXT_PUBLIC_SITE_URL`). **Không hardcode domain** trực tiếp trong bất kỳ component nào.
- **Kiểm soát Canonical trên Production:** Thêm cờ `SITE_CONFIG.enableCanonical` (điều khiển qua `VITE_ENABLE_CANONICAL`). Nếu domain chưa xác nhận chính thức, không phát hành canonical URLs chỉ tới domain placeholder trên môi trường production.
- **Sitemap & Hreflang:** Đã tạo sitemap.xml và thẻ `hreflang` động cho `vi`, `en`, `ja`, và `x-default`.

### 2. Demo Videos
- **Nguồn video:** Tái sử dụng các video có sẵn trong `docs/demo/` (`knowledge-history.mp4`, `knowledge-skills.mp4` cùng poster JPG).
- **Phục vụ tĩnh:** Đã sao chép các file demo từ `docs/demo/` sang thư mục public `apps/web/public/demo/` để đảm bảo được phục vụ trực tiếp qua HTTP.
- **Component `VideoDemo`:** Tạo component `VideoDemo.tsx` hỗ trợ cả video local và external URL (YouTube/CDN).
- **Tối ưu hóa:** Sử dụng Lazy loading qua `IntersectionObserver`, poster image, khung hình dọc 9:16 responsive, nút điều khiển Play/Pause/Mute hiện đại.
- **Không tự động phát âm thanh:** Video được mặc định `muted` hoặc yêu cầu người dùng nhấn Play để mở tiếng.

### 3. Favicon & Open Graph (OG Image)
- **Asset bộ nhận diện thương hiệu:** Đã tạo các assets chuẩn tại `apps/web/public/`:
  - `favicon.svg` (Biểu tượng SVG vector hiện đại)
  - `favicon.png` (64×64 px PNG)
  - `apple-touch-icon.png` (180×180 px PNG)
  - `og-image.png` (1200×630 px PNG Banner với gradient dark-mode, thông tin sản phẩm và minh họa khung phone 9:16).
- **Khai báo trong HTML & Hook:** Tích hợp trực tiếp vào `index.html` và cập nhật trong hook `useSEO.ts`.

### 4. Đa ngôn ngữ i18n (Tiếng Việt, Tiếng Anh, Tiếng Nhật)
- **Hỗ trợ 3 ngôn ngữ:** `vi` (Tiếng Việt), `en` (English), `ja` (日本語).
- **Chất lượng dịch tiếng Nhật:** Ngôn ngữ tự nhiên, chuyên nghiệp cho sản phẩm công nghệ. Giữ nguyên tên thương hiệu và thuật ngữ kỹ thuật: *omaishort, ElevenLabs, edge-tts, Character Bible, Ken Burns, I2V, TikTok, Reels, Shorts*.
- **Theo dõi kiểm duyệt bản dịch:** Thêm trường metadata `_meta` trong các file translation (`common.json`, `landing.json`) với `needsReview: false` và thông tin kiểm duyệt rõ ràng.
- **Khóa dịch đầy đủ:** Đảm bảo 100% đồng bộ keys giữa cả 3 ngôn ngữ.

---

## Giai đoạn triển khai (Phases)

### Phase A: Foundation (Hoàn thành ✅)
1. **Dependencies:** `react-router-dom`, `react-i18next`, `i18next`, `i18next-browser-languagedetector`, `react-helmet-async` đã được cài đặt và cấu hình.
2. **Routing:** Setup `BrowserRouter` hỗ trợ `/:lang` (Landing Page) và `/:lang/studio` (Studio Page).
3. **i18n:** Đã tích hợp `index.ts` và đầy đủ các file JSON cho `en`, `vi`, `ja`.
4. **SEO Infrastructure:** `useSEO` hook, `src/config/site.ts`, `robots.txt`, `sitemap.xml`, `favicon.svg`, `og-image.png`.

### Phase B: Landing Page UI & Components (Hoàn thành ✅)
1. **Header & Navigation:** Sticky header với scroll blur, language switcher, mobile drawer.
2. **Hero Section:** Headline hấp dẫn, visual glow effect, CTA buttons.
3. **Features Section:** Grid 3 cột giới thiệu Drama, News, Knowledge shorts.
4. **Capabilities Section:** Key features (Character Bible, 5-Beat Storytelling, AI VO, Karaoke Captions, Cinematic Motion, Local-First).
5. **How It Works:** Flow 4 bước trực quan.
6. **Demo Section:** Tích hợp component `VideoDemo` chạy video thực tế local (`knowledge-history.mp4`, `knowledge-skills.mp4`).
7. **Use Cases & Benefits:** Ứng dụng thực tế và ví dụ mẫu.
8. **FAQ Section:** Accordion 7+ câu hỏi thường gặp.
9. **CTA & Footer:** Final call to action và footer liên kết.

### Phase C: Polish, Optimization & Validation (Đang thực hiện 🔄)
1. **Type Checking:** Chạy `npx tsc --noEmit` đạt 0 lỗi TypeScript.
2. **Performance:** Lazy loading cho VideoDemo và poster images.
3. **Accessibility:** Phím tắt skip-link, `aria-label`, contrast ratio đạt chuẩn.
4. **Documentation Sync:** Cập nhật `IMPLEMENTATION_PLAN.md`, `SEO_STRATEGY.md`, `I18N_STRATEGY.md`, `UI_UX_GUIDELINES.md`.

---

## Nguyên Tắc Tuân Thủ Khi Làm Việc

1. **Không phá vỡ Studio:** Giữ studio nguyên vẹn tại `/:lang/studio`.
2. **Không tự động push hay deploy:** Mọi bước build & check đều thực hiện local. Không push GitHub hoặc deploy khi chưa có yêu cầu từ người dùng.
3. **Kiểm tra TypeScript strict:** Luôn đảm bảo `npx tsc --noEmit` pass sạch.
