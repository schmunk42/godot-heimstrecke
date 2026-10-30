# file generated with AI assistance: Claude Code - 2026-10-23 20:40:00 UTC
"""Signposts: direction, town and distance signs beside the roads,
written as signs.json for Godot (signs.gd draws posts, panels and text;
text cannot be baked into vertex colours). signs.json carries the
`country` (from the recipe's Geofabrik path), which sets the style.

Destination signs come from the OSM tags of a way: `destination`
(and :forward, :backward) with `destination:ref` and
`destination:ref:to`; a way with only `destination:lanes` takes the
destinations of its lanes. The sign for the forward direction stands
SIGN_IN_M after the start of the way's first edge, the one for the
backward direction as far before the end of its last edge. At most
MAX_LINES destinations per sign behind an arrow straight on (↑), the
first ref in front. Only on roads from tertiary up and on links, not on
bridges or in tunnels; a sign with the same text within DEDUPE_M of
another is left out.

On a carriageway of its own that carries through traffic (motorway,
trunk, or a oneway primary road with two lanes or more, GANTRY_*) the
sign hangs on a gantry over the road instead (`gantry`: the half width
of the carriageway and the panels with their lateral offset, positive
to the right of the travel direction). With `destination:lanes` each
lane gets its panel, neighbouring lanes with the same destinations
share one; without it one panel hangs over the middle.

Where OSM has no destination tags nearby (no destination sign within
PLAIN_CLEAR_M), plain signs fill in, sparingly: at junctions of degree
3 or more with an arm from tertiary up, on every approach from tertiary
up a sign PLAIN_BEFORE_M before the junction names, for each other arm,
the most important place (city > town > village, then the nearest)
within PLACE_CONE_DEG of the arm's direction and PLACE_KM, with an
arrow. Plain signs keep PLAIN_SPACING_M from each other.

Town signs (Ortstafel, panneau d'entrée) stand where OSM maps a town
entry sign (`traffic_sign` city_limit, DE:310, FR:EB10) on a road,
facing the traffic that enters the town: the town side is the one with
more urban land cover and buildings within TOWN_PROBE_M. A place
without any mapped town sign within TOWN_MAPPED_M gets one where a road
from unclassified up enters urban land cover within TOWN_NEAR_M of it.
The name comes from the node, else the nearest place.

Distance signs stand DIST_AFTER_M past a town sign for the traffic
leaving the town, on roads from tertiary up, DIST_SPACING_M apart: the
nearest place ahead and the nearest bigger one, with the road distance
in km (shortest paths through the road graph to the graph node nearest
each place inside the area; a place counts as ahead when its shortest
path leaves in the travel direction).

Cyprus (`cy`): every sign stands left of the travel direction (left-hand
traffic, LEFT_HAND), and names are bilingual (say()): each destination,
place or distance becomes a Greek line over a Latin one (`tones` el/en,
signs.gd draws Greek in yellow on motorway panels), the names looked up
among the name variants of the places (extract.PLACE_NAMES), so the
Turkish name of a place in the north reads as on the signs of the
Republic (Gazimağusa: Αμμόχωστος / Famagusta), a Latin spelling of
another transliteration by the closest variant (CY_SPELLING); at most
CY_DESTINATIONS destinations per panel.

Colour (`kind`) by the road the sign stands on and the country.
Germany: `motorway` (blue) on motorways; `federal` (yellow, black text)
on roads with a B, L or K ref and for all plain and distance signs (the
German Wegweiser outside towns); `local` (white) otherwise. France:
`motorway` (blue); `primary` (green) on N and T routes; `local` (white)
otherwise. Cyprus: `motorway` (green) on motorways and A routes;
`primary` (blue) on B routes and for all plain and distance signs;
`local` (white) otherwise. Town signs are `town` (Germany yellow with a
black border, France white with a red border, Cyprus white with a black
border, in signs.gd).

A side sign stands right of the travel direction (left in Cyprus) with the inner edge of
its panel SIDE_CLEAR_M beyond the carriageway or its sidewalk, so no
panel reaches over the road; the panel width is estimated from the text
with the sizes of signs.gd (PANEL_PAD, PANEL_CHAR_W, ARROW_W). A panel
that would cut into a building moves along the road by SHIFTS_M, the
first free spot wins; without one the sign is left out.
"""
import difflib
import heapq
import json
import math

import numpy as np
import shapely

from frame import xyz
from sidewalks import KERB, WIDTH as SIDEWALK

SIGN_IN_M = 20.0
SIDE_CLEAR_M = 0.6
MAX_LINES = 3
DEDUPE_M = 40.0
MIN_RANK = 4  # roads.ROAD_RANK: tertiary
TOWN_RANK = 3  # unclassified
PLAIN_CLEAR_M = 400.0
PLAIN_SPACING_M = 900.0
PLAIN_BEFORE_M = 40.0
PLAIN_ARM_M = 150.0
PLACE_CONE_DEG = 30.0
PLACE_KM = (1.5, 40.0)
PLACE_RANK = {"city": 3, "town": 2, "village": 1}
TOWN_SNAP_M = 15.0
TOWN_PROBE_M = 120.0
TOWN_MAPPED_M = 1500.0
TOWN_NEAR_M = 1200.0
TOWN_DEDUPE_M = 150.0
DIST_AFTER_M = 120.0
DIST_SPACING_M = 1500.0
DIST_MIN_M = 800.0
DIST_MAX_M = 60000.0
PLACE_NODE_M = 800.0
# panel sizes as in godot/scripts/signs.gd (PAD, CHAR_W, ARROW_W)
PANEL_PAD = 0.35
PANEL_CHAR_W = 0.27
ARROW_W = 0.42
SHIFTS_M = (0.0, 10.0, -10.0, 20.0, -20.0)
GANTRY_CLASSES = ("motorway", "trunk")
GANTRY_PRIMARY_LANES = 2
BUILDING_CLEAR_M = 0.3
# countries with left-hand traffic: side signs stand left of the road
LEFT_HAND = ("cy",)
# Cyprus: destinations per panel, each a Greek and a Latin line
CY_DESTINATIONS = 2
# a Latin spelling not among the name variants (Agia Napa for Ayia Napa)
# matches the closest one at least this similar (difflib ratio)
CY_SPELLING = 0.85


def country_of(osm_region):
    """de, fr or cy from a Geofabrik path; Germany is the default."""
    if "/france" in osm_region:
        return "fr"
    return "cy" if osm_region.endswith("/cyprus") else "de"


def greek(text):
    return any("\u0370" <= c <= "\u03ff" or "\u1f00" <= c <= "\u1fff"
               for c in text)


def name_index(places):
    """Every name variant of a place (casefolded) -> (Greek, Latin), each
    possibly empty."""
    index = {}
    for p in places:
        names = {"name": p["name"], **p.get("names", {})}
        el = names.get("name:el") or (p["name"] if greek(p["name"]) else "")
        en = names.get("name:en") or names.get("name:el-Latn") \
            or names.get("int_name") \
            or ("" if greek(p["name"]) or "name:tr" in names
                else p["name"])
        for v in names.values():
            for part in v.split(";"):
                index.setdefault(part.strip().casefold(), (el, en))
    return index


def bilingual(lines, index):
    """Cyprus: each line (an optional arrow, a name, an optional "  N km")
    as a Greek line over a Latin one; returns lines and tones (el/en)."""
    out, tones = [], []
    for line in lines[:CY_DESTINATIONS]:
        arrow = line[:2] if line[:1] in "↑←→" else ""
        name, sep, km = line[len(arrow):].partition("  ")
        key = name.strip().casefold()
        if key not in index and not greek(key):
            close = difflib.get_close_matches(key, sorted(index), n=1,
                                              cutoff=CY_SPELLING)
            key = close[0] if close else key
        el, en = index.get(key, ("", ""))
        if not el and not en:
            el, en = (name, "") if greek(name) else ("", name)
        tail = sep + km
        pair = [(el, "el"), (en, "en")] if el and en and el != en \
            else [(el or en, "el" if el else "en")]
        for i, (text, tone) in enumerate(pair):
            out.append((arrow if i == 0 else "") + text
                       + (tail if i == 0 else ""))
            tones.append(tone)
    return out, tones


def panel_width(lines, ref):
    """Panel width in metres as signs.gd draws it."""
    text = [(f"{ref}  {ln}" if ref and i == 0 else ln)
            for i, ln in enumerate(lines)]
    arrow = any(t[:1] in "↑←→" for t in text)
    widest = max(len(t[1:].strip() if t[:1] in "↑←→" else t) for t in text)
    return 2 * PANEL_PAD + PANEL_CHAR_W * widest + (ARROW_W if arrow else 0)


def sign_kind(highway, road_ref, country, outside=False):
    """The panel style from the road the sign stands on (see the module
    doc); outside: a plain or distance sign naming towns."""
    if highway.startswith("motorway"):
        return "motorway"
    own = [r.strip().upper() for r in (road_ref or "").split(";")
           if r.strip()]
    if country == "fr":
        if any(r[:1] in ("N", "T") and r[1:2] in (" ", *"0123456789")
               for r in own):
            return "primary"
        return "local"
    if country == "cy":
        if any(r[:1] == "A" for r in own):
            return "motorway"
        if outside or any(r[:1] == "B" for r in own):
            return "primary"
        return "local"
    if outside or any(r[:1] in ("B", "L", "K") for r in own):
        return "federal"
    return "local"


def ahead(lines):
    """The lines with an arrow straight on in front of the first."""
    return [f"↑ {ln}" if i == 0 else ln for i, ln in enumerate(lines)]


def _split(value):
    return [v.strip() for v in (value or "").split(";") if v.strip()]


def _entry(x, y, foot, t, kind, lines, ref, tones=None):
    pos = xyz([x], [foot], [y])[0]
    # the panel faces the traffic: against the travel direction
    face = xyz([-t[0]], [0.0], [-t[1]])[0]
    entry = {"pos": [round(float(v), 2) for v in pos],
             "face": [round(float(face[0]), 3), round(float(face[2]), 3)],
             "kind": kind, "ref": ref, "lines": lines}
    if tones is not None:
        entry["tones"] = tones
    return entry


def gantry_road(tags):
    """A carriageway that gets gantries: motorway, trunk, or a oneway
    primary road with GANTRY_PRIMARY_LANES lanes or more."""
    cls = tags["highway"]
    if cls in GANTRY_CLASSES:
        return True
    try:
        lanes = int(tags.get("lanes", "0"))
    except ValueError:
        lanes = 0
    return cls == "primary" and tags.get("oneway") == "yes" \
        and lanes >= GANTRY_PRIMARY_LANES


def gantry_panels(tags, half, dest, refs):
    """Panels of a gantry: per lane from destination:lanes (equal
    neighbours merged), else one over the middle. offset: panel centre
    right of the road centre, span: the width of its lanes."""
    lanes = (tags.get("destination:lanes") or "").split("|")
    lane_refs = (tags.get("destination:ref:lanes") or "").split("|")
    if len(lanes) < 2:
        return [{"offset": 0.0, "span": round(2 * half, 2),
                 "lines": ahead(dest[:MAX_LINES]),
                 "ref": refs[0] if refs else ""}]
    lane_w = 2 * half / len(lanes)
    groups = []
    for i, lane in enumerate(lanes):
        lines = _split(lane)[:MAX_LINES]
        ref = _split(lane_refs[i] if i < len(lane_refs) else "")
        ref = ref[0] if ref else ""
        if groups and groups[-1]["lines"] == lines \
                and groups[-1]["ref"] == ref:
            groups[-1]["last"] = i
        else:
            groups.append({"first": i, "last": i, "lines": lines,
                           "ref": ref})
    out = []
    for g in groups:
        if not g["lines"]:
            continue
        mid = (g["first"] + g["last"] + 1) / 2 * lane_w - half
        out.append({"offset": round(mid, 2),
                    "span": round((g["last"] - g["first"] + 1) * lane_w, 2),
                    "lines": ahead(g["lines"]), "ref": g["ref"]})
    return out


class Signs:
    """The road network, terrain, buildings and places the signs are
    placed with."""

    def __init__(self, net, ground, base, frame, buildings, cover, places,
                 half, country):
        self.net, self.ground, self.base = net, ground, base
        self.frame, self.country = frame, country
        self.half = np.broadcast_to(half, 2)
        self.tree = shapely.STRtree([g for g, _ in buildings])
        self.urban = cover.get("urban")
        self.places = places
        self.names = name_index(places) if country == "cy" else None
        if places:
            self.px, self.py = frame.to_local(
                np.array([p["lonlat"][0] for p in places]),
                np.array([p["lonlat"][1] for p in places]))
            self.prank = np.array([PLACE_RANK[p["place"]] for p in places])
        self.taken = []

    # -- placement --------------------------------------------------------

    def tangent(self, k, forward):
        net = self.net
        j = k + 1 if forward else k - 1
        t = np.array([net.sx[j] - net.sx[k], net.sy[j] - net.sy[k]])
        return t / (np.linalg.norm(t) + 1e-12)

    def say(self, lines):
        """The lines of a panel and their tones: bilingual in Cyprus
        (bilingual()), as they are elsewhere (tones None)."""
        if self.names is None:
            return lines, None
        return bilingual(lines, self.names)

    def side_spot(self, k, forward, width):
        """Panel centre right of the travel direction at sample k (left
        with LEFT_HAND traffic): its inner edge SIDE_CLEAR_M beyond the
        carriageway or the sidewalk on that side, on the conformed
        terrain."""
        net = self.net
        t = self.tangent(k, forward)
        right = np.array([t[1], -t[0]])
        e = net.edge_of[k]
        # net.walk: (left, right) in the edge direction
        walk = net.walk[e, 1] if forward else net.walk[e, 0]
        if self.country in LEFT_HAND:
            right = -right
            walk = net.walk[e, 0] if forward else net.walk[e, 1]
        off = float(net.half[k]) + (SIDEWALK + KERB if walk else 0.0) \
            + SIDE_CLEAR_M + width / 2
        x, y = net.sx[k] + right[0] * off, net.sy[k] + right[1] * off
        foot = float(self.ground.height(np.array([x]),
                                        np.array([y]))[0]) - self.base
        return x, y, foot, t

    def free(self, x, y, t, width):
        """The panel across the travel direction t at x, y is clear of
        buildings and inside the playable area."""
        if abs(x) > self.half[0] - width or abs(y) > self.half[1] - width:
            return False
        right = np.array([t[1], -t[0]]) * (width / 2)
        panel = shapely.LineString([(x - right[0], y - right[1]),
                                    (x + right[0], y + right[1])])
        return len(self.tree.query(panel, predicate="dwithin",
                                   distance=BUILDING_CLEAR_M)) == 0

    def placed(self, k, forward, s0, s1, width):
        """side_spot at sample k or SHIFTS_M along the road where the
        panel is free; None if there is no such spot."""
        net = self.net
        step = (net.dist[s0 + 1] - net.dist[s0]) or 5.0
        for shift in SHIFTS_M:
            j = k + int(round(shift / step))
            j = min(max(j, s0 + 1), s1 - 1)
            spot = self.side_spot(j, forward, width)
            if self.free(spot[0], spot[1], spot[3], width):
                return spot
        return None

    def kind(self, e, outside=False):
        tags = self.net.edges[e]["tags"]
        return sign_kind(tags["highway"], tags.get("ref"), self.country,
                         outside)

    # -- destination signs and gantries ------------------------------------

    def destination(self):
        net = self.net
        first, last = {}, {}
        for k, e in enumerate(net.edges):
            first.setdefault(e["way"], k)
            last[e["way"]] = k
        out = []
        for way, k0 in first.items():
            tags = net.edges[k0]["tags"]
            highway = tags["highway"]
            if net.rank[k0] < MIN_RANK and not highway.endswith("_link"):
                continue
            for forward in (True, False):
                side = "forward" if forward else "backward"
                dest = _split(tags.get(f"destination:{side}")
                              or (tags.get("destination") if forward
                                  else None))
                if not dest and forward and tags.get("destination:lanes"):
                    dest = list(dict.fromkeys(
                        d for lane in tags["destination:lanes"].split("|")
                        for d in _split(lane)))
                if not dest:
                    continue
                refs = _split(tags.get(f"destination:ref:{side}")
                              or (tags.get("destination:ref") if forward
                                  else None)) \
                    + _split(tags.get(f"destination:ref:to:{side}")
                             or (tags.get("destination:ref:to") if forward
                                 else None))
                e = k0 if forward else last[way]
                if net.struct[e]:
                    continue
                s0, s1 = net.start[e], net.start[e + 1] - 1
                dist = net.dist[s0:s1 + 1] - net.dist[s0]
                if dist[-1] < 2 * SIGN_IN_M:
                    continue
                if forward:
                    k = s0 + int(np.searchsorted(dist, SIGN_IN_M))
                    k = min(max(k, s0), s1 - 1)
                else:
                    k = s0 + int(np.searchsorted(dist,
                                                 dist[-1] - SIGN_IN_M))
                    k = max(k, s0 + 1)
                lines, ref = ahead(dest[:MAX_LINES]), refs[0] if refs else ""
                lines, tones = self.say(lines)
                kind = self.kind(e)
                if gantry_road(tags):
                    panels = gantry_panels(tags, float(net.half[k]), dest,
                                           refs)
                    for p in panels if self.names is not None else ():
                        p["lines"], p["tones"] = self.say(p["lines"])
                    if panels:
                        entry = _entry(net.sx[k], net.sy[k],
                                       float(net.surface[k]),
                                       self.tangent(k, forward), kind, [],
                                       "")
                        entry["gantry"] = {
                            "half": round(float(net.half[k]), 2),
                            "panels": panels}
                        out.append(entry)
                    continue
                spot = self.placed(k, forward, s0, s1,
                                   panel_width(lines, ref))
                if spot is not None:
                    out.append(_entry(*spot, kind, lines, ref, tones))
        kept = []
        for s in out:
            p = np.array(s["pos"])
            if "gantry" not in s and any(
                    k["lines"] == s["lines"]
                    and np.linalg.norm(np.array(k["pos"]) - p) < DEDUPE_M
                    for k in kept):
                continue
            kept.append(s)
        return kept

    # -- plain direction signs ---------------------------------------------

    def _arm_point(self, e, node, length):
        """The point `length` metres out along edge e from node (or its
        far end), and whether node is the edge's start."""
        c = self.net.edges[e]["coords"]
        from_start = self.net.u[e] == node
        c = c if from_start else c[::-1]
        seg = np.hypot(*np.diff(c, axis=0).T)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        d = min(length, cum[-1])
        return np.array([np.interp(d, cum, c[:, 0]),
                         np.interp(d, cum, c[:, 1])]), from_start

    def plain(self):
        net = self.net
        if not self.places:
            return []
        names = [p["name"] for p in self.places]
        placed, out = [], []
        arms_of = {}
        for e in range(len(net.edges)):
            if net.struct[e] or net.rank[e] < MIN_RANK \
                    or net.u[e] == net.v[e]:
                continue
            arms_of.setdefault(int(net.u[e]), []).append(e)
            arms_of.setdefault(int(net.v[e]), []).append(e)
        lo, hi = PLACE_KM[0] * 1000, PLACE_KM[1] * 1000
        for node, arms in arms_of.items():
            if len(arms) < 3:
                continue
            nxy = net.xy[node]
            heads = {}
            for a in arms:
                q, _ = self._arm_point(a, node, PLAIN_ARM_M)
                d = q - nxy
                heads[a] = math.atan2(d[1], d[0])
            for appr in arms:
                # the approach: travel along appr towards node
                if net.length[appr] < PLAIN_BEFORE_M + 20.0:
                    continue
                q, from_start = self._arm_point(appr, node, PLAIN_BEFORE_M)
                if any(np.linalg.norm(q - t) < PLAIN_CLEAR_M
                       for t in self.taken) \
                        or any(np.linalg.norm(q - p) < PLAIN_SPACING_M
                               for p in placed):
                    continue
                travel = heads[appr] + math.pi
                lines = []
                for a in arms:
                    if a == appr:
                        continue
                    ang = heads[a]
                    dx, dy = self.px - nxy[0], self.py - nxy[1]
                    dist = np.hypot(dx, dy)
                    off = np.abs((np.arctan2(dy, dx) - ang + math.pi)
                                 % (2 * math.pi) - math.pi)
                    ok = (dist >= lo) & (dist <= hi) \
                        & (off <= math.radians(PLACE_CONE_DEG))
                    if not np.any(ok):
                        continue
                    cand = np.flatnonzero(ok)
                    best = cand[np.lexsort((dist[cand],
                                            -self.prank[cand]))[0]]
                    turn = (ang - travel + math.pi) % (2 * math.pi) - math.pi
                    arrow = "↑" if abs(turn) < math.radians(35) \
                        else ("←" if turn > 0 else "→")
                    if names[best] not in (ln[2:] for ln in lines):
                        lines.append(f"{arrow} {names[best]}")
                if not lines:
                    continue
                lines, tones = self.say(lines[:MAX_LINES])
                s0, s1 = net.start[appr], net.start[appr + 1]
                k = s0 + int(np.argmin(np.hypot(net.sx[s0:s1] - q[0],
                                                net.sy[s0:s1] - q[1])))
                k = min(max(k, s0 + 1), s1 - 2)
                # travel towards node: forward if node is the edge's end
                spot = self.placed(k, not from_start, s0, s1 - 1,
                                   panel_width(lines, ""))
                if spot is None:
                    continue
                out.append(_entry(*spot, self.kind(appr, True), lines, "",
                                  tones))
                placed.append(q)
        return out

    # -- town signs --------------------------------------------------------

    def _townness(self, x, y):
        """Urban land cover and buildings around x, y (a score)."""
        p = shapely.Point(x, y)
        score = 0.0
        if self.urban is not None and shapely.contains_xy(self.urban, x, y):
            score += 10.0
        score += len(self.tree.query(p, predicate="dwithin",
                                     distance=TOWN_PROBE_M))
        return score

    def _nearest_place(self, x, y, limit):
        if not self.places:
            return ""
        d = np.hypot(self.px - x, self.py - y)
        i = int(np.argmin(d))
        return self.places[i]["name"] if d[i] <= limit else ""

    def _town_entry(self, k, name):
        """A town sign at sample k for the traffic entering the town;
        None if neither side looks like the town."""
        net = self.net
        e = net.edge_of[k]
        s0, s1 = net.start[e], net.start[e + 1] - 1
        if s1 - s0 < 2:
            return None
        step = (net.dist[s0 + 1] - net.dist[s0]) or 5.0
        n = int(TOWN_PROBE_M / step)
        fwd = min(k + n, s1)
        back = max(k - n, s0)
        f = self._townness(net.sx[fwd], net.sy[fwd])
        b = self._townness(net.sx[back], net.sy[back])
        if f == b:
            return None
        forward = f > b
        k = min(max(k, s0 + 1), s1 - 1)
        lines, tones = self.say([name])
        spot = self.placed(k, forward, s0, s1, panel_width(lines, ""))
        if spot is None:
            return None
        entry = _entry(*spot, "town", lines, "", tones)
        entry["leave"] = [int(k), not forward]
        entry["place"] = name
        return entry

    def towns(self, town_signs):
        """Town signs at the mapped entry signs, then fallbacks for places
        without one (see the module doc)."""
        net = self.net
        if not len(net.sx):
            return []
        samples = shapely.points(net.sx, net.sy)
        stree = shapely.STRtree(samples)
        ok = net.rank[net.edge_of] >= TOWN_RANK
        out = []

        def keep(entry):
            p = np.array(entry["pos"])
            if any(o["lines"] == entry["lines"]
                   and np.linalg.norm(np.array(o["pos"]) - p)
                   < TOWN_DEDUPE_M for o in out):
                return
            out.append(entry)

        mapped = []
        for t in town_signs:
            x, y = self.frame.to_local(*t["lonlat"])
            x, y = float(x), float(y)
            i, d = stree.query_nearest(shapely.Point(x, y),
                                       return_distance=True)
            if not len(i) or d[0] > TOWN_SNAP_M or not ok[i[0]]:
                continue
            # "Hebsack;Geradstetten": the first name is the town's
            name = _split(t["name"])[0] if _split(t["name"]) \
                else self._nearest_place(x, y, 2500.0)
            if not name:
                continue
            mapped.append((x, y))
            entry = self._town_entry(int(i[0]), name)
            if entry is not None:
                keep(entry)
        # fallbacks: places with no mapped sign nearby
        if self.urban is None or not self.places:
            return out
        inside = shapely.contains_xy(self.urban, net.sx, net.sy) & ok
        for e in range(len(net.edges)):
            if net.rank[e] < TOWN_RANK or net.struct[e]:
                continue
            s0, s1 = net.start[e], net.start[e + 1] - 1
            flips = np.flatnonzero(inside[s0:s1] != inside[s0 + 1:s1 + 1])
            for f in flips:
                k = s0 + int(f)
                # the outside sample of the boundary crossing
                k = k if not inside[k] else k + 1
                x, y = net.sx[k], net.sy[k]
                d = np.hypot(self.px - x, self.py - y)
                j = int(np.argmin(d))
                if d[j] > TOWN_NEAR_M:
                    continue
                if any(math.hypot(mx - self.px[j], my - self.py[j])
                       < TOWN_MAPPED_M for mx, my in mapped):
                    continue
                entry = self._town_entry(k, self.places[j]["name"])
                if entry is not None:
                    keep(entry)
        return out

    # -- distance signs ----------------------------------------------------

    def _graph(self):
        net = self.net
        adj = {}
        for e in range(len(net.edges)):
            u, v, w = int(net.u[e]), int(net.v[e]), float(net.length[e])
            adj.setdefault(u, []).append((v, w))
            adj.setdefault(v, []).append((u, w))
        return adj

    @staticmethod
    def _dijkstra(adj, start):
        dist = {start: 0.0}
        heap = [(0.0, start)]
        while heap:
            d, n = heapq.heappop(heap)
            if d > dist.get(n, math.inf) or d > DIST_MAX_M:
                continue
            for m, w in adj.get(n, ()):
                nd = d + w
                if nd < dist.get(m, math.inf):
                    dist[m] = nd
                    heapq.heappush(heap, (nd, m))
        return dist

    def distances(self, towns):
        """Distance signs past the town signs, for the leaving traffic."""
        net = self.net
        if not self.places or not towns:
            return []
        hx, hy = self.half
        node_tree = shapely.STRtree(shapely.points(net.xy))
        place_node = {}
        for i in range(len(self.places)):
            x, y = self.px[i], self.py[i]
            if abs(x) > hx or abs(y) > hy:
                continue
            j, d = node_tree.query_nearest(shapely.Point(x, y),
                                           return_distance=True)
            if len(j) and d[0] <= PLACE_NODE_M:
                place_node[i] = int(j[0])
        if not place_node:
            return []
        adj = self._graph()
        out, placed = [], []
        for town in towns:
            k, forward = town["leave"]
            e = net.edge_of[k]
            if net.rank[e] < MIN_RANK or net.struct[e]:
                continue
            s0, s1 = net.start[e], net.start[e + 1] - 1
            step = (net.dist[s0 + 1] - net.dist[s0]) or 5.0
            k2 = k + (1 if forward else -1) * int(DIST_AFTER_M / step)
            if not (s0 + 1 <= k2 <= s1 - 1):
                continue
            here = np.array([net.sx[k2], net.sy[k2]])
            if any(np.linalg.norm(here - p) < DIST_SPACING_M
                   for p in placed):
                continue
            along = float(net.dist[k2] - net.dist[s0])
            length = float(net.dist[s1] - net.dist[s0])
            ahead_node, back_node = (int(net.v[e]), int(net.u[e])) \
                if forward else (int(net.u[e]), int(net.v[e]))
            rem_ahead = length - along if forward else along
            rem_back = along if forward else length - along
            d_ahead = self._dijkstra(adj, ahead_node)
            d_back = self._dijkstra(adj, back_node)
            left = town["place"]
            found = []
            for i, n in place_node.items():
                name = self.places[i]["name"]
                if name == left or n not in d_ahead:
                    continue
                f = rem_ahead + d_ahead[n]
                b = rem_back + d_back.get(n, math.inf)
                if f < DIST_MIN_M or f >= b:
                    continue
                found.append((f, -self.prank[i], name))
            if not found:
                continue
            found.sort()
            pick = [found[0]]
            bigger = [c for c in found if -c[1] > -found[0][1]]
            if bigger:
                pick.append(bigger[0])
            lines, tones = self.say(
                [f"{name}  {round(f / 1000)} km" for f, _, name in pick])
            spot = self.placed(k2, forward, s0, s1, panel_width(lines, ""))
            if spot is None:
                continue
            out.append(_entry(*spot, self.kind(e, True), lines, "", tones))
            placed.append(here)
        return out


def write_signs(net, ground, base, places, town_signs, frame, buildings,
                cover, half, country, path):
    """signs.json for Godot; returns the counts."""
    signs = Signs(net, ground, base, frame, buildings, cover, places, half,
                  country)
    dest = signs.destination()
    signs.taken = [np.array([s["pos"][0], -s["pos"][2]]) for s in dest]
    plain = signs.plain()
    towns = signs.towns(town_signs)
    dist = signs.distances(towns)
    for t in towns:
        t.pop("leave", None)
        t.pop("place", None)
    every = dest + plain + towns + dist
    path.write_text(json.dumps({"country": country, "signs": every},
                               ensure_ascii=False))
    kinds = {}
    for s in every:
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    gantries = [s for s in dest if "gantry" in s]
    return {"destination": len(dest), "plain": len(plain),
            "town": len(towns), "distance": len(dist),
            "gantries": len(gantries),
            "gantry_lane_panels": sum(len(g["gantry"]["panels"]) > 1
                                      for g in gantries), **kinds}
# - revised 2026-10-23 (gantries over through carriageways)
# - revised 2026-10-25 (town and distance signs, country styles, panels
#   beside the road)
# - revised 2026-10-27 (Cyprus: left side, bilingual, green/blue/white)
