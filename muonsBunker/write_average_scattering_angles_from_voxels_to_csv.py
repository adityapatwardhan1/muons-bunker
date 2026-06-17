"""ROI-scoped mean voxel angle vs resolution."""
from voxelize_data import get_avg_scattering_angle_among_voxels
import sys
import csv

# Arguments: filename, number of muons used, cube side length (120 is good since it's highly divisible)
if __name__ == '__main__':
    if len(sys.argv) == 4: # Specified voxel size
        cube_side_length = sys.argv[3]
        # Correct ``_nt_Hits.csv`` suffix strip for output basename
        base = sys.argv[1][:-len("_nt_Hits.csv")] if sys.argv[1].endswith("_nt_Hits.csv") else sys.argv[1]
        filename = base + "AverageScatteringAnglesCubeSideLength" + cube_side_length + "mm.csv"
        with open(filename, "w") as avg_voxel_angles_csv:
            writer = csv.writer(avg_voxel_angles_csv)
            writer.writerow(["Voxel Side Length (mm)", "Avg Scattering Angle (Degrees)"])
            for i in range(1,int(cube_side_length)):
                if int(sys.argv[3]) % i == 0:
                    writer.writerow([i, get_avg_scattering_angle_among_voxels(sys.argv[1], int(sys.argv[2]), i)])
        print("wrote output to "+filename)
    else:
        print("Missing arguments. Terminating program")
