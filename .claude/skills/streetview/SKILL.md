---
name: streetview
description: "Turn a Heimstrecke screenshot (with the # position readout visible) into a Google Street View link at the same spot, heading and pitch. Use when the user runs /streetview, or asks for the Street View of a screenshot or a # position line."
argument-hint: "[screenshot path | # position line]"
---
<!-- file generated with AI assistance: Claude Code - 2026-11-04 17:02:26 UTC -->

# /streetview

Input: `$ARGUMENTS`, one of

- a path to a screenshot (`.png`, `.jpg`),
- a pasted image in the message,
- a pasted `#` position line (the clipboard text of the `#` key),
- nothing: take the newest `screenshot-*.png` in `~/Pictures/` (`ls -t ~/Pictures/screenshot-*.png | head -1`) and say which file was used.

## Read the position

The `#` key in the game shows the readout top centre (`godot/scripts/world.gd`, `_position_text()`):

```
<world>  <road> (<n> m)  <lat>,<lon>  heading <deg>°  pitch <±deg>°  camera <view>
{"position": [x, y, z], "look_at": [x, y, z]}
```

Read the screenshot with the Read tool and take from the first line `lat`, `lon`, `heading` and `pitch`. The heading is already the true compass heading of the camera, the pitch already in degrees; no conversion. If the text is too small to read with certainty, crop and enlarge the top centre first (`magick <in> -gravity north -crop 60%x8%+0+0 +repage -resize 300% <scratchpad>/readout.png`) and read that. Never guess digits: if the readout is missing or unreadable, say so and ask for a screenshot with `#` switched on or for the clipboard line.

## Output

```
https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=<lat>,<lon>&heading=<heading>&pitch=<pitch>
```

`pitch` is clamped to -90..90. Answer with the link and one line naming world, road, lat/lon, heading and pitch as read, so a misread digit shows. Street View snaps to the nearest panorama; on a road without coverage Google shows the map instead, which is worth a sentence if the road name suggests a track or a minor road.
