# Bài thực hành 8 — Hai lệnh CI chạy trên máy

Từ gốc repo:

```powershell
apps\api\.venv\Scripts\python.exe -m pytest -q
cd apps\web
npx tsc --noEmit
```

Ghi lại số dòng cuối của pytest. Phiên viết chương này: **135 passed**, 1 warning `StarletteDeprecationWarning` từ `fastapi/testclient.py` (httpx/starlette). Warning không làm job CI fail trừ khi workflow bật `-W error`, và `ci.yml` không bật.

`tsc --noEmit` không in gì khi sạch. Phiên này exit 0.

Không đặt `OPENAI_API_KEY`, `HF_TOKEN`, `XAI_API_KEY` để "cho test thật hơn". Test cố ý không cần chúng.

Đối chiếu: job `api` và job `web` trong `.github/workflows/ci.yml` phải còn đúng `pytest -q` và `npx tsc --noEmit`.
