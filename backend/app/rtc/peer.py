"""aiortc PeerConnection wiring.

M1 scope: accept screen + mic tracks from the client and echo them back
through a MediaRelay so the client can verify the transport end-to-end.
Later milestones plug the FrameSampler and AudioPipeline in place of the
raw echo.
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay

log = logging.getLogger("app.rtc")

_peers: Dict[str, RTCPeerConnection] = {}
_relay = MediaRelay()


async def create_peer(offer_sdp: str, offer_type: str) -> tuple[str, RTCSessionDescription]:
    """Build a new RTCPeerConnection, apply the remote offer, return our answer."""
    pc = RTCPeerConnection()
    pc_id = uuid.uuid4().hex[:8]
    _peers[pc_id] = pc
    log.info("[%s] peer created (total=%d)", pc_id, len(_peers))

    @pc.on("connectionstatechange")
    async def _on_state():
        log.info("[%s] connectionState=%s", pc_id, pc.connectionState)
        if pc.connectionState in ("failed", "closed", "disconnected"):
            await _drop(pc_id)

    @pc.on("track")
    def _on_track(track):
        log.info("[%s] inbound track kind=%s id=%s", pc_id, track.kind, track.id)
        # Echo the track back so the client can see its own screen / hear its mic.
        # Later: replace with FrameSampler (video) + AudioPipeline (audio).
        pc.addTrack(_relay.subscribe(track))

        @track.on("ended")
        async def _on_end():
            log.info("[%s] track ended kind=%s", pc_id, track.kind)

    offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return pc_id, pc.localDescription


async def _drop(pc_id: str) -> None:
    pc = _peers.pop(pc_id, None)
    if pc is None:
        return
    try:
        await pc.close()
    finally:
        log.info("[%s] peer closed (remaining=%d)", pc_id, len(_peers))


async def close_all_peers() -> None:
    for pc_id in list(_peers.keys()):
        await _drop(pc_id)
