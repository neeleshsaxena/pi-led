#!/usr/bin/env bash
# uvmon — Raspberry Pi under-voltage / throttle monitor.
#
# Reads `vcgencmd get_throttled` and logs to the systemd journal (tag: uvmon),
# but ONLY when the state CHANGES — so a healthy Pi logs one "clean" line at boot
# and nothing more, while a brownout leaves a precise timestamped trail:
#
#   journalctl -t uvmon                 # the whole voltage timeline
#   journalctl -t uvmon -p warning      # just the under-voltage / throttle events
#
# The "occurred" bits (0x1xxxx) latch until reboot, so a transient sag that never
# fully crashes the box is still recorded. Pair with persistent journald so the
# record survives the reboot after a hard brownout.
set -u

raw="$(vcgencmd get_throttled 2>/dev/null)"   # e.g. "throttled=0x50005"
val="${raw#*=}"                                # "0x50005"
[ -z "$val" ] && exit 0
n=$(( val ))                                   # bash parses 0x-hex

decode=""
(( n & 0x1 ))     && decode+="under-voltage-NOW "
(( n & 0x2 ))     && decode+="arm-freq-capped-NOW "
(( n & 0x4 ))     && decode+="throttled-NOW "
(( n & 0x8 ))     && decode+="soft-temp-limit-NOW "
(( n & 0x10000 )) && decode+="under-voltage-OCCURRED "
(( n & 0x20000 )) && decode+="arm-freq-cap-OCCURRED "
(( n & 0x40000 )) && decode+="throttled-OCCURRED "
(( n & 0x80000 )) && decode+="soft-temp-OCCURRED "
[ -z "$decode" ] && decode="clean"

# Edge-detect against the last reading (/run is tmpfs — resets each boot, so the
# first run after boot always logs a baseline line).
last_file="/run/uvmon.last"
last="$(cat "$last_file" 2>/dev/null || true)"
printf '%s' "$val" > "$last_file"
[ "$val" = "$last" ] && exit 0

temp="$(vcgencmd measure_temp 2>/dev/null | cut -d= -f2)"
# Any "now" bit (0xF) => warning; latched-only or clean => notice.
if (( n & 0xF )); then pri="user.warning"; else pri="user.notice"; fi
logger -p "$pri" -t uvmon "throttled=$val temp=${temp:-?} :: ${decode% }"
