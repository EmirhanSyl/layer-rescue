"""Generate the LayerRescue insert-mode benchmark models (M1-M3, G1-G7).

Every model is built from parameters at the top of this file, so the
geometry used in the paper can be regenerated exactly:

    pip install manifold3d trimesh numpy
    python generate_models.py            # writes the STL files next to this script

Units are millimetres. Z is the print direction (every part is printed
standing up, as positioned in the STL). "seam_z" is the height at which the
print is stopped and the insert starts; enter it as the part height in
LayerRescue's insert tab.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import CrossSection, JoinType, Manifold

OUT = Path(__file__).resolve().parent
SEG = 128  # circle segments

# --- shared parameters -------------------------------------------------------
LAYER = 0.20            # layer height used in the experiments
RIB_W = 1.0             # reference rib width (tangential)
RIB_H = 0.8             # reference rib protrusion
RIB_EMBED = 0.2         # how far a rib reaches into the body (for a clean union)
NOTCH_BELOW_SEAM = 2.0  # Z reference notch: centre this far below the seam
NOTCH_H = 0.6
NOTCH_D = 0.4
G_SEAM = 20.0           # insert height of the G parts
G_CONT = 10.0           # printed after the insert


# --- helpers -----------------------------------------------------------------
def rect(w, h, cx=0.0, cy=0.0):
    return CrossSection.square([w, h], center=True).translate([cx, cy])


def circle(r):
    return CrossSection.circle(r, SEG)


def rib(x, y, direction):
    """A rib on the outer face at (x, y), pointing along +x/-x/+y/-y."""
    depth = RIB_H + RIB_EMBED
    off = RIB_H - depth / 2
    dx, dy = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}[direction]
    if dx:
        return rect(depth, RIB_W, x + dx * off, y)
    return rect(RIB_W, depth, x, y + dy * off)


def with_ribs(cs, anchors):
    for a in anchors:
        cs = cs + rib(*a)
    return cs


def prism(cs, height):
    return Manifold.extrude(cs, height)


def z_notch(part, cs_at_notch, seam_z):
    """Cut a shallow horizontal groove NOTCH_BELOW_SEAM under the seam."""
    z0 = seam_z - NOTCH_BELOW_SEAM - NOTCH_H / 2
    ring = cs_at_notch.offset(5.0, JoinType.Miter) - cs_at_notch.offset(-NOTCH_D, JoinType.Miter)
    return part - Manifold.extrude(ring, NOTCH_H).translate([0, 0, z0])


def four_anchors(rx, ry=None):
    ry = rx if ry is None else ry
    return [(rx, 0, "+x"), (0, ry, "+y"), (-rx, 0, "-x"), (0, -ry, "-y")]


# --- M: mechanical specimens -------------------------------------------------
def m1_tensile():
    """ASTM D638 Type I outline, 7 mm thick (the maximum ASTM D638 Type I allows), printed standing up (length along Z)."""
    L0, W0, W, L, R, T = 165.0, 19.0, 13.0, 57.0, 76.0, 7.0
    step = (W0 - W) / 2
    arc_len = math.sqrt(R**2 - (R - step) ** 2)  # length of each fillet along Z
    grip = (L0 - L - 2 * arc_len) / 2
    # half-profile x(z) for z from 0..L0, then mirror -> polygon in (x, z)
    def half_width(z):
        if z <= grip or z >= L0 - grip:
            return W0 / 2
        a, b = grip + arc_len, L0 - grip - arc_len
        if a <= z <= b:
            return W / 2
        d = (a - z) if z < a else (z - b)  # distance into the fillet, 0..arc_len
        return W / 2 + (R - math.sqrt(R**2 - d**2))
    zs = np.unique(np.concatenate([
        np.linspace(0, grip, 2),
        np.linspace(grip, grip + arc_len, 40),
        np.linspace(grip + arc_len, L0 - grip - arc_len, 2),
        np.linspace(L0 - grip - arc_len, L0 - grip, 40),
        np.linspace(L0 - grip, L0, 2),
    ]))
    right = [(half_width(z), z) for z in zs]
    left = [(-x, z) for x, z in reversed(right)]
    profile = CrossSection([right + left])
    body = Manifold.extrude(profile, T).translate([0, 0, -T / 2])  # profile in XY, thickness in Z
    body = body.rotate([90, 0, 0])  # profile plane -> XZ, length along +Z, thickness along Y
    info = dict(size_mm=[W0, T, L0], seam_z=L0 / 2, gauge_width=W, gauge_length=L,
                fillet_radius=R, standard="ASTM D638 Type I outline, T = 7 mm")
    return body, info


def m2_flex():
    """Flexural bar 80 x 10 x 5 mm (ISO 178 based; 5 mm instead of 4 mm), printed standing up."""
    body = prism(rect(10, 5), 80)
    return body, dict(size_mm=[10, 5, 80], seam_z=40.0,
                      standard="ISO 178 based, thickness 5 mm (deviation: minimum narrow side in insert mode)")


def m3_shear():
    body = prism(rect(20, 20), 30)
    return body, dict(size_mm=[20, 20, 30], seam_z=15.0, standard="custom shear block")


# --- G: alignment reference parts --------------------------------------------
def g_part(cs, seam=G_SEAM, cont=G_CONT):
    part = prism(cs, seam + cont)
    return z_notch(part, cs, seam)


def g1_square():
    cs = with_ribs(rect(20, 20), four_anchors(10))
    return g_part(cs), dict(seam_z=G_SEAM, section="square 20 x 20")


def g2_cylinder():
    cs = with_ribs(circle(10), four_anchors(10))
    return g_part(cs), dict(seam_z=G_SEAM, section="circle d = 20")


def g3_cone(angle_deg):
    r0 = 8.0
    h = G_SEAM + G_CONT
    r1 = r0 + h * math.tan(math.radians(angle_deg))
    cs = with_ribs(circle(r0), four_anchors(r0))
    s = r1 / r0
    part = Manifold.extrude(cs, h, scale_top=[s, s])
    zn = G_SEAM - NOTCH_BELOW_SEAM
    sn = 1 + (s - 1) * zn / h
    part = z_notch(part, cs.scale([sn, sn]), G_SEAM)
    return part, dict(seam_z=G_SEAM, section=f"cone, base d = 16, flare {angle_deg} deg per side, top d = {2 * r1:.1f}")


def g4_tube():
    cs = with_ribs(circle(12) - circle(8), four_anchors(12))
    part = prism(cs, G_SEAM + G_CONT)
    part = z_notch(part, circle(12) + CrossSection(), G_SEAM)
    return part, dict(seam_z=G_SEAM, section="tube, outer d = 24, inner d = 16")


def g5_l():
    poly = [(0, 0), (30, 0), (30, 8), (8, 8), (8, 20), (0, 20)]
    base = CrossSection([poly]).translate([-15, -10])
    anchors = [(0, -10, "-y"), (-15, 0, "-x"), (15, -6, "+x"), (-11, 10, "+y")]
    cs = with_ribs(base, anchors)
    return g_part(cs), dict(seam_z=G_SEAM, section="L, 30 x 20, arm 8")


def g6_thin():
    cs = with_ribs(rect(5, 30), [(2.5, 0, "+x"), (-2.5, 0, "-x"), (0, 15, "+y"), (0, -15, "-y")])
    return g_part(cs, seam=3.0, cont=10.0), dict(seam_z=3.0, section="5 x 30 (minimum narrow side)")


def g7_overhang():
    part, _ = g1_square()
    # 0 deg ledge (bridge, needs support) on +X, 5 mm above the seam
    ledge = prism(rect(10, 12, 10 + 5 - 0.5, 0), 2.0).translate([0, 0, G_SEAM + 5])
    # 45 deg overhang on -X: a wedge growing outwards from z = seam + 2 to seam + 7
    wedge_profile = CrossSection([[(0, 0), (5, 5), (0, 5)]])  # (x, z) right triangle
    wedge = Manifold.extrude(wedge_profile, 12).translate([0, 0, -6]).rotate([90, 0, 0])
    wedge = wedge.rotate([0, 0, 180]).translate([-10 + 0.01, 0, G_SEAM + 2])
    part = part + ledge + wedge
    return part, dict(seam_z=G_SEAM, section="G1 + 0 deg ledge (+X, z = 25-27) + 45 deg overhang (-X, z = 22-27)")


MODELS = {
    "M1_tensile_D638-I_t7": m1_tensile,
    "M2_flex_80x10x5": m2_flex,
    "M3_shear_block_20x20x30": m3_shear,
    "G1_square_20": g1_square,
    "G2_cylinder_d20": g2_cylinder,
    "G3a_cone_10deg": lambda: g3_cone(10),
    "G3b_cone_25deg": lambda: g3_cone(25),
    "G4_tube_d24_d16": g4_tube,
    "G5_L_30x20": g5_l,
    "G6_thin_5x30": g6_thin,
    "G7_overhang": g7_overhang,
}


def recommended_wall(z):
    """LayerRescue's default insert wall height: clamp(Z/2, 3, 15) and at most Z - 1."""
    return round(min(max(z / 2, 3.0), 15.0, z - 1), 2)


def export(name, part):
    mesh = part.to_mesh()
    tri = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3],
                          faces=np.asarray(mesh.tri_verts), process=True)
    lo = tri.bounds[0]
    tri.apply_translation([-(tri.bounds[0][0] + tri.bounds[1][0]) / 2,
                           -(tri.bounds[0][1] + tri.bounds[1][1]) / 2, -lo[2]])
    tri.export(OUT / f"{name}.stl")
    return tri


def main():
    summary = {}
    for name, fn in MODELS.items():
        part, info = fn()
        tri = export(name, part)
        ext = tri.bounds[1] - tri.bounds[0]
        seam = info["seam_z"]
        summary[name] = {
            **info,
            "bbox_mm": [round(float(v), 2) for v in ext],
            "volume_cm3": round(tri.volume / 1000, 2),
            "watertight": bool(tri.is_watertight),
            "seam_layer_0p2": int(round(seam / LAYER)),
            "recommended_wall_mm": recommended_wall(seam),
        }
        print(f"{name:28s} bbox {summary[name]['bbox_mm']}  seam {seam} mm  watertight {tri.is_watertight}")
    (OUT / "models.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
