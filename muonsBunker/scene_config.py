# Part of bunker-simulation (GPLv3). Scene JSON loader and autoAlign resolver.
# Provenance: stdlib json + validation patterns (original).

import copy
import json
import os

AUTO_ALIGN_Z_MARGIN = 0.2  # m above detector topZ (matches legacy centerZ=1.0 at topZ=0.8)


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
    run = scene["run"]
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
    source["centerZ"] = top_z + AUTO_ALIGN_Z_MARGIN
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
    """Locate scene JSON for analysis beside a hits file.

    Search order: ``scene.resolved.json`` in the hits directory (written by
    simulation), then ``scene.json`` there, then package ``scene.json``.

    :param hits_csv_path: Path to ``*_nt_Hits.csv``.
    :returns: Absolute path, or ``None`` if no file is found.
    """
    d = os.path.dirname(os.path.abspath(hits_csv_path))
    for name in ("scene.resolved.json", "scene.json"):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scene.json")
    return p if os.path.isfile(p) else None


def get_voxel_filter_config(scene):
    """Merge ``analysis.voxelFilter`` from *scene* over code defaults.

    Prefer :func:`load_scene_for_analysis` so resolved run files inherit missing
    keys from package ``scene.json``. Code defaults: ``nFloor=5``,
    ``deltaThetaDeg=1.0``, ``poissonZ=2.0``, ``usePoissonExcess=True``,
    ``sRefMm=10.0``.
    """
    cfg = {"nFloor": 5, "deltaThetaDeg": 1.0, "poissonZ": 2.0, "usePoissonExcess": True, "sRefMm": 10.0}
    cfg.update(scene.get("analysis", {}).get("voxelFilter", {}))
    return cfg


def _package_scene_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "scene.json")


def load_scene_for_analysis(hits_csv_path):
    """Load scene JSON for analysis scripts and voxel filtering.

    Run geometry (detector, objects, traversal stats) comes from
    ``scene.resolved.json`` beside the hits file when present. Any
    ``analysis.voxelFilter`` keys absent there are filled from package
    ``scene.json`` so older resolved files without an ``analysis`` section
    still pick up project defaults (e.g. ``nFloor``).

    Traversal stats under ``run`` (plate crossings, target traversals) come from
    the resolved file only; they record simulation geometry acceptance, not
    analysis filter settings.

    :param hits_csv_path: Path to ``*_nt_Hits.csv``.
    :returns: Merged scene dict (possibly empty if no JSON is found).
    """
    path = resolve_scene_path(hits_csv_path)
    scene = {}
    if path:
        with open(path) as f:
            scene = json.load(f)
    pkg_path = _package_scene_path()
    if os.path.isfile(pkg_path):
        with open(pkg_path) as f:
            pkg_vf = json.load(f).get("analysis", {}).get("voxelFilter", {})
        if pkg_vf:
            merged_vf = scene.setdefault("analysis", {}).setdefault("voxelFilter", {})
            for key, val in pkg_vf.items():
                if key not in merged_vf:
                    merged_vf[key] = val
    return scene


def box_bounds_mm(obj):
    """Axis-aligned box bounds for a scene ``objects[]`` entry.

    :param obj: Box object with ``pX``, ``pY``, ``pZ``, ``halfSide`` in metres.
    :returns: ``(min_x, max_x, min_y, max_y, min_z, max_z)`` in mm.
    """
    cx, cy, cz = float(obj["pX"]) * 1e3, float(obj["pY"]) * 1e3, float(obj["pZ"]) * 1e3
    h = float(obj["halfSide"]) * 1e3
    return (cx - h, cx + h, cy - h, cy + h, cz - h, cz + h)


def detector_bounds_mm(scene):
    """Detector ROI as an axis-aligned box in mm.

    ``detector.side`` is the G4Box *half*-extent in metres (see ``simulation.py``).
    """
    det = scene.get("detector", {})
    h = float(det.get("side", 1.0)) * 1e3
    return (-h, h, -h, h, float(det.get("bottomZ", 0)) * 1e3, float(det.get("topZ", 0.8)) * 1e3)
