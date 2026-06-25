"""
ai_api.py – AI generation wrappers for images, logos, and video.
Falls back gracefully when optional APIs are unavailable.
"""

import asyncio
import io
import logging
import os
import time
import uuid
from typing import Optional

import aiohttp
import config

logger = logging.getLogger(__name__)

# ─── helpers ──────────────────────────────────────────────────────────────────

async def _download_url(url: str) -> Optional[bytes]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception as e:
        logger.error(f"_download_url error: {e}")
    return None


# ─── OpenAI DALL·E (image / logo) ─────────────────────────────────────────────

async def generate_image_openai(prompt: str, size: str = "1024x1024") -> Optional[bytes]:
    """Generate an image via OpenAI Images API (DALL·E 3)."""
    if not config.OPENAI_API_KEY or config.OPENAI_API_KEY.startswith("sk-xxx"):
        logger.warning("OpenAI API key not configured.")
        return None
    url = "https://api.openai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": size,
        "response_format": "url",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=90)) as resp:
                data = await resp.json()
                if resp.status == 200:
                    img_url = data["data"][0]["url"]
                    return await _download_url(img_url)
                else:
                    logger.error(f"OpenAI error {resp.status}: {data}")
    except Exception as e:
        logger.error(f"generate_image_openai exception: {e}")
    return None


async def edit_image_openai(image_bytes: bytes, prompt: str) -> Optional[bytes]:
    """Edit an existing image using OpenAI DALL·E edit endpoint."""
    if not config.OPENAI_API_KEY or config.OPENAI_API_KEY.startswith("sk-xxx"):
        return None
    url = "https://api.openai.com/v1/images/edits"
    headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
    try:
        data = aiohttp.FormData()
        data.add_field("image", image_bytes, filename="image.png", content_type="image/png")
        data.add_field("prompt", prompt)
        data.add_field("n", "1")
        data.add_field("size", "1024x1024")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=120)) as resp:
                result = await resp.json()
                if resp.status == 200:
                    img_url = result["data"][0]["url"]
                    return await _download_url(img_url)
                else:
                    logger.error(f"OpenAI edit error {resp.status}: {result}")
    except Exception as e:
        logger.error(f"edit_image_openai exception: {e}")
    return None


# ─── Stability AI (fallback image) ────────────────────────────────────────────

async def generate_image_stability(prompt: str) -> Optional[bytes]:
    """Generate image via Stability AI REST API (fallback)."""
    if not config.STABILITY_API_KEY or config.STABILITY_API_KEY.startswith("sk-xxx"):
        logger.warning("Stability API key not configured.")
        return None
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
    headers = {
        "Authorization": f"Bearer {config.STABILITY_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "text_prompts": [{"text": prompt, "weight": 1}],
        "cfg_scale": 7,
        "height": 1024,
        "width": 1024,
        "samples": 1,
        "steps": 30,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=90)) as resp:
                result = await resp.json()
                if resp.status == 200:
                    import base64
                    b64 = result["artifacts"][0]["base64"]
                    return base64.b64decode(b64)
                else:
                    logger.error(f"Stability error {resp.status}: {result}")
    except Exception as e:
        logger.error(f"generate_image_stability exception: {e}")
    return None


# ─── Video generation via Runway ML ───────────────────────────────────────────

async def generate_video_runway(prompt: str) -> Optional[bytes]:
    """
    Runway Gen-2 / Gen-3 text-to-video.
    Polls until the job completes then downloads the MP4.
    """
    if not config.RUNWAY_API_KEY or config.RUNWAY_API_KEY.startswith("your_runway"):
        logger.warning("Runway API key not configured.")
        return None

    headers = {
        "Authorization": f"Bearer {config.RUNWAY_API_KEY}",
        "Content-Type": "application/json",
        "X-Runway-Version": "2024-11-06",
    }
    # Submit generation task
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.dev.runwayml.com/v1/text_to_video",
                json={"promptText": prompt, "model": "gen4_turbo", "ratio": "1280:768", "duration": 5},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                data = await resp.json()
                if resp.status not in (200, 201):
                    logger.error(f"Runway submit error {resp.status}: {data}")
                    return None
                task_id = data.get("id")
                if not task_id:
                    return None

            # Poll for completion (max 5 min)
            for _ in range(60):
                await asyncio.sleep(5)
                async with session.get(
                    f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as poll:
                    status_data = await poll.json()
                    status = status_data.get("status")
                    if status == "SUCCEEDED":
                        video_url = status_data["output"][0]
                        return await _download_url(video_url)
                    elif status in ("FAILED", "CANCELLED"):
                        logger.error(f"Runway task {status}: {status_data}")
                        return None
    except Exception as e:
        logger.error(f"generate_video_runway exception: {e}")
    return None


async def edit_video_runway(video_bytes: bytes, prompt: str) -> Optional[bytes]:
    """
    Runway video-to-video edit.  Uploads source video then runs generation.
    """
    if not config.RUNWAY_API_KEY or config.RUNWAY_API_KEY.startswith("your_runway"):
        return None

    headers = {
        "Authorization": f"Bearer {config.RUNWAY_API_KEY}",
        "X-Runway-Version": "2024-11-06",
    }
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Upload source video as an asset
            form = aiohttp.FormData()
            form.add_field("file", video_bytes, filename="source.mp4", content_type="video/mp4")
            async with session.post(
                "https://api.dev.runwayml.com/v1/assets",
                data=form, headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as up_resp:
                up_data = await up_resp.json()
                if up_resp.status not in (200, 201):
                    logger.error(f"Runway upload error: {up_data}")
                    return None
                asset_uri = up_data.get("url") or up_data.get("uri")

            # 2. Submit video-to-video task
            async with session.post(
                "https://api.dev.runwayml.com/v1/video_to_video",
                json={"promptText": prompt, "model": "gen4_turbo",
                      "promptVideo": asset_uri, "duration": 5},
                headers={**headers, "Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                data = await resp.json()
                if resp.status not in (200, 201):
                    logger.error(f"Runway v2v submit error: {data}")
                    return None
                task_id = data.get("id")
                if not task_id:
                    return None

            # 3. Poll
            for _ in range(60):
                await asyncio.sleep(5)
                async with session.get(
                    f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as poll:
                    status_data = await poll.json()
                    status = status_data.get("status")
                    if status == "SUCCEEDED":
                        return await _download_url(status_data["output"][0])
                    elif status in ("FAILED", "CANCELLED"):
                        return None
    except Exception as e:
        logger.error(f"edit_video_runway exception: {e}")
    return None


# ─── Public dispatch functions ────────────────────────────────────────────────

async def generate_logo(prompt: str) -> Optional[bytes]:
    """Logo = image with logo-style prefix; try OpenAI then Stability."""
    styled = f"Professional vector logo design: {prompt}. Clean, minimalistic, high quality."
    result = await generate_image_openai(styled)
    if not result:
        result = await generate_image_stability(styled)
    return result


async def generate_image(prompt: str) -> Optional[bytes]:
    result = await generate_image_openai(prompt)
    if not result:
        result = await generate_image_stability(prompt)
    return result


async def generate_video(prompt: str) -> Optional[bytes]:
    return await generate_video_runway(prompt)


async def edit_image(image_bytes: bytes, prompt: str) -> Optional[bytes]:
    result = await edit_image_openai(image_bytes, prompt)
    if not result:
        # fallback: regenerate with prompt (no source image)
        result = await generate_image(prompt)
    return result


async def edit_video(video_bytes: bytes, prompt: str) -> Optional[bytes]:
    return await edit_video_runway(video_bytes, prompt)
