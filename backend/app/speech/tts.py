"""Azure Speech streaming TTS.

Synthesizes speech to raw PCM chunks asynchronously so the caller can
stream frames straight into a live WebRTC audio track. The output is
48 kHz / 16-bit mono PCM to match the Opus encoder aiortc uses.

Like STT, this is a soft dependency: missing SDK/key -> returns empty
async iterator + a log warning.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from app.config import settings

log = logging.getLogger("app.speech.tts")

try:
    import azure.cognitiveservices.speech as speechsdk
    _SDK_OK = True
except ImportError:
    _SDK_OK = False

# 48 kHz, 16-bit, mono — matches aiortc's audio pipeline out-of-the-box.
_OUTPUT_FORMAT = "Raw48Khz16BitMonoPcm"


async def synthesize(text: str) -> AsyncIterator[bytes]:
    """Stream synthesized PCM bytes for `text`. Yields raw 48k/16/mono PCM."""
    if not _SDK_OK or not settings.AZURE_SPEECH_KEY:
        log.warning("TTS unavailable (sdk=%s, key=%s)", _SDK_OK, bool(settings.AZURE_SPEECH_KEY))
        return

    sc = speechsdk.SpeechConfig(
        subscription=settings.AZURE_SPEECH_KEY,
        region=settings.AZURE_SPEECH_REGION,
    )
    sc.speech_synthesis_voice_name = settings.AZURE_SPEECH_VOICE
    sc.set_speech_synthesis_output_format(
        getattr(speechsdk.SpeechSynthesisOutputFormat, _OUTPUT_FORMAT)
    )

    synth = speechsdk.SpeechSynthesizer(speech_config=sc, audio_config=None)
    loop = asyncio.get_running_loop()

    # Run the blocking synthesis on a thread; we'll pull bytes from the result stream.
    def _run() -> "speechsdk.SpeechSynthesisResult":
        return synth.speak_text_async(text).get()

    result_future = loop.run_in_executor(None, _run)
    result = await result_future

    reason = result.reason
    if reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        details = getattr(result, "cancellation_details", None)
        c_reason = getattr(details, "reason", None) if details else None
        err = getattr(details, "error_details", None) if details else None
        log.warning(
            "TTS failed reason=%s cancel=%s err=%s", reason, c_reason, err
        )
        return

    # The result contains the full audio; chunk it so the track sees sensible frames.
    audio = result.audio_data
    chunk = 48000 * 2 // 50  # 20 ms @ 48 kHz, 16-bit mono
    for i in range(0, len(audio), chunk):
        yield audio[i : i + chunk]
