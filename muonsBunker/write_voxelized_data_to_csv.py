"""Write filtered voxel medians to CSV."""
from voxelize_data import voxelize
import sys
import csv

def output_voxels_to_csv(orig_filename, mu_tot, voxel_size):
    """Voxelize hits and write ``{run}VoxelsResolution{N}mm.csv``.

    :param orig_filename: Simulation ``*_nt_Hits.csv`` path.
    :param mu_tot: Beam-on count passed through to :func:`voxelize`.
    :param voxel_size: Voxel edge length in mm.
    """
    # Strip ``_nt_Hits.csv`` suffix (legacy code used wrong suffix ``ntHits.csv``)
    base = orig_filename[:-len("_nt_Hits.csv")] if orig_filename.endswith("_nt_Hits.csv") else orig_filename
    filename = base + "VoxelsResolution" + str(voxel_size) + "mm.csv"
    coordinate_to_median, headers = voxelize(orig_filename, mu_tot, voxel_size)
    with open(filename, "w") as voxelized_csv:
        writer = csv.writer(voxelized_csv)
        for header in headers:
            writer.writerow(header)
        for key in coordinate_to_median.keys():
            row = [0, key[0], key[1], key[2], coordinate_to_median[key]]
            writer.writerow(row)
    print("wrote voxelized data to "+filename)

# Run script
if __name__ == '__main__':
    if len(sys.argv) == 4:
        output_voxels_to_csv(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
    else:
        print("Missing arguments. Terminating program")
