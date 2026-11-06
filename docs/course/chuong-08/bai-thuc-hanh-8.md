# Bài thực hành 8 — Chạy đủ ba lớp test và làm đỏ một test

## 1. Hai lệnh CI

Từ gốc repo:

```powershell
apps\api\.venv\Scripts\python.exe -m pytest -q
cd apps\web
npx tsc --noEmit
```

Ghi lại dòng cuối của pytest. Phiên 06/11/2026: **144 passed**, 1 warning `StarletteDeprecationWarning` từ `fastapi/testclient.py`. Warning không làm CI fail vì `ci.yml` không bật `-W error`.

`tsc --noEmit` không in gì khi sạch. Phiên này exit 0.

## 2. Test trình duyệt

```powershell
cd apps\web; npm run build; cd ..\..
apps\api\.venv\Scripts\python.exe -m pytest -q tests\test_studio_e2e.py -rs
```

Kỳ vọng `3 passed`. Nếu thấy `3 skipped`, đọc lý do do `-rs` in ra: thiếu `apps/web/dist` hoặc không có Chrome/Edge. Skip không phải pass; ghi rõ trong báo cáo.

## 3. Cố tình làm đỏ

1. Mở `apps/api/omaishort/desktop.py`, đổi `/work"` trong `url = ...` thành `/"`.
2. Chạy `pytest -q tests\test_desktop.py`. Phải thấy `FAILED test_desktop_window_opens_the_studio_not_the_landing`.
3. Trả lại `/work`, chạy lại, phải xanh. `git diff` trên `desktop.py` phải rỗng.

Làm tương tự với `apps/api/omaishort/main.py`: tạm bỏ dòng kiểm `user.get("role") != "operator"`. `test_site_theme_is_public_and_only_operator_changes_it` phải đỏ ở chỗ `creator` nhận 200 thay vì 403. Trả lại dòng đó.

## Không làm

Không đặt `OPENAI_API_KEY`, `HF_TOKEN`, `XAI_API_KEY` để "cho test thật hơn". Test cố ý không cần chúng.

Đối chiếu: job `api` và job `web` trong `.github/workflows/ci.yml` phải còn đúng `pytest -q` và `npx tsc --noEmit`.
