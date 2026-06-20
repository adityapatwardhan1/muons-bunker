"""Append voxel overlap DSC rows; uses canonical :func:`voxelize_data.percent_voxels_matching`."""
from voxelize_data import percent_voxels_matching
import sys
import csv
from geant4_pybind import *

def output_voxel_match_percentages_to_csv(orig_filename, mu_tot, voxel_size, cube_info_filename, add_column_titles):
    """Write overlap rows for one voxel size to ``VoxelOverlapDSC.csv``."""
    rows_to_write = []
    base = orig_filename[:-len("_nt_Hits.csv")] if orig_filename.endswith("_nt_Hits.csv") else orig_filename
    filename = base + "VoxelOverlapDSC.csv"
    with open(cube_info_filename, "r") as cube_info:
        reader = csv.reader(cube_info)
        next(reader)
        for row in reader:
            pX = float(row[0])*m
            pY = float(row[1])*m
            pZ = float(row[2])*m
            sL = float(row[3])*m
            single_row_to_write = row.copy()
            single_row_to_write.append(voxel_size) # or whatever
            single_row_to_write.append(percent_voxels_matching(orig_filename, mu_tot, voxel_size, pX-sL,pX+sL,pY-sL,pY+sL,pZ-sL,pZ+sL))
            rows_to_write.append(single_row_to_write)
    with open(filename, "a") as write_percentages:
        writer = csv.writer(write_percentages)
        if add_column_titles:
            writer.writerow(["pX(m)","pY(m)","pZ(m)","sideLengthHalf(m)","mat","voxelSize(mm)","percentDetected"])
        for row in rows_to_write:
            writer.writerow(row)
