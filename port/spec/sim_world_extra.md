# sim_world — extra: the far text buffer `39e5:0000`

`39e5:0000` (256 bytes, indexed as a function by the indexer) is **data**: a 256-byte far char
buffer in its own paragraph-aligned segment, all zero in the file. Its only users are in
`kill_credit` `088a:054f` (sim_world_dmg.md): when the player is the killer and the victim `t` is a plane
(`t+18 == 0`) with damage word `*(t+2A) > 3FFh`, of the other side, with pilot profile index `t+BB > 2Ch` (an ace):

```
_fstrcpy(39e5:0000, "You just shot down ")          // DS:139A
_fstrcat(39e5:0000, DS:55CE[t+BB] + 58h)             // the ace's name from the pilot profile
_fstrcat(39e5:0000, "!")                             // DS:13AE
msg_show(39e5:0000, 2, 0:0)                          // 1614:024e, priority 2, no speaker
```

(x86dis `088a:05fd..0642`: `0000:4b91` = `_fstrcpy`, `0000:4b22` = `_fstrcat`.)

Port: a static `char kill_msg[256]`; it need not live in emulated memory unless `msg_show` keeps
the far pointer (it copies the text into its rotating buffers, `sim_flow_cockpit.md` `1614:024e`, so a local buffer is enough).

Correction for reconciliation: `video_ts.md` (Hand-offs) says this block "matches PS `3d50:3e0f` =
the `m_cam_block` data". It does not: the match is only that both are data blocks of zeros; AP
`39e5` is referenced solely as `push 39E5h` segment in `kill_credit`. `sim_flow.md` ("256 zero
bytes, no code") is right.
