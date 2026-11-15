"""Smart scene image search & generation via Grok (xAI / Grok Hub) and ChatGPT (OpenAI / ChatGPT Web + Wikimedia/Openverse)."""

from __future__ import annotations

import asyncio
import io
import json
import re
import shutil
from pathlib import Path

import httpx
from PIL import Image

from omaishort.config import GROK_WEB_ENABLED, GROK_WEB_TIMEOUT_MIN
from omaishort.engine.brief_media import (
    STILL_OVERLAP,
    conform_photo,
    download_photo,
    editorial_candidate_score,
    external_terms_for_beat,
    search_openverse_hits,
    search_wikimedia_hits,
    search_wikipedia_original,
    unique_image_urls,
    visual_terms_for_beat,
    wants_object_photo,
    wikipedia_titles,
)
from omaishort.providers import chatgpt_web, grok_web
from omaishort.providers.image import OpenAIImageProvider, generate_image
from omaishort.providers.llm import complete_json_result, parse_llm_json
from omaishort.providers.placeholder import HEIGHT, WIDTH
from omaishort.providers.xai_image import XaiImageProvider

_CONVERSATION = "https://grok.com/rest/app-chat/conversations/new"
_ASSETS = "https://assets.grok.com"
_IMG_URL_RE = re.compile(
    r"https?://[^\s\"'<>)+]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'<>)+]*)?",
    re.I,
)


def _extract_grok_stream_image_urls(raw: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    def _add(u: str) -> None:
        u = u.strip()
        if not u:
            return
        if u.startswith("/"):
            u = f"{_ASSETS}{u}"
        if not u.startswith("http"):
            return
        if u not in seen:
            seen.add(u)
            urls.append(u)

    for line in raw.splitlines():
        blob = line.strip()
        if blob.startswith("data:"):
            blob = blob[5:].strip()
        if not blob or blob == "[DONE]" or not blob.startswith("{"):
            continue
        try:
            frame = json.loads(blob)
        except json.JSONDecodeError:
            continue
        stack: list[object] = [frame]
        visited: set[int] = set()
        while stack:
            curr = stack.pop(0)
            if isinstance(curr, dict):
                ident = id(curr)
                if ident in visited:
                    continue
                visited.add(ident)
                for key in (
                    "imageUrl",
                    "image_url",
                    "mediaUrl",
                    "media_url",
                    "generatedImageUrl",
                    "url",
                ):
                    val = curr.get(key)
                    if isinstance(val, str) and (
                        "assets.grok.com" in val
                        or val.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                    ):
                        _add(val)
                for key in ("imageUrls", "generatedImageUrls", "images", "webSearchResults"):
                    arr = curr.get(key)
                    if isinstance(arr, list):
                        for item in arr:
                            if isinstance(item, str):
                                _add(item)
                            elif isinstance(item, dict):
                                for k2 in ("url", "imageUrl", "image", "thumbnailUrl"):
                                    v2 = item.get(k2)
                                    if isinstance(v2, str):
                                        _add(v2)
                stack.extend(curr.values())
            elif isinstance(curr, list):
                stack.extend(curr)

    for match in _IMG_URL_RE.findall(raw):
        _add(match)
    return urls


async def generate_or_search_via_grok_hub(prompt: str, dest: Path) -> Path | None:
    """Use logged-in Grok Web session (grok.com/imagine) to generate or search an image."""
    if not GROK_WEB_ENABLED or not grok_web.playwright_ok() or not grok_web.is_authed():
        return None
    from playwright.async_api import async_playwright

    timeout_ms = max(45_000, min(120_000, GROK_WEB_TIMEOUT_MIN * 60_000))
    urls: list[str] = []
    cookie_header = ""
    try:
        async with grok_web.session_lock:
            async with async_playwright() as pw:
                launch = grok_web.launch_args(headed=False)
                ctx = await pw.chromium.launch_persistent_context(**launch)
                await grok_web.prepare(ctx)
                try:
                    if not await grok_web.has_session(ctx):
                        grok_web.clear_authed()
                        return None
                    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                    await grok_web.open_imagine(page)
                    body = {
                        "temporary": True,
                        "modelName": "grok-3",
                        "message": f"Generate a vertical 9:16 photographic image (no text overlay): {prompt[:500]}",
                        "enableImageGeneration": True,
                    }
                    status, stream = await grok_web.page_fetch(
                        page,
                        _CONVERSATION,
                        body=json.dumps(body),
                        timeout_ms=timeout_ms,
                    )
                    if status < 400 and stream:
                        urls = _extract_grok_stream_image_urls(stream)
                    cookies = await ctx.cookies()
                    cookie_header = "; ".join(
                        f"{item.get('name')}={item.get('value')}"
                        for item in cookies
                        if grok_web.grok_domain(str(item.get("domain") or ""))
                    )
                finally:
                    await ctx.close()
    except Exception:
        return None

    if not urls:
        return None
    headers = {
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://grok.com/",
        "Cookie": cookie_header,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    for url in urls[:4]:
        tmp = dest.with_suffix(".grok")
        try:
            async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
                res = await client.get(url, headers=headers)
                if res.status_code >= 400 or len(res.content) < 4000:
                    continue
                tmp.write_bytes(res.content)
                conform_photo(tmp, dest)
                return dest
        except Exception:
            continue
        finally:
            tmp.unlink(missing_ok=True)
    return None


async def extract_visual_search_plan(
    query_or_vo: str,
    title: str = "",
    *,
    prefer: str = "auto",
) -> tuple[list[str], list[str], list[str]]:
    """Ask ChatGPT Web or configured LLM (Grok/OpenAI/Gemini) for optimal English visual search queries & Wikipedia titles."""
    system = (
        "You are a visual researcher for a vertical documentary short video.\n"
        "Given a scene narration/prompt and video title, return ONLY valid JSON with:\n"
        '{"queries": ["3-5 specific English photographic search terms for Wikimedia Commons / Openverse"], '
        '"wiki_titles": ["2-3 exact English or Vietnamese Wikipedia article titles that have real photos"], '
        '"image_urls": ["optional direct https image URLs if known"]}\n'
        "Focus on concrete physical subjects, places, historical events, or objects (no abstract words)."
    )
    user = f"Title: {title}\nScene / Query: {query_or_vo[:1000]}"
    data: dict | None = None

    if prefer == "chatgpt" and chatgpt_web.is_authed():
        try:
            raw = await chatgpt_web.complete_json_prompt(system, user)
            parsed = parse_llm_json(raw)
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            data = None

    if data is None:
        try:
            parsed, _provider, _err = await complete_json_result(system, user)
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            data = None

    queries: list[str] = []
    wiki_list: list[str] = []
    img_urls: list[str] = []
    if isinstance(data, dict):
        for q in data.get("queries") or []:
            if isinstance(q, str) and len(q.strip()) >= 3:
                queries.append(q.strip())
        for w in data.get("wiki_titles") or []:
            if isinstance(w, str) and len(w.strip()) >= 2:
                wiki_list.append(w.strip())
        for u in data.get("image_urls") or []:
            if isinstance(u, str) and u.strip().startswith("http"):
                img_urls.append(u.strip())

    # Prefer deterministic object terms from the spoken beat over LLM topic pages.
    for term in external_terms_for_beat(query_or_vo, title) or visual_terms_for_beat(query_or_vo, title):
        if term not in queries:
            queries.insert(0, term)
    # Object-photo beats: do not prepend Inflation/CPI Wikipedia lead images.
    if not wants_object_photo(query_or_vo):
        for wtitle in wikipedia_titles("", query_or_vo):
            if wtitle not in wiki_list:
                wiki_list.append(wtitle)
    else:
        wiki_list = []
    if query_or_vo.strip() and len(query_or_vo.strip()) <= 80:
        queries.insert(0, query_or_vo.strip())

    return queries[:6], wiki_list[:4], unique_image_urls(img_urls, limit=4)


async def search_and_download_web_still(
    query_or_vo: str,
    title: str,
    dest: Path,
    *,
    prefer: str = "auto",
) -> tuple[Path | None, str]:
    """Search Wikimedia/Openverse, rank by beat overlap, then conform to 9:16."""
    queries, wiki_list, direct_urls = await extract_visual_search_plan(query_or_vo, title, prefer=prefer)
    ranked: list[tuple[float, str, str]] = []
    for u in direct_urls:
        ranked.append((editorial_candidate_score(u, query_or_vo, query=query_or_vo), u, f"{prefer}_direct"))
    if not wants_object_photo(query_or_vo):
        for wpage in wiki_list:
            for u in await search_wikipedia_original(wpage):
                tag = f"{prefer}_wikipedia" if prefer in {"grok", "chatgpt"} else "wikipedia"
                ranked.append((editorial_candidate_score(u, query_or_vo, caption=wpage), u, tag))
    for q in queries:
        tag_w = f"{prefer}_wikimedia" if prefer in {"grok", "chatgpt"} else "wikimedia"
        tag_o = f"{prefer}_openverse" if prefer in {"grok", "chatgpt"} else "openverse"
        for u, label in await search_wikimedia_hits(q, limit=6):
            ranked.append((editorial_candidate_score(u, query_or_vo, caption=label, query=q), u, tag_w))
        for u, label in await search_openverse_hits(q, limit=6):
            ranked.append((editorial_candidate_score(u, query_or_vo, caption=label, query=q), u, tag_o))

    ranked.sort(key=lambda row: row[0], reverse=True)
    seen: set[str] = set()
    dest.parent.mkdir(parents=True, exist_ok=True)
    for score, url, tag in ranked:
        if not url or url in seen:
            continue
        if score < STILL_OVERLAP and wants_object_photo(query_or_vo):
            continue
        seen.add(url)
        saved = await download_photo(url, dest)
        if saved and saved.is_file():
            return saved, tag
    # Last resort: best remaining download even under the gate (still better than random wiki lead).
    for score, url, tag in ranked:
        if not url or url in seen:
            continue
        seen.add(url)
        saved = await download_photo(url, dest)
        if saved and saved.is_file():
            return saved, tag
    return None, "none"


def _copy_still(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest


async def resolve_scene_still(
    *,
    prompt: str,
    vo: str,
    title: str,
    dest: Path,
    source: str = "auto",
    refs: list[Path] | None = None,
    editorial: bool = False,
    skip_remote: bool = False,
    action: str = "",
    context: str = "",
    avoid_urls: set[str] | None = None,
) -> tuple[Path, str]:
    """Generate or search a scene still using the requested source ('grok', 'chatgpt', 'search', or 'auto')."""
    del avoid_urls  # reserved for callers that already reserved article/CC URLs
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = (source or "auto").strip().lower()
    search_text = prompt.strip() or vo.strip() or title.strip()
    beat_blob = (context or " ".join(p for p in (action, vo) if p).strip() or vo).strip()
    # Editorial search must follow the spoken beat + action, not the full BRIEF blob.
    if editorial and beat_blob:
        query_input = beat_blob
        terms = external_terms_for_beat(beat_blob, title)
        if terms:
            query_input = f"{terms[0]}\n{beat_blob}"
    else:
        query_input = (
            f"{search_text}\n{vo.strip()}".strip()
            if search_text and search_text != vo.strip()
            else (vo.strip() or search_text)
        )

    if skip_remote:
        return await generate_image(search_text, dest, refs, photo=False, skip_remote=True)

    if src == "grok":
        # Parallel: xAI / hub search path + photographic generate — take first usable, prefer search.
        search_dest = dest.with_name(f"{dest.stem}.search{dest.suffix}")
        gen_dest = dest.with_name(f"{dest.stem}.gen{dest.suffix}")

        async def _grok_search() -> tuple[Path | None, str]:
            xai = await XaiImageProvider().generate(search_text, search_dest, refs)
            if xai and xai.is_file():
                return xai, "grok_xai"
            ghub = await generate_or_search_via_grok_hub(search_text, search_dest)
            if ghub and ghub.is_file():
                return ghub, "grok_hub"
            return await search_and_download_web_still(query_input, title, search_dest, prefer="grok")

        found_pair, gen_pair = await asyncio.gather(
            _grok_search(),
            generate_image(search_text, gen_dest, refs, photo=True),
            return_exceptions=True,
        )
        if not isinstance(found_pair, BaseException):
            found, tag = found_pair
            if found and found.is_file():
                return _copy_still(found, dest), tag
        if not isinstance(gen_pair, BaseException):
            gpath, gtag = gen_pair
            if gpath and Path(gpath).is_file():
                return _copy_still(Path(gpath), dest), gtag
        return await generate_image(search_text, dest, refs, photo=False)

    if src == "chatgpt":
        search_dest = dest.with_name(f"{dest.stem}.search{dest.suffix}")
        gen_dest = dest.with_name(f"{dest.stem}.gen{dest.suffix}")

        async def _chatgpt_search() -> tuple[Path | None, str]:
            oai = await OpenAIImageProvider().generate(search_text, search_dest, refs)
            if oai and oai.is_file():
                return oai, "chatgpt_openai"
            return await search_and_download_web_still(query_input, title, search_dest, prefer="chatgpt")

        found_pair, gen_pair = await asyncio.gather(
            _chatgpt_search(),
            generate_image(search_text, gen_dest, refs, photo=True),
            return_exceptions=True,
        )
        if not isinstance(found_pair, BaseException):
            found, tag = found_pair
            if found and found.is_file():
                return _copy_still(found, dest), tag
        if not isinstance(gen_pair, BaseException):
            gpath, gtag = gen_pair
            if gpath and Path(gpath).is_file():
                return _copy_still(Path(gpath), dest), gtag
        return await generate_image(search_text, dest, refs, photo=False)

    if src == "search":
        found, tag = await search_and_download_web_still(query_input, title, dest, prefer="auto")
        if found and found.is_file():
            return found, tag
        return await generate_image(search_text, dest, refs, photo=True)

    # Default 'auto': race web search + AI generate so stills don't wait in series.
    if editorial:
        search_dest = dest.with_name(f"{dest.stem}.search{dest.suffix}")
        gen_dest = dest.with_name(f"{dest.stem}.gen{dest.suffix}")
        found_pair, gen_pair = await asyncio.gather(
            search_and_download_web_still(query_input, title, search_dest, prefer="auto"),
            generate_image(search_text, gen_dest, refs, photo=True),
            return_exceptions=True,
        )
        if not isinstance(found_pair, BaseException):
            found, tag = found_pair
            if found and found.is_file():
                return _copy_still(found, dest), tag
        if not isinstance(gen_pair, BaseException):
            gpath, gtag = gen_pair
            if gpath and Path(gpath).is_file():
                return _copy_still(Path(gpath), dest), gtag
        ghub = await generate_or_search_via_grok_hub(search_text, dest)
        if ghub and ghub.is_file():
            return ghub, "grok_hub"
    return await generate_image(search_text, dest, refs, photo=not editorial)
