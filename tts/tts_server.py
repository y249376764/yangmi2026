#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小听 · Edge-TTS HTTP 服务（六音色引擎专用，接口与原 5.45.99.149:8075 完全一致）

接口：
  GET /tts?t=文本&v=音色&r=语速(-50~50)&p=音调(-50~50)&s=风格
  返回 audio/mpeg（mp3）

启动：
  pip install edge-tts aiohttp
  python tts_server.py            # 默认 0.0.0.0:8075
  PORT=9000 python tts_server.py
"""
import asyncio
import os
import re
import edge_tts
from aiohttp import web

PORT = int(os.environ.get("PORT", "8075"))
HOST = os.environ.get("HOST", "0.0.0.0")
MAX_CHARS = 4000

# 允许的音色白名单（防止被当免费代理刷其它语言）
ALLOWED = {v.lower() for v in [
    "zh-CN-YunjianNeural", "zh-CN-YunxiNeural", "zh-CN-YunyiMultilingualNeural",
    "zh-CN-XiaoxiaoNeural", "zh-CN-XiaochenNeural", "zh-CN-XiaoxiaoMultilingualNeural",
    "zh-CN-YunyangNeural", "zh-CN-YunzeNeural", "zh-CN-YunhaoNeural", "zh-CN-YunfengNeural",
    "zh-CN-YunyeNeural", "zh-CN-YunxiaNeural", "zh-CN-XiaoyiNeural", "zh-CN-XiaohanNeural",
    "zh-CN-XiaomengNeural", "zh-CN-XiaomoNeural", "zh-CN-XiaoqiuNeural", "zh-CN-XiaoruiNeural",
    "zh-CN-XiaoshuangNeural", "zh-CN-XiaoyanNeural", "zh-CN-XiaoyouNeural", "zh-CN-XiaozhenNeural",
    "zh-CN-liaoning-XiaobeiNeural", "zh-CN-shaanxi-XiaoniNeural",
    "zh-HK-HiuMaanNeural", "zh-HK-WanLungNeural", "zh-TW-HsiaoChenNeural", "zh-TW-YunJheNeural",
]}

# 常见风格 -> edge-tts 的 SSML style（不支持时自动忽略，不影响出声）
STYLE_MAP = {
    "narration-relaxed": "narration-relaxed",
    "newscast": "newscast",
    "cheerful": "cheerful",
    "sad": "sad",
    "angry": "angry",
    "fearful": "fearful",
    "gentle": "gentle",
    "affectionate": "affectionate",
    "calm": "calm",
}


def clamp(v, lo, hi):
    try:
        v = int(float(v))
    except (TypeError, ValueError):
        return 0
    return max(lo, min(hi, v))


def clean(t):
    """去掉会破坏 SSML 的字符，保留段落换行（换行在 TTS 里是自然停顿）"""
    t = t.replace("&", "＆").replace("<", "＜").replace(">", "＞")
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()[:MAX_CHARS]


async def handle_tts(request):
    q = request.rel_url.query
    text = clean(q.get("t", ""))
    if not text:
        return web.Response(status=400, text="missing t")

    voice = q.get("v", "zh-CN-YunjianNeural")
    if voice.lower() not in ALLOWED:
        return web.Response(status=400, text="voice not allowed")

    r = clamp(q.get("r", 0), -50, 50)
    p = clamp(q.get("p", 0), -50, 50)
    style = STYLE_MAP.get(q.get("s", ""), "")

    rate = f"{r:+d}%"
    pitch = f"{p:+d}Hz"

    try:
        if style:
            # 带风格需要 SSML；edge-tts 的 Communicate 支持传率/调，风格用 inner SSML 拼
            ssml = (
                f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
                f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="zh-CN">'
                f'<voice name="{voice}"><mstts:express-as style="{style}" styledegree="1.6">'
                f'<prosody rate="{rate}" pitch="{pitch}">{text}</prosody>'
                f"</mstts:express-as></voice></speak>"
            )
            comm = edge_tts.Communicate(ssml, voice)
        else:
            comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)

        audio = bytearray()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
        if not audio:
            raise RuntimeError("empty audio")
        return web.Response(
            body=bytes(audio),
            content_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=86400",
                     "Accept-Ranges": "bytes"},
        )
    except Exception as e:
        # 风格不被该音色支持时，退回不带风格再试一次
        if style:
            try:
                comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
                audio = bytearray()
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        audio.extend(chunk["data"])
                if audio:
                    return web.Response(body=bytes(audio), content_type="audio/mpeg",
                                        headers={"Cache-Control": "public, max-age=86400"})
            except Exception as e2:
                return web.Response(status=502, text=f"tts failed: {e2}")
        return web.Response(status=502, text=f"tts failed: {e}")


async def handle_voices(request):
    return web.json_response(sorted(ALLOWED))


async def handle_health(request):
    return web.json_response({"ok": True, "port": PORT})


app = web.Application()
app.router.add_get("/tts", handle_tts)
app.router.add_get("/voices", handle_voices)
app.router.add_get("/", handle_health)

if __name__ == "__main__":
    print(f"小听 TTS 服务启动 http://{HOST}:{PORT}/tts?t=你好&v=zh-CN-YunjianNeural")
    web.run_app(app, host=HOST, port=PORT, print=None)