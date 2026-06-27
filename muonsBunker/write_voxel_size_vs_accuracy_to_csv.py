"""Voxel overlap percent vs resolution; bounds from scene JSON."""
from voxelize_data import percent_voxels_matching_object
from scene_config import load_scene_for_analysis
import csv
import sys

if __name__ == '__main__':
    if len(sys.argv) > 2:
        raw_data_filename = sys.argv[1]
        mu_tot = int(sys.argv[2])

        # Output sits beside hits: resultsFoo_nt_Hits.csv -> resultsFooVoxelOverlapDSC.csv
        base = raw_data_filename[:-len("_nt_Hits.csv")] if raw_data_filename.endswith("_nt_Hits.csv") else raw_data_filename
        out_filename = base + "VoxelOverlapDSC.csv"
        rows_to_write = []

        scene = load_scene_for_analysis(raw_data_filename)
        if not scene.get("objects"):
            raise ValueError(
                "scene.resolved.json has no objects[]; "
                "re-run simulation or fix the resolved scene beside the hits CSV"
            )
        for obj in scene["objects"]:
            shape = obj.get("shape", "box")
            row = [
                obj.get("name", ""),
                shape,
                obj["pX"],
                obj["pY"],
                obj["pZ"],
                obj.get("halfSide", ""),
                obj.get("radius", ""),
                obj.get("halfHeight", ""),
                obj.get("mat", ""),
            ]

            if shape == "box":
                sL = float(obj["halfSide"]) * 1000.0
                sweep_mm = int(2 * sL)
            elif shape == "cylinder":
                sweep_mm = int(2 * float(obj["radius"]) * 1000.0)
            else:
                continue

            for voxel_size in range(1, sweep_mm + 1):
                if sweep_mm % voxel_size == 0:
                    single_row_to_write = row.copy()
                    single_row_to_write.append(voxel_size)
                    single_row_to_write.append(
                        percent_voxels_matching_object(
                            raw_data_filename, mu_tot, voxel_size, obj))
                    rows_to_write.append(single_row_to_write)
        
        with open(out_filename, "w") as output:
            writer = csv.writer(output)
            writer.writerow([
                "objectName", "shape", "pX(m)", "pY(m)", "pZ(m)",
                "sideLengthHalf(m)", "radius(m)", "halfHeight(m)", "mat",
                "voxelSize(mm)", "percentDetected",
            ])
            for row in rows_to_write:
                writer.writerow(row)
        print("wrote output to "+out_filename)
        
    else:
        print("Missing arguments. Terminating program")
