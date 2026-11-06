---
name: local-video-storage
description: Manages local video MP4 storage, job disk artifacts, compaction, orphan cleanup, and Cloudflare D1 storage metadata sync. Use when editing storage.py, files.py, job disk layout, or local video library routes.
---

# Local Video Storage

Read `apps/api/omaishort/storage.py`, `files.py`, `paths.py`, `db.py`.

- **Split storage model**: All relational state (`users`, `refresh_tokens`, `jobs`, `attachments`, `settings`, `storage_json`, attachment `content_b64` backup) lives in **Cloudflare D1** (`omaishort-db` Worker). Rendered video MP4s (`render/short.mp4`) and job working files (`stills/`, `refs/`, `audio/`) live on local disk under `DATA_DIR/jobs/<job_id>/`.
- **Per-job layout**: `data/jobs/<job_id>/` holds `bible.json`, `structure.json`, `storyboard.json`, `timeline.json`, `refs/*.png`, `stills/*.png`, `audio/voiceover.mp3`, `render/captions.ass`, `render/motion.json`, and `render/short.mp4`.
- **Storage inspection (`inspect_job_storage`)**: Computes `mp4_bytes`, `stills_bytes`, `refs_bytes`, `audio_bytes`, `other_bytes`, `total_bytes`, and `mp4_ready` (`render/short.mp4` exists on disk), and persists the summary in `jobs.storage_json` on Cloudflare D1 when a job finishes or is compacted.
- **Compaction (`compact_job_storage`)**: Removes heavy intermediate directories (`stills/sourced`, temporary render scratch files, `audio/voiceover.mp3` if `short.mp4` is already muxed) while preserving `render/short.mp4`, `render/captions.ass`, `render/motion.json`, final `stills/*.png`, `refs/*.png`, `storyboard.json`, and `timeline.json`.
- **Deletion (`delete_job_storage`)**: Unlinks `data/jobs/<job_id>/` safely after verifying `path.resolve().relative_to(DATA_DIR.resolve())`. Never follow symlinks or allow `..` traversal.
- **Access control**: Serving bytes through `/files/{path}` or `/jobs/{id}/download` requires owner or `operator` role via `resolve_public_file()` / `require_job()`. Never expose `.auth_secret`, `omaishort.db`, or `chatgpt-web/`.

