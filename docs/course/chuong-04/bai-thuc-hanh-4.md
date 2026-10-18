# Bài thực hành 4 — Đối chiếu luồng với code

Không vẽ mockup mới. Việc là chỉ ra route.

1. Mở `apps/web/src/main.tsx`. Liệt kê path nào ra `LandingPage`, path nào ra `App`.
2. Mở `apps/web/src/App.tsx`. Viết một câu: người chưa có `user` thì bị đưa đi đâu.
3. Mở `apps/api/omaishort/desktop.py`, hàm `run`. URL cửa sổ desktop là `/` hay `/en`?
4. Trong `HeroSection.tsx` hoặc `CTASection.tsx`, href của nút chính là gì?

Đáp khớp code hiện tại:

- Landing: `/en`, `/vi`, `/ja`
- Chưa login: `/login`
- Desktop: `http://127.0.0.1:8765/`
- CTA: `/work` (rồi `App` đẩy sang `/login` nếu chưa session)

Chạy typecheck khi sửa UI (bài này không sửa UI):

```powershell
cd apps\web
npx tsc --noEmit
```
