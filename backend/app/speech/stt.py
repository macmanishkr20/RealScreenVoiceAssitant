"""Azure Speech streaming STT.

Wraps Azure's `SpeechRecognizer` with a `PushAudioInputStream` so the
audio pipeline can feed 16 kHz / 16-bit mono PCM as it arrives off the
WebRTC track. Azure handles VAD and utterance segmentation server-side
and fires `recognizing` (partial) and `recognized` (final) events,
which we fan out to the session's event queue as transcript messages.

STT is a soft dependency: if the key or SDK is missing, `start_stt`
returns None and the caller logs a hint.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.config import settings
from app.session import Session

log = logging.getLogger("app.speech.stt")

try:
    import azure.cognitiveservices.speech as speechsdk
    _SDK_OK = True
except ImportError:
    _SDK_OK = False


class SttSession:
    """One Azure streaming recognition per browser session."""

    def __init__(self, session: Session, loop: asyncio.AbstractEventLoop):
        self._session = session
        self._loop = loop
        self._push_stream: "speechsdk.audio.PushAudioInputStream" | None = None
        self._recognizer: "speechsdk.SpeechRecognizer" | None = None
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        sc = speechsdk.SpeechConfig(
            subscription=settings.AZURE_SPEECH_KEY,
            region=settings.AZURE_SPEECH_REGION,
        )
        sc.speech_recognition_language = "en-US"
        # Trim silence windows to keep first-partial latency low.
        sc.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs,
            "3000",
        )
        sc.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs,
            "800",
        )

        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=16000, bits_per_sample=16, channels=1
        )
        self._push_stream = speechsdk.audio.PushAudioInputStream(audio_format)
        audio_config = speechsdk.audio.AudioConfig(stream=self._push_stream)
        self._recognizer = speechsdk.SpeechRecognizer(
            speech_config=sc, audio_config=audio_config
        )

        def _partial(evt):
            text = evt.result.text.strip()
            if text:
                self._emit("transcript", text=text, final=False)

        def _final(evt):
            text = evt.result.text.strip()
            if text:
                self._emit("transcript", text=text, final=True)

        def _cancel(evt):
            log.warning("STT canceled: %s", evt)

        self._recognizer.recognizing.connect(_partial)
        self._recognizer.recognized.connect(_final)
        self._recognizer.canceled.connect(_cancel)
        self._recognizer.start_continuous_recognition_async()
        self._started = True
        log.info("STT started session=%s", self._session.id)

    def push(self, pcm16_mono_16k: bytes) -> None:
        if self._push_stream is not None:
            self._push_stream.write(pcm16_mono_16k)

    def stop(self) -> None:
        if self._recognizer is not None:
            try:
                self._recognizer.stop_continuous_recognition_async()
            except Exception:
                pass
        if self._push_stream is not None:
            self._push_stream.close()
        self._started = False
        log.info("STT stopped session=%s", self._session.id)

    def _emit(self, kind: str, **payload) -> None:
        # SDK callbacks fire on non-asyncio threads; marshal back to the loop.
        asyncio.run_coroutine_threadsafe(
            self._session.emit(type=kind, **payload), self._loop
        )


def start_stt(session: Session, loop: asyncio.AbstractEventLoop) -> Optional[SttSession]:
    if not _SDK_OK:
        log.warning("azure-cognitiveservices-speech not installed; STT disabled")
        return None
    if not settings.AZURE_SPEECH_KEY:
        log.warning("AZURE_SPEECH_KEY empty; STT disabled")
        return None
    stt = SttSession(session, loop)
    stt.start()
    return stt
