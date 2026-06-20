"""Voxel overlap percent vs resolution; bounds from scene JSON."""
from voxelize_data import percent_voxels_matching, percent_voxels_matching_object
from scene_config import load_scene_for_analysis
import csv
import sys

if __name__ == '__main__':
    if len(sys.argv) > 2:
        raw_data_filename = sys.argv[1]
        mu_tot = int(sys.argv[2])

        # Output sits beside hits: resultsFoo_nt_Hits.csv -> resultsFooCubeHitPercentages.csv
        base = raw_data_filename[:-len("_nt_Hits.csv")] if raw_data_filename.endswith("_nt_Hits.csv") else raw_data_filename
        out_filename = base + "CubeHitPercentages.csv"
        rows_to_write = []

        scene = load_scene_for_analysis(raw_data_filename)
        if scene.get("objects"):
            for obj in scene.get("objects", []):
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
        else:
            # Legacy path when simulation did not write scene.resolved.json
            with open("cubeInfo.txt", "r") as cube_info:
                reader = csv.reader(cube_info)
                next(reader)
                for row in reader:
                    pX = float(row[0]) * 1000.0
                    pY = float(row[1]) * 1000.0
                    pZ = float(row[2]) * 1000.0
                    sL = float(row[3]) * 1000.0
                    legacy_row = ["", "box", row[0], row[1], row[2], row[3], "", "", row[4] if len(row) > 4 else ""]
                    for voxel_size in range(1, int(2 * sL) + 1):
                        if int(2 * sL) % voxel_size == 0:
                            single_row_to_write = legacy_row.copy()
                            single_row_to_write.append(voxel_size)
                            single_row_to_write.append(percent_voxels_matching(
                                raw_data_filename, mu_tot, voxel_size,
                                pX - sL, pX + sL, pY - sL, pY + sL, pZ - sL, pZ + sL))
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
