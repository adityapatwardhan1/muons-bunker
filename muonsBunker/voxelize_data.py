"""PoCA hit voxelization and two-stage discovery filter.

Bins simulation hits into voxels, applies a stability floor plus Poisson
excess test against a background shell, and exposes overlap/angle metrics.
"""
import csv
import json
import math
import sys

from scene_config import box_bounds_mm, detector_bounds_mm, get_voxel_filter_config, resolve_scene_path

def voxelize(filename, mu_tot, voxel_size=10):
    """Bin hits CSV into voxels and return median scattering angle per kept voxel.

    :param filename: Path to ``*_nt_Hits.csv`` from simulation.
    :param mu_tot: Beam-on count (kept for CLI compatibility; not used in filter math).
    :param voxel_size: Cube edge length in mm.
    :returns: ``(coordinate_to_median, headers)`` — dict keyed by voxel center
        ``(x, y, z)`` mm, plus Geant4 ntuple header rows from the input file.

    **Stage A (stability):** require ``N_v >= max(nFloor, ceil(r_ref * V_v/V_ref))``,
    optionally ``N_min_stat`` when background occupancy is high enough.

    **Stage B (discovery):** keep voxels with Poisson excess
    ``N_v >= lambda_bg + z * sqrt(lambda_bg)`` where ``lambda_bg`` is estimated
    from the background shell (inside detector, outside ``objects[]``).
    """
    coordinate_to_info_needed_for_median = dict()
    headers = []
    # Read file
    with open(filename, "r") as non_voxelized_csv:
        reader = csv.reader(non_voxelized_csv)
        for row in reader:
            # Get info needed for theta average
            if len(row) > 1:
                x = float(row[1])
                y = float(row[2])
                z = float(row[3])
                theta = float(row[4])
                
                voxel_coordinate = convert_to_voxel_coordinate((x, y, z), voxel_size)
                if not voxel_coordinate in coordinate_to_info_needed_for_median.keys():
                    coordinate_to_info_needed_for_median[voxel_coordinate] = [theta]
                else:
                    coordinate_to_info_needed_for_median[voxel_coordinate].append(theta)
            else:
                headers.append(row)
    # Estimate background rate r_ref from shell voxels in this run
    coordinate_to_median = dict()
    scene_path = resolve_scene_path(filename)
    scene = json.load(open(scene_path)) if scene_path else {}
    vf = get_voxel_filter_config(scene)
    half = voxel_size // 2
    v_v, v_ref = float(voxel_size) ** 3, float(vf["sRefMm"]) ** 3
    obj_bounds = [box_bounds_mm(o) for o in scene.get("objects", []) if o.get("shape", "box") == "box"]
    det_bounds = detector_bounds_mm(scene) if scene.get("detector") else None
    shell_norm, shell_thetas, shell_ns = [], [], []

    # Collect per-voxel stats in the background shell (detector ROI minus object boxes).
    for key, thetas in coordinate_to_info_needed_for_median.items():
        in_det = det_bounds and _voxel_in_roi(key, det_bounds, half)
        in_obj = any(_voxel_in_roi(key, b, half) for b in obj_bounds)
        if in_det and not in_obj:
            n = len(thetas)
            # Normalize hit count to reference voxel volume (default 10 mm cube)
            shell_norm.append(n * v_ref / v_v)
            shell_ns.append(n)
            shell_thetas.extend(thetas)
    n_floor = int(vf["nFloor"])

    # Derive r_ref and angle spread from shell; or degrade to nFloor-only if shell is empty.
    if shell_norm:
        shell_norm.sort()
        r_ref = median(shell_norm)
        sigma = _theta_std(shell_thetas)
        med_shell = median(sorted(shell_ns))
    else:
        # No shell voxels: fall back to nFloor only and skip Poisson excess.
        print("voxelize_data: empty background shell; nFloor-only", file=sys.stderr)
        r_ref, sigma, med_shell = float(n_floor), 5.0, 0.0
        vf = {**vf, "usePoissonExcess": False}
    n_min_stat = math.ceil((sigma / float(vf["deltaThetaDeg"])) ** 2)

    # Apply stability + Poisson filters; keep median theta for passing voxels.
    for key in coordinate_to_info_needed_for_median:
        n_v = len(coordinate_to_info_needed_for_median[key])
        lam = r_ref * v_v / v_ref  # expected background count at this voxel volume
        n_min = max(n_floor, math.ceil(lam))
        # Precision floor binds only when shell voxels already meet that occupancy
        if med_shell >= n_min_stat:
            n_min = max(n_min, n_min_stat)
        if n_v < n_min:
            continue
        if vf["usePoissonExcess"] and n_v < lam + float(vf["poissonZ"]) * math.sqrt(max(lam, 1e-9)):
            continue
        coordinate_to_info_needed_for_median[key].sort()
        coordinate_to_median[key] = median(coordinate_to_info_needed_for_median[key])

    return coordinate_to_median, headers


def get_avg_scattering_angle_among_voxels(orig_filename, mu_tot, voxel_size):
    """Mean median scattering angle over voxels inside target ``objects[]`` bounds.

    ROI scoping is for **evaluation metrics only** — not used in Stage B discovery.

    :returns: Average angle in degrees, or ``-1`` if no ROI voxels pass the filter.
    """
    all_voxels = voxelize(orig_filename, mu_tot, voxel_size)[0]
    if len(all_voxels) == 0:
        return -1
    scene_path = resolve_scene_path(orig_filename)
    if scene_path:
        scene = json.load(open(scene_path))
        half = voxel_size // 2
        obj_bounds = [box_bounds_mm(o) for o in scene.get("objects", []) if o.get("shape", "box") == "box"]
        roi = [all_voxels[k] for k in all_voxels if any(_voxel_in_roi(k, b, half) for b in obj_bounds)]
        if roi:
            return sum(roi) / len(roi)
        return -1
    return sum(all_voxels[key] for key in all_voxels) / len(all_voxels)


def convert_to_voxel_coordinate(coordinate, voxel_size):
    return (coordinate[0]//voxel_size*voxel_size + voxel_size//2, coordinate[1]//voxel_size*voxel_size + voxel_size//2, coordinate[2]//voxel_size*voxel_size + voxel_size//2)


def _voxel_in_roi(center, bounds, half_voxel):
    """True if voxel *center* (mm) overlaps axis-aligned *bounds* with half-voxel slack.

    :param bounds: ``(min_x, max_x, min_y, max_y, min_z, max_z)`` in mm.
    """
    return (bounds[0] - half_voxel <= center[0] <= bounds[1] + half_voxel
            and bounds[2] - half_voxel <= center[1] <= bounds[3] + half_voxel
            and bounds[4] - half_voxel <= center[2] <= bounds[5] + half_voxel)


def _theta_std(thetas):
    """Sample std of scattering angles (degrees) for stability-floor estimate.

    :returns: ``5.0`` when fewer than two shell angles are available.
    """
    if len(thetas) < 2:
        return 5.0
    m = sum(thetas) / len(thetas)
    return math.sqrt(sum((t - m) ** 2 for t in thetas) / (len(thetas) - 1))


def median(sorted_list):
    if len(sorted_list) == 0:
        return 0
    if len(sorted_list) % 2 == 1:
        return sorted_list[len(sorted_list)//2]
    return 0.5*(sorted_list[len(sorted_list)//2] + sorted_list[len(sorted_list)//2 - 1])    

def percent_voxels_matching(filename, mu_tot, voxel_size, min_x, max_x, min_y, max_y, min_z, max_z):
    """Overlap score between filtered voxels and a ground-truth box (percent).

    Only works reliably for a single cube. Bounds are in mm (same frame as voxel keys).
    """
    correct_num_voxels = round((max_x - min_x) / voxel_size) * round((max_y - min_y) / voxel_size) * round((max_z - min_z) / voxel_size) # Should it be round or ceil or floor, need voxel side length that is factor of cube side length
    all_voxels_with_object = voxelize(filename, mu_tot, voxel_size)[0]
    counted_voxels_in_bounds = 0
    counted_voxels_outside_bounds = 0
    for key in all_voxels_with_object.keys():
        if min_x-voxel_size//2 <= key[0] <= max_x+voxel_size//2 and min_y-voxel_size//2 <= key[1] <= max_y+voxel_size//2 and min_z-voxel_size//2 <= key[2] <= max_z+voxel_size//2:
            counted_voxels_in_bounds += 1
        else:
            counted_voxels_outside_bounds += 1
    # Overlap of correct and simulated set * 2 / union of all voxels correct and incorrect, as %
    # Weird metric but it is necessary to account for externally accidentally counted voxels
    return 100 * (2 * counted_voxels_in_bounds) / (correct_num_voxels + counted_voxels_in_bounds + counted_voxels_outside_bounds)       
