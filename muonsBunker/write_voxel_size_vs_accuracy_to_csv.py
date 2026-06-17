"""Voxel overlap percent vs resolution; bounds from scene JSON."""
from voxelize_data import percent_voxels_matching
from scene_config import box_bounds_mm, load_scene_for_analysis
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
            # Ground-truth boxes from the run's resolved scene (geometry from simulation).
            for obj in scene.get("objects", []):
                if obj.get("shape", "box") != "box":
                    continue  # overlap helper is box-only for now

                # Scene positions are metres; overlap / voxel keys are mm.
                min_x, max_x, min_y, max_y, min_z, max_z = box_bounds_mm(obj)
                sL = float(obj["halfSide"]) * 1000.0  # half-side mm; full cube edge = 2*sL
                row = [obj["pX"], obj["pY"], obj["pZ"], obj["halfSide"], obj.get("mat", "")]

                # Try every voxel size that tiles the cube face evenly (divisor of 2*sL).
                for voxel_size in range(1, int(2 * sL) + 1):
                    if int(2 * sL) % voxel_size == 0:
                        single_row_to_write = row.copy()
                        single_row_to_write.append(voxel_size)
                        single_row_to_write.append(percent_voxels_matching(
                            raw_data_filename, mu_tot, voxel_size,
                            min_x, max_x, min_y, max_y, min_z, max_z))
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
                    for voxel_size in range(1, int(2 * sL) + 1):
                        single_row_to_write = row.copy()
                        if int(2 * sL) % voxel_size == 0:
                            single_row_to_write.append(voxel_size)
                            single_row_to_write.append(percent_voxels_matching(
                                raw_data_filename, mu_tot, voxel_size,
                                pX - sL, pX + sL, pY - sL, pY + sL, pZ - sL, pZ + sL))
                            rows_to_write.append(single_row_to_write)
        
        with open(out_filename, "w") as output:
            writer = csv.writer(output)
            writer.writerow(["pX(m)","pY(m)","pZ(m)","sideLengthHalf(m)","mat","voxelSize(mm)","percentDetected"])
            for row in rows_to_write:
                writer.writerow(row)
        print("wrote output to "+out_filename)
        
    else:
        print("Missing arguments. Terminating program")
