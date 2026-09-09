"""Hikvision CCTV on the hub.

The DVRs live on the factory LAN behind NAT; the VPS cannot reach them and
must not try (opening ISAPI ports to the internet is how DVRs get owned).
So the direction is reversed: a small **agent** on a LAN PC polls each DVR's
ISAPI and *pushes* device state, channel list, storage and snapshots to the
gateway. The hub only ever reads what the agent last sent, and says how old it
is. DVR passwords never leave the LAN PC's `config.json`.
"""
