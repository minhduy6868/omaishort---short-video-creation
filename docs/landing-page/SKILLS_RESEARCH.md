# Skills Research — Landing Page

## Phương pháp nghiên cứu

Tìm kiếm GitHub repositories cho Agent Skills liên quan đến:
1. Frontend Design / UI/UX
2. Responsive Web Design
3. Technical SEO
4. Internationalization (i18n)
5. Accessibility (WCAG)
6. Web Performance

## Kết quả tìm kiếm

### 1. https://github.com/anthropics/skills

| Tiêu chí | Đánh giá |
| --- | --- |
| Tồn tại | ✅ Tồn tại (Anthropic official, open standard agentskills.io) |
| Nội dung | Modular skill folders (`SKILL.md`): `frontend-design`, `theme-factory`, `web-artifacts-builder`, document workflows |
| License | Mixed: Apache 2.0 (example skills) / Source-Available (document skills) |
| Liên quan | `frontend-design` skill — hướng dẫn tạo UI bespoke, tránh template AI generic |
| Quyết định | ⚠️ Tham khảo nguyên tắc `frontend-design`, không cài vào dự án |

### 2. https://github.com/vercel-labs/agent-skills

| Tiêu chí | Đánh giá |
| --- | --- |
| Tồn tại | ✅ Tồn tại (Vercel Labs, MIT license) |
| Nội dung | `web-design-guidelines` (100+ rules: WCAG AA, responsive, semantic HTML, ARIA), `react-best-practices`, `composition-patterns` |
| License | MIT |
| Liên quan | Rất cao — trực tiếp target React performance, bundle optimization, accessibility |
| Quyết định | ⚠️ Tham khảo `web-design-guidelines` và `react-best-practices` làm checklist, không fork vào dự án |

### 3. https://github.com/nextlevelbuilder/ui-ux-pro-max-skill

| Tiêu chí | Đánh giá |
| --- | --- |
| Tồn tại | ✅ Tồn tại (MIT, 130k+ stars/bookmarks) |
| Nội dung | 67+ UI styles (Bento Grid, Glassmorphism, SaaS Dark Mode…), 161+ color palettes, 57+ font pairings, 161+ reasoning rules |
| License | MIT |
| Liên quan | Rất cao — design director cho landing page, palette, typography, hero section, responsive layouts |
| Quyết định | ⚠️ Tham khảo design guidelines, không cài trực tiếp — dự án đã có design system riêng |

> **Ghi chú:** Cả 3 repo đều tồn tại và có nội dung hữu ích. Tuy nhiên, chúng ta **không cài đặt** chúng vào dự án vì:
> 1. Dự án đã có hệ thống `.cursor/skills/` riêng (tuân thủ `AGENTS.md`)
> 2. Các skills này là hướng dẫn cho agent, không phải runtime dependencies
> 3. Sẽ áp dụng nguyên tắc thiết kế của chúng (dark premium, WCAG AA, mobile-first) như reference
> 4. Không chạy script từ nguồn bên ngoài — chỉ đọc và tham khảo

## Existing Project Skills (Tái sử dụng)

Dự án đã có hệ thống skills riêng trong `.cursor/skills/`:

| Skill | Liên quan | Sử dụng cho Landing Page |
| --- | --- | --- |
| `frontend-ui` | ✅ Cao | Tuân thủ conventions: Fraunces + Public Sans fonts, charcoal panel, terracotta accent, `credentials: include`, `tsc --noEmit` |
| `refactor` | ✅ Trung bình | Khi tách `App.tsx` thành components |
| `test` | ✅ Trung bình | TypeScript check sau mỗi thay đổi |

## Libraries đề xuất (Thay cho external skills)

Thay vì cài external Agent Skills, sử dụng các libraries đã kiểm chứng:

### i18n

| Library | Version | License | Lý do |
| --- | --- | --- | --- |
| `i18next` | ^24.0.0 | MIT | Industry standard, React 19 compatible |
| `react-i18next` | ^15.0.0 | MIT | Official React binding |
| `i18next-browser-languagedetector` | ^8.0.0 | MIT | Auto-detect browser language |

### SEO

| Library | Version | License | Lý do |
| --- | --- | --- | --- |
| `react-helmet-async` | ^2.0.0 | Apache-2.0 | Dynamic `<head>` management, SSR-ready |

### Routing

| Library | Version | License | Lý do |
| --- | --- | --- | --- |
| `react-router-dom` | ^7.0.0 | MIT | Standard React router, path-based i18n |

### Animations

Không thêm library animation. Sử dụng:
- CSS `@keyframes` và `transition`
- Intersection Observer API (native browser)
- `prefers-reduced-motion` media query

### Accessibility

Không cần library riêng. Tuân thủ WCAG 2.1 AA qua:
- Semantic HTML
- ARIA attributes khi cần
- Focus management
- Color contrast checking (manual + Lighthouse)

## Tổng kết

| Loại | Quyết định |
| --- | --- |
| External Agent Skills | ⚠️ Tồn tại, tham khảo nguyên tắc — không cài vào dự án |
| Project Skills | ✅ Tái sử dụng `frontend-ui`, `refactor`, `test` |
| NPM Libraries | ✅ Thêm 5 packages nhỏ: i18next, react-i18next, detector, react-helmet-async, react-router-dom |
| CSS Framework | ❌ Giữ vanilla CSS — không thêm Tailwind |
| Animation Library | ❌ Dùng CSS native + Intersection Observer |
