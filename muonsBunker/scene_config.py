# Part of bunker-simulation (GPLv3). Scene JSON loader and autoAlign resolver.
# Provenance: stdlib json + validation patterns (original).

import copy
import json

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
