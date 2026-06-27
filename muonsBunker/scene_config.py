# Part of bunker-simulation (GPLv3). Scene JSON loader and autoAlign resolver.
# Provenance: stdlib json + validation patterns (original).

import copy
import json
import os


def _horizontal_extent(obj):
    shape = obj.get("shape", "box")
    if shape == "box":
        return float(obj["halfSide"])
    if shape == "cylinder":
        return float(obj["radius"])
    raise ValueError(f"unsupported object shape: {shape!r}")


def _extent_z(obj):
    shape = obj.get("shape", "box")
    if shape == "box":
        return float(obj["halfSide"])
    if shape == "cylinder":
        return float(obj["halfHeight"])
    raise ValueError(f"unsupported object shape: {shape!r}")


def _validate_object(obj, index):
    for key in ("name", "pX", "pY", "pZ", "shape", "mat"):
        if key not in obj:
            raise ValueError(f"objects[{index}] missing required field {key!r}")
    shape = obj["shape"]
    if shape == "box" and "halfSide" not in obj:
        raise ValueError(f"objects[{index}] box requires halfSide")
    if shape == "cylinder":
        for key in ("radius", "halfHeight"):
            if key not in obj:
                raise ValueError(f"objects[{index}] cylinder requires {key}")


def _validate_scene(scene):
    if "output" not in scene:
        raise ValueError("scene missing required section 'output'")
    for key in ("pathname", "foldername"):
        if key not in scene["output"]:
            raise ValueError(f"output missing required field {key!r}")
    if "objects" not in scene or not scene["objects"]:
        raise ValueError("scene requires non-empty objects[]")
    for i, obj in enumerate(scene["objects"]):
        _validate_object(obj, i)
    scene.setdefault("detector", {})
    scene.setdefault("source", {})
    scene.setdefault("run", {})
    det = scene["detector"]
    det.setdefault("minScatteringAngleDeg", 1.5)
    det.setdefault("maxScatteringAngleDeg", 30.0)
    det.setdefault("pocaZMarginFraction", 0.1)
    if det["minScatteringAngleDeg"] >= det["maxScatteringAngleDeg"]:
        raise ValueError(
            "detector.minScatteringAngleDeg must be < maxScatteringAngleDeg")
    z_frac = float(det["pocaZMarginFraction"])
    if not 0.0 <= z_frac < 0.5:
        raise ValueError("detector.pocaZMarginFraction must be in [0, 0.5)")
    det.setdefault("plateThicknessMm", 2.5)
    if float(det["plateThicknessMm"]) <= 0:
        raise ValueError("detector.plateThicknessMm must be > 0")
    pn = det.setdefault("positionNoise", {})
    pn.setdefault("enabled", False)
    pn.setdefault("sigmaMm", 1.0)
    pn.setdefault("sigmaZMm", None)
    if float(pn["sigmaMm"]) < 0:
        raise ValueError("detector.positionNoise.sigmaMm must be >= 0")
    if pn["sigmaZMm"] is not None and float(pn["sigmaZMm"]) < 0:
        raise ValueError("detector.positionNoise.sigmaZMm must be >= 0 when set")
    source = scene["source"]
    source.setdefault("autoAlignZMargin", 0.2)
    run = scene["run"]
    run.setdefault("seed", 1234)
    run.setdefault("reportTargetTraversal", True)
    run.setdefault("gatePoCAOnTargetTraversal", False)


def apply_auto_align(scene):
    """Override source center/radius from objects when autoAlign is true."""
    source = scene.setdefault("source", {})
    if not source.get("autoAlign", False):
        return scene
    objects = scene["objects"]
    detector = scene.get("detector", {})
    source["centerX"] = sum(float(o["pX"]) for o in objects) / len(objects)
    source["centerY"] = sum(float(o["pY"]) for o in objects) / len(objects)
    top_z = float(detector.get("topZ", 0.8))
    z_margin = float(source.get("autoAlignZMargin", 0.2))
    source["centerZ"] = top_z + z_margin
    source["radius"] = max(_horizontal_extent(o) for o in objects)
    return scene


def resolve_scene(scene):
    resolved = copy.deepcopy(scene)
    _validate_scene(resolved)
    apply_auto_align(resolved)
    return resolved


def load_scene(path):
    with open(path, "r") as f:
        scene = json.load(f)
    return resolve_scene(scene)


def resolve_scene_path(hits_csv_path):
    """Path to ``scene.resolved.json`` beside a hits file.

    Analysis uses only the resolved scene written by simulation at end of run.

    :param hits_csv_path: Path to ``*_nt_Hits.csv``.
    :returns: Absolute path to ``scene.resolved.json`` in the hits directory.
    :raises FileNotFoundError: if the resolved scene file is missing.
    """
    d = os.path.dirname(os.path.abspath(hits_csv_path))
    p = os.path.join(d, "scene.resolved.json")
    if not os.path.isfile(p):
        raise FileNotFoundError(
            f"analysis requires {p}; run simulation to write scene.resolved.json beside hits CSV"
        )
    return p


def get_voxel_filter_config(scene):
    """Merge ``analysis.voxelFilter`` from *scene* over code defaults.

    Code defaults: ``nFloor=5``, ``deltaThetaDeg=1.0``, ``poissonZ=2.0``,
    ``usePoissonExcess=True``, ``sRefMm=10.0``.
    """
    cfg = {"nFloor": 5, "deltaThetaDeg": 1.0, "poissonZ": 2.0, "usePoissonExcess": True, "sRefMm": 10.0}
    cfg.update(scene.get("analysis", {}).get("voxelFilter", {}))
    return cfg


def load_scene_for_analysis(hits_csv_path):
    """Load ``scene.resolved.json`` beside a hits CSV for analysis.

    Run geometry (detector, objects, traversal stats) and analysis settings
    come solely from the resolved file written at simulation time.

    :param hits_csv_path: Path to ``*_nt_Hits.csv``.
    :returns: Resolved scene dict.
    :raises FileNotFoundError: if ``scene.resolved.json`` is missing.
    """
    path = resolve_scene_path(hits_csv_path)
    with open(path) as f:
        return json.load(f)


def object_center_mm(obj):
    """Object centre ``(x, y, z)`` in mm from scene ``objects[]`` position fields."""
    return (
        float(obj["pX"]) * 1e3,
        float(obj["pY"]) * 1e3,
        float(obj["pZ"]) * 1e3,
    )


def box_bounds_mm(obj):
    """Axis-aligned box bounds for a scene ``objects[]`` entry.

    :param obj: Box object with ``pX``, ``pY``, ``pZ``, ``halfSide`` in metres.
    :returns: ``(min_x, max_x, min_y, max_y, min_z, max_z)`` in mm.
    """
    cx, cy, cz = object_center_mm(obj)
    h = float(obj["halfSide"]) * 1e3
    return (cx - h, cx + h, cy - h, cy + h, cz - h, cz + h)


def object_aabb_mm(obj):
    """Axis-aligned bounding box in mm for lattice sweeps (box or cylinder)."""
    shape = obj.get("shape", "box")
    if shape == "box":
        return box_bounds_mm(obj)
    if shape == "cylinder":
        cx, cy, cz = object_center_mm(obj)
        r = float(obj["radius"]) * 1e3
        hh = float(obj["halfHeight"]) * 1e3
        return (cx - r, cx + r, cy - r, cy + r, cz - hh, cz + hh)
    raise ValueError(f"unsupported object shape: {shape!r}")


def voxel_in_object(center, obj, half_voxel):
    """True if voxel centre (mm) lies inside *obj* with half-voxel slack."""
    shape = obj.get("shape", "box")
    if shape == "box":
        bounds = box_bounds_mm(obj)
        return (bounds[0] - half_voxel <= center[0] <= bounds[1] + half_voxel
                and bounds[2] - half_voxel <= center[1] <= bounds[3] + half_voxel
                and bounds[4] - half_voxel <= center[2] <= bounds[5] + half_voxel)
    if shape == "cylinder":
        cx, cy, cz = object_center_mm(obj)
        r = float(obj["radius"]) * 1e3 + half_voxel
        hh = float(obj["halfHeight"]) * 1e3 + half_voxel
        dx, dy, dz = center[0] - cx, center[1] - cy, center[2] - cz
        return dx * dx + dy * dy <= r * r and abs(dz) <= hh
    raise ValueError(f"unsupported object shape: {shape!r}")


def detector_bounds_mm(scene):
    """Detector ROI as an axis-aligned box in mm.

    ``detector.side`` is the G4Box *half*-extent in metres (see ``simulation.py``).
    """
    det = scene.get("detector", {})
    h = float(det.get("side", 1.0)) * 1e3
    return (-h, h, -h, h, float(det.get("bottomZ", 0)) * 1e3, float(det.get("topZ", 0.8)) * 1e3)
