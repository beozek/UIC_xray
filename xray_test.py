#!/usr/bin/env python3
# -*- coding: utf-8 -*-
##############################################################################
# Author: M.Antonello 
# Date: 29/07/2023
# Input: 1 physics root file of a X-Ray scan + 1 Thr root file + the relative txt file 
# Usage: python3 Missing_Full_Analysis_Ph2ACF_CROC.py -scurve Run000083 -noise Run000088 -outpath ADVCAM -sensor SH0054 -bias 80 -vref 785
# Output: png plots with the main results
# Variables to change: Sensor, Thr, VMAX (only if hot pixels are present) 
##############################################################################
import os
from scipy.optimize import curve_fit
import ROOT
ROOT.gErrorIgnoreLevel = ROOT.kWarning
ROOT.gROOT.SetBatch(True) 
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
# import mplhep as hep; hep.style.use("CMS")
try:
    import mplhep as hep
    hep.style.use("CMS")
except ImportError:
    print("mplhep not found, using default Matplotlib style")

import argparse
import matplotlib.patches as patches


# How to run manually:
# python xray_analysis.py -scurve Run0000041_SCurve -noise Run000000_NoiseScan -sensor SH0055



# Arguments --------------------
parser = argparse.ArgumentParser(description='Do the XRay analysis')

# Removed the -thr_strange argument as it's no longer used
# parser.add_argument('-thr_strange','--thr_strange', help = 'The threshold to classify the problematic bumps [Hits]', default = 1000, type = int)

parser.add_argument('-scurve','--scurve', help = 'The name of the SCurve.root (and txt) file', default = 'Run000021', type = str)
parser.add_argument('-noise','--noise', help = 'The name of the Noise.root file', default = 'Run000088', type = str)
parser.add_argument('-outpath','--outpath', help = 'The name of the folder to be created in results', default = 'results_xray_ToT', type = str)

# Removed the -chips argument as chips are now defined within the script
# parser.add_argument('-chips', '--chips', nargs='+', help='List of chip IDs to process', required=True) 

parser.add_argument('-sensor','--sensor', help = 'The name of the sensor', default = 'SH0054', type = str) #write the module name. 
parser.add_argument('-thr_missing','--thr_missing', help = 'The threshold to classify the missing bumps [Hits]', default = 200, type = int)
parser.add_argument('-bias','--bias', help = 'The bias of the sensor [V]', default = 80, type = float)  # Changed type to float
parser.add_argument('-vref','--vref', help = 'The VRef_ADC [mV]', default = 800, type = int)
parser.add_argument('-ntrg','--ntrg', help = 'The total # of triggers in the xml', default = 1e7, type = int)
parser.add_argument('-nbx','--nbx', help = 'The total # of bunch crossing for each trigger in the xml', default = 10, type = int)
parser.add_argument('-chiptype','--chiptype', help = 'Type of module (dual or quad)', default = 'quad', type = str)
args = parser.parse_args()

debug = False

# Set chip list based on module type
if args.chiptype.lower() == 'dual':
    chips = [12, 13]
else:  # Default to quad
    chips = [12, 13, 14, 15]

# Path to the SCurve root file (contains threshold data)
thr_data_file = f"{args.scurve}.root"

# X-ray output: NoiseScan root file
analyzed_data_file = f"{args.noise}.root"

# Path where the results will be stored
Path = args.outpath

# Thresholds and other parameters
Thr = args.thr_missing
Voltage_1 = args.bias
V_adc = args.vref
nTrg = args.ntrg
nBX = args.nbx

####### PARAMETERS TO BE CHANGED MANUALLY: ###################################  
num_rows = 336
num_cols = 432
FIT = True
el_conv = V_adc / 162
Noise_MAX = 65 * el_conv
Thr_MAX = 600 * el_conv 
step_noise = 0.1 * el_conv
step_thr = 2 * el_conv
YMAX = 100000
step = 10
VMAX = 7000
##############################################################################

# Ensure the base output path exists
base_output_path = os.path.join(Path, args.sensor)
if not os.path.exists(base_output_path):
    os.makedirs(base_output_path)
    print(f"Created directory: {base_output_path}")

# Reads a text file (x-ray txt) and creates a mask array indicating enabled pixels.
# ---------------- Hybrid Mappings ----------------
# SCurve expects HybridID = 0
scurve_hybrid_mapping = {
    12: '0',
    13: '0',
    14: '0',
    15: '0'
}

# Noise expects HybridID = 1
noise_hybrid_mapping = {
    12: '1',
    13: '1',
    14: '1',
    15: '1'
}


def GetMaskFromTxt(file_path, num_rows, num_cols):
    if not os.path.isfile(file_path):
        print(f"Mask file {file_path} does not exist.")
        return None
    array_2d = np.zeros((num_rows, num_cols))
    col = -1
    try:
        with open(file_path, 'r') as file:
            for line in file:
                if line.startswith("COL "):
                    col += 1
                if line.startswith("ENABLE "):
                    enable_row = line.replace("ENABLE ", "").strip().split(',')
                    for row, value in enumerate(enable_row):
                        array_2d[row, col] = int(value)
    except Exception as e:
        print(f"Error processing mask file {file_path}: {e}")
        return None
    return array_2d.T

def Ph2_ACFRootExtractor(infile, Scan_n, type, C_ID, H_ID):
    # Construct the full path to the canvas
    canvas_path = f"Detector/Board_0/OpticalGroup_0/Hybrid_{H_ID}/Chip_{int(C_ID)}/D_B(0)_O(0)_H({H_ID})_{Scan_n}_Chip({int(C_ID)})"
    
    if debug:
        print(f"Attempting to access canvas path: {canvas_path}")
    canvas = infile.Get(canvas_path)
    if not canvas:
        print(f"Error: Could not retrieve canvas at {canvas_path} from ROOT file.")
        return None
    
    # Construct the histogram name
    hist_name = f"D_B(0)_O(0)_H({H_ID})_{Scan_n}_Chip({int(C_ID)})"
    
    if debug:
        print(f"Attempting to retrieve histogram: {hist_name}")
    map_r = canvas.GetPrimitive(hist_name)
    if not map_r:
        print(f"Error: Could not retrieve histogram {hist_name} from canvas.")
        return None

    if debug:
        print(f"Extracting map from {Scan_n}...")
    
    if "2D" in type:
        # Convert the TH2F histogram to a numpy 2D array
        map = np.zeros((map_r.GetNbinsX(), map_r.GetNbinsY()))
        for i in range(1, map_r.GetNbinsX() + 1):
            for j in range(1, map_r.GetNbinsY() + 1):
                map[i - 1][j - 1] = map_r.GetBinContent(i, j)
        if debug:
            print(f"Extracted map shape: {map.T.shape}")
        return map.T  # Transpose to ensure the right shape

    elif "Entries" in type:
        # Handle 'Entries' type histograms (scalar counts)
        entries = map_r.GetEntries()
        if debug:
            print(f"Extracted entries: {entries}")
        return entries

    else:
        print("Error: Map extraction failed. Unsupported type.")
        return None


# Extracts threshold, noise, and time-over-threshold (ToT) maps from the SCurve ROOT file and converts them to the sensor's coordinate system.
def ExtractThrData(thr_data_file, C_ID, H_ID):
    inFile = ROOT.TFile.Open(thr_data_file, "READ")
    if not inFile or inFile.IsZombie():
        print(f"Cannot open {thr_data_file}.")
        return None, None, None, None, None, None, None

    ThrMap = Ph2_ACFRootExtractor(inFile, 'Threshold2D', '2D', C_ID, H_ID)
    if ThrMap is None:
        print(f"ThrMap extraction failed for chip {C_ID}.")
    ThrMap = To50x50SensorCoordinates(ThrMap) if ThrMap is not None else ThrMap

    NoiseMap = Ph2_ACFRootExtractor(inFile, 'Noise2D', '2D', C_ID, H_ID)
    if NoiseMap is None:
        print(f"NoiseMap extraction failed for chip {C_ID}.")
    NoiseMap = To50x50SensorCoordinates(NoiseMap) if NoiseMap is not None else NoiseMap

    ToTMap = Ph2_ACFRootExtractor(inFile, 'ToT2D', '2D', C_ID, H_ID)
    if ToTMap is None:
        print(f"ToTMap extraction failed for chip {C_ID}.")
    ToTMap = To50x50SensorCoordinates(ToTMap) if ToTMap is not None else ToTMap

    ReadoutErrors = Ph2_ACFRootExtractor(inFile, 'ReadoutErrors', 'Entries', C_ID, H_ID)
    FitErrors = Ph2_ACFRootExtractor(inFile, 'FitErrors', 'Entries', C_ID, H_ID)

    inFile.Close()

    Noise_L = NoiseMap.flatten() if NoiseMap is not None else None
    Thr_L = ThrMap.flatten() if ThrMap is not None else None

    return ThrMap, NoiseMap, ToTMap, ReadoutErrors, FitErrors, Noise_L, Thr_L


# Defines a Gaussian function and a function to fit a Gaussian to a histogram.
def gaus(X, A, X_mean, sigma):
    return A * np.exp(-(X - X_mean) ** 2 / (2 * sigma ** 2))

def GAUSS_FIT(x_hist, y_hist, color):
    try:
        mean = sum(x_hist * y_hist) / sum(y_hist)               
        sigma = np.sqrt(sum(y_hist * (x_hist - mean) ** 2) / sum(y_hist))
        # Gaussian least-square fitting process
        param_optimised, param_covariance_matrix = curve_fit(gaus, x_hist, y_hist, p0=[1, mean, sigma], maxfev=5000)
        x_hist_2 = np.linspace(np.min(x_hist), np.max(x_hist), 500)
        plt.plot(x_hist_2, gaus(x_hist_2, *param_optimised), color, 
                 label=f'FIT: μ = {param_optimised[1]:.1f} e$^-$ σ = {abs(param_optimised[2]):.1f} e$^-$')
    except Exception as e:
        print(f"Gaussian fit failed: {e}")

# X-Ray Analysis Function
def XRayAnalysis(nTrg, nBX, analyzed_data_file, C_ID, H_ID, analyzed_txt_file, Sensor, output_path):
    # FIND MISSING BUMPS:
    Mask_before = GetMaskFromTxt(analyzed_txt_file, num_rows, num_cols)  # 0 = MASKED, 1 = Good
    if Mask_before is None:
        print(f"Failed to retrieve mask from {analyzed_txt_file} for chip {C_ID}.")
        return None, None, None, None, None, None, None, None, None
    Disabled = np.where(Mask_before == 0)
    Mask_before_transformed = To50x50SensorCoordinates(Mask_before.T)

    # Open X-ray root file
    inFile = ROOT.TFile.Open(analyzed_data_file, "READ")
    if not inFile or inFile.IsZombie():
        print(f"Cannot open {analyzed_data_file}.")
        return None, None, None, None, None, None, None, None, None

    # Extract data
    Data = Ph2_ACFRootExtractor(inFile, 'PixelAlive', '2D', C_ID, H_ID)
    ToTMapX = Ph2_ACFRootExtractor(inFile, 'ToT2D', '2D', C_ID, H_ID)
    ReadoutErrorsXRay = Ph2_ACFRootExtractor(inFile, 'ReadoutErrors', 'Entries', C_ID, H_ID)  # Changed to 'Entries'
    inFile.Close()

    if Data is None or ToTMapX is None or ReadoutErrorsXRay is None:
        print(f"Data extraction failed for chip {C_ID}.")
        return Disabled[0].size, Data, None, None, None, ReadoutErrorsXRay, None, ToTMapX, None

    # Scale Data
    Data = Data * nTrg * nBX
    Data_L = Data.flatten()

    # Define ToT threshold
    ToT_threshold = 1

    # Create a mask for low hits and low ToT pixels
    low_hits = Data < Thr  # Pixels with hits less than Thr.
    low_ToT = ToTMapX < ToT_threshold  # Pixels with ToT <= ToT_threshold.
    low_hits_and_ToT = low_hits & low_ToT  # Identify pixels satisfying both conditions.

    # Initialize Mask_XRay
    Mask_XRay = np.ones((num_cols, num_rows)) + 1  # Start with 2 for GOOD pixels.

    # Apply both thresholds to Mask_XRay
    Cut = np.where(low_hits_and_ToT)
    Mask_XRay[Cut[1], Cut[0]] = 0  # MISSING pixels.

    # Combine masks
    Missing_mat = Mask_before + Mask_XRay  # 0=MASKED, 1=MISSING, 2=ERRORS, 3=GOOD
    Missing_mat[Missing_mat != 1] = 3  # All non-missing become GOOD.
    Missing = np.where(Missing_mat == 1)
    Perc_missing = float("{:.4f}".format((Missing[0].size / ((num_rows * num_cols) - Disabled[0].size)) * 100))

    # Coordinate transformation
    Data = To50x50SensorCoordinates(Data)
    Missing_mat = To50x50SensorCoordinates(Missing_mat.T)  # Transpose for consistency.
    ToTMapX = To50x50SensorCoordinates(ToTMapX)

    # Create a list of tuples (row, column) for missing pixels
    missing_pixels = [(Missing[1][i], Missing[0][i]) for i in range(len(Missing[1]))]

    # Sort the list of tuples by the first element (row)
    missing_pixels_sorted = sorted(missing_pixels, key=lambda x: x[0])

    # Print the sorted list of missing pixels
    print("Open Bump Coordinates (Row, Column):")
    for pixel in missing_pixels_sorted:
        print(f"({pixel[0]}, {pixel[1]})")

    # --- Save Missing Bumps Coordinates ---
    missing_pixels_file = os.path.join(output_path, "open_bumps.txt")
    try:
        with open(missing_pixels_file, 'w') as f_missing:
            f_missing.write("Missing Pixels Coordinates (Row, Column):\n")
            for pixel in missing_pixels_sorted:
                f_missing.write(f"({pixel[0]}, {pixel[1]})\n")
        
        if debug:
            print(f"Open bump saved to {missing_pixels_file}")
    except Exception as e:
        print(f"Error saving missing pixels to file: {e}")

    ##### --- New Addition: Save Number of Hits for Open Bumps ---
    open_bumps_hits_file = os.path.join(output_path, "open_bumps_hits.txt")
    try:
        with open(open_bumps_hits_file, 'w') as f_hits:
            f_hits.write("Missing Pixels Coordinates and Hits:\n")
            for pixel in missing_pixels_sorted:
                row, col = pixel
                hits = Data[row, col]  # Retrieve the number of hits for this pixel
                f_hits.write(f"({row}, {col}): {hits}\n")
        
        if debug:
            print(f"Open bump hits saved to {open_bumps_hits_file}")
    except Exception as e:
        print(f"Error saving open bump hits to file: {e}")
   
    ##### --- End of New Addition ---



    ##### Identify pixels with zero hits and are not masked

    # Create a mask for pixels with 0 hits
    zero_hits_pixels = np.where((Data == 0) & (Mask_before_transformed == 1))

    # Convert to list of coordinates in (row, column) order and sort
    zero_hits_pixel_list = [(zero_hits_pixels[0][i], zero_hits_pixels[1][i]) for i in range(len(zero_hits_pixels[0]))]
    zero_hits_pixel_list_sorted = sorted(zero_hits_pixel_list, key=lambda x: x[0])

    # Print the sorted list of zero-hit pixels
    print("Zero-Hit Pixels Coordinates (Row, Column):")
    for pixel in zero_hits_pixel_list_sorted:
        print(f"({pixel[0]}, {pixel[1]})")

    # --- Save Zero-Hit Pixels Coordinates ---
    zero_hits_pixels_file = os.path.join(output_path, "zero_hits_pixels.txt")
    try:
        with open(zero_hits_pixels_file, 'w') as f_zero_hits:
            f_zero_hits.write("Zero-Hit Pixels Coordinates (Row, Column):\n")
            for pixel in zero_hits_pixel_list_sorted:
                f_zero_hits.write(f"({pixel[0]}, {pixel[1]})\n")
        if debug:
            print(f"Zero-hit pixels saved to {zero_hits_pixels_file}")
    except Exception as e:
        print(f"Error saving zero-hit pixels to file: {e}")
    
    return Disabled[0].size, Data, Data_L, Missing_mat, Missing[0].size, ReadoutErrorsXRay, Perc_missing, ToTMapX, zero_hits_pixel_list_sorted


# Function to exclude high ToT pixels (not used in the current script but kept for reference)
def exclude_high_ToT_pixels(ToTMap, Mask_before, ToT_threshold=0):
    # Transpose Mask_before to match the shape of ToTMap if needed
    Mask_before = Mask_before.T

    # Create a mask that only includes pixels with ToT ≤ ToT_threshold and are enabled
    valid_pixels_mask = (ToTMap <= ToT_threshold) & (Mask_before == 1)

    # Apply this mask to filter the ToTMap and exclude pixels with ToT > threshold
    filtered_ToTMap = np.where(valid_pixels_mask, ToTMap, np.nan)  # Use NaN for excluded values

    return filtered_ToTMap

# Hits vs ToT Plot Function
def HitsVsToTPlot(Data, ToTMapX, Mask_before, output_path):
    # Flatten the data arrays
    Data_flat = Data.flatten()
    ToT_flat = ToTMapX.flatten()
    Mask_flat = Mask_before.T.flatten()  # Transpose to match the shape

    # Apply mask to include only enabled pixels
    valid_indices = np.where(Mask_flat == 1)
    Data_valid = Data_flat[valid_indices]
    ToT_valid = ToT_flat[valid_indices]

    # Define bins
    hits_bins_lower = np.linspace(0, 500, 100)  # 100 bins from 0 to 500
    hits_bins_upper = np.linspace(500, Data_valid.max(), 50)  # 50 bins from 500 to max hits
    hits_bins = np.concatenate((hits_bins_lower, hits_bins_upper[1:]))  # Avoid duplicate bin at 500

    ToT_bins = np.linspace(ToT_valid.min(), ToT_valid.max(), 50)

    # Regular 2D Histogram
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111)
    h = ax.hist2d(ToT_valid, Data_valid, bins=[ToT_bins, hits_bins],
                 norm=matplotlib.colors.LogNorm(), cmap='viridis')
    ax.set_xlabel('ToT')
    ax.set_ylabel('Number of Hits')
    ax.set_title('Number of Hits vs ToT for Pixels (Regular)')

    # ToT=1 and Hits=200 with labels
    ax.axvline(x=1, color='red', linestyle='--', linewidth=1, label='ToT = 1')
    ax.axhline(y=200, color='blue', linestyle='--', linewidth=1, label='Hits = 200')

    plt.colorbar(h[3], ax=ax, label='Number of Pixels')
    plt.grid(True)
    ax.legend(loc='upper right')
    plt.tight_layout()
    fig.savefig(os.path.join(output_path, f"{Voltage_1}V_Hits_vs_ToT_2Dhist_regular.png"), format='png', dpi=300)
    if debug:
        print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}V_Hits_vs_ToT_2Dhist_regular.png')}")
    plt.close(fig)  # Close the figure

    # Zoomed 2D Histogram with y-axis limited to 500 hits
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111)

    h_zoom = ax.hist2d(ToT_valid, Data_valid, bins=[ToT_bins, hits_bins],
                       norm=matplotlib.colors.LogNorm(), cmap='viridis')
    ax.set_ylim([0, 500])

    ax.set_xlabel('ToT')
    ax.set_ylabel('Number of Hits')
    ax.set_title('Number of Hits vs ToT for Pixels (Hits up to 500)')

    ax.axvline(x=1, color='red', linestyle='--', linewidth=1, label='ToT = 1')
    ax.axhline(y=200, color='blue', linestyle='--', linewidth=1, label='Hits = 200')

    plt.colorbar(h_zoom[3], ax=ax, label='Number of Pixels')
    plt.grid(True)
    ax.legend(loc='upper right')
    plt.tight_layout()
    fig.savefig(os.path.join(output_path, f"{Voltage_1}V_Hits_vs_ToT_2Dhist_hits_500.png"), format='png', dpi=300)
    if debug:
        print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}V_Hits_vs_ToT_2Dhist_hits_500.png')}")
    plt.close(fig)  # Close the figure

# Plotting Function
def Plots(ToTMap, NoiseMap, Noise_L, ThrMap, Thr_L, Data, Data_L, Missing_mat, Missing, Perc_missing, Disabled, ToTMapX, FitErrors, Mask_before, Sensor, output_path):
    # Transform the mask to match the data coordinates
    Mask_before_transformed = To50x50SensorCoordinates(Mask_before.T)
    Mask_flat = Mask_before_transformed.flatten()

    # Find indices of unmasked pixels (where mask value is 1)
    unmasked_indices = np.where(Mask_flat == 1)

    # Filter the Data_L to include only unmasked pixels
    Data_L_filtered = Data_L[unmasked_indices]

    # Noise Map: This plot shows the distribution of noise levels across the sensor.
    fig1 = plt.figure()
    ax = fig1.add_subplot(111)
    ax.spines["bottom"].set_linewidth(1)
    ax.spines["left"].set_linewidth(1)
    ax.spines["top"].set_linewidth(1)
    ax.spines["right"].set_linewidth(1)
    imgplot = ax.imshow(NoiseMap * el_conv, vmax=Noise_MAX)  # 150 vmax
    ax.set_aspect(1)
    plt.colorbar(imgplot, orientation='horizontal', extend='max', label='electrons')
    fig1.savefig(os.path.join(output_path, f"{Voltage_1}V_Noise_Map.png"), format='png', dpi=300)
    if debug:
        print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}V_Noise_Map.png')}")

    plt.close(fig1)  # Close the figure

    # Noise Histogram
    fig2 = plt.figure(figsize=(1050/96, 750/96), dpi=96)
    ax = fig2.add_subplot(111)
    ax.spines["bottom"].set_linewidth(1)
    ax.spines["left"].set_linewidth(1)
    ax.spines["top"].set_linewidth(1)
    ax.spines["right"].set_linewidth(1)
    h_S = plt.hist(Noise_L * el_conv, color='black', bins=np.arange(0, Noise_MAX, step_noise), label='Noise', histtype='step')
    if FIT:
        GAUSS_FIT(h_S[1][:-1], h_S[0], 'red')
    ax.set_ylim([0.1, 10000])
    ax.set_yscale('log')
    ax.set_xlabel('electrons')
    ax.set_ylabel('entries')
    ax.legend(prop={'size': 14}, loc='upper right')
    fig2.savefig(os.path.join(output_path, f"{Voltage_1}V_Noise_Hist.png"), format='png', dpi=300)
    if debug:
        print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}V_Noise_Hist.png')}")
    plt.close(fig2)  # Close the figure

    # Threshold Map: This plot shows the threshold levels across the sensor.
    fig3 = plt.figure()
    ax = fig3.add_subplot(111)
    ax.spines["bottom"].set_linewidth(1)
    ax.spines["left"].set_linewidth(1)
    ax.spines["top"].set_linewidth(1)
    ax.spines["right"].set_linewidth(1)
    imgplot = ax.imshow(ThrMap * el_conv, vmax=Thr_MAX, vmin=1200, origin='lower')  # 3500 vmax
    ax.set_aspect(1)
    plt.colorbar(imgplot, orientation='horizontal', extend='max', label='electrons')
    fig3.savefig(os.path.join(output_path, f"{Voltage_1}V_Threshold_Map.png"), format='png', dpi=300)
    if debug:
        print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}V_Threshold_Map.png')}")
    plt.close(fig3)  # Close the figure

    # ToT Map: This plot shows the time-over-threshold values across the sensor.
    fig7 = plt.figure()
    ax = fig7.add_subplot(111)
    ax.spines["bottom"].set_linewidth(1)
    ax.spines["left"].set_linewidth(1)
    ax.spines["top"].set_linewidth(1)
    ax.spines["right"].set_linewidth(1)
    imgplot = ax.imshow(ToTMap, origin='lower')
    ax.set_aspect(1)
    plt.colorbar(imgplot, orientation='horizontal', extend='max', label='ToT')
    fig7.savefig(os.path.join(output_path, f"{Voltage_1}V_ToT_Map.png"), format='png', dpi=300)
    if debug:
        print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}V_ToT_Map.png')}")
    plt.close(fig7)  # Close the figure

    # ToT Map XRay: This plot shows the ToT values specifically for the X-ray scan.
    fig10 = plt.figure()
    ax = fig10.add_subplot(111)
    ax.spines["bottom"].set_linewidth(1)
    ax.spines["left"].set_linewidth(1)
    ax.spines["top"].set_linewidth(1)
    ax.spines["right"].set_linewidth(1)
    imgplot = ax.imshow(ToTMapX, origin='lower')
    ax.set_aspect(1)
    plt.colorbar(imgplot, orientation='horizontal', extend='max', label='ToT')
    fig10.savefig(os.path.join(output_path, f"{Voltage_1}V_ToT_Map_XRay.png"), format='png', dpi=300)
    if debug:
        print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}V_ToT_Map_XRay.png')}")
    plt.close(fig10)  # Close the figure

    # Threshold Histogram: This plot shows the distribution of threshold levels across the sensor.
    fig4 = plt.figure(figsize=(1050/96, 750/96), dpi=96)
    ax = fig4.add_subplot(111)
    ax.spines["bottom"].set_linewidth(1)
    ax.spines["left"].set_linewidth(1)
    ax.spines["top"].set_linewidth(1)
    ax.spines["right"].set_linewidth(1)
    h_L = plt.hist(Thr_L * el_conv, color='black', bins=np.arange(0, Thr_MAX, step_thr), label='Threshold', histtype='step')
    if FIT:
        GAUSS_FIT(h_L[1][:-1], h_L[0], 'red')
    ax.set_ylim([0.1, YMAX])
    ax.set_xlim([0, Thr_MAX])
    ax.set_yscale('log')
    ax.set_xlabel('electrons')
    ax.set_ylabel('entries')
    ax.legend(prop={'size': 14}, loc='upper left')
    fig4.savefig(os.path.join(output_path, f"{Voltage_1}V_Threshold_Hist.png"), format='png', dpi=300)
    if debug:
        print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}V_Threshold_Hist.png')}")
    plt.close(fig4)  # Close the figure

    # XRAY PART
    # HITS/PXL HISTOGRAM WITH X-RAYS: This plot shows the distribution of hits per pixel with X-rays.
    fig5 = plt.figure(figsize=(1050/96, 750/96), dpi=96)
    ax = fig5.add_subplot(111)
    ax.spines["bottom"].set_linewidth(1)
    ax.spines["left"].set_linewidth(1)
    ax.spines["top"].set_linewidth(1)
    ax.spines["right"].set_linewidth(1)
    ax.set_yscale('log')
    ax.set_xscale('log')    
    h_LIN = plt.hist(Data_L_filtered, color='black', bins=range(0, int(VMAX*3.0), step), label='Hits/pixel', histtype='step')
    ax.set_xlabel('Number of total Hits/pixel')
    ax.set_ylabel('Entries')
    ax.legend(prop={'size': 14}, loc='upper right')
    fig5.savefig(os.path.join(output_path, f"{Voltage_1}V_Hist_Thr_{Thr}.png"), format='png', dpi=300)
    if debug:
        print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}V_Hist_Thr_{Thr}.png')}")
    plt.close(fig5)  # Close the figure

    # Raw Hit Map from XRay alone: This plot shows the raw hits map from the X-ray scan.
    fig8 = plt.figure()
    ax = fig8.add_subplot(111)
    ax.spines["bottom"].set_linewidth(1)
    ax.spines["left"].set_linewidth(1)
    ax.spines["top"].set_linewidth(1)
    ax.spines["right"].set_linewidth(1)
    imgplot = ax.imshow(Data, vmax=VMAX, origin='lower')
    ax.set_aspect(1)
    plt.colorbar(imgplot, orientation='horizontal', extend='max', label='Hits')
    fig8.savefig(os.path.join(output_path, f"{Voltage_1}_XRay_Hits_Map.png"), format='png', dpi=300)
    if debug:
        print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}_XRay_Hits_Map.png')}")
    plt.close(fig8)  # Close the figure

    # Raw Hit Map from XRay alone: This plot shows a zoomed-in view of the raw hits map from the X-ray scan.
    fig9 = plt.figure()
    ax = fig9.add_subplot(111)
    ax.spines["bottom"].set_linewidth(1)
    ax.spines["left"].set_linewidth(1)
    ax.spines["top"].set_linewidth(1)
    ax.spines["right"].set_linewidth(1)
    imgplot = ax.imshow(Data[0:35,0:15], vmax=VMAX, origin='lower')
    ax.set_aspect(1)
    plt.colorbar(imgplot, orientation='horizontal', extend='max', label='Hits')
    fig9.savefig(os.path.join(output_path, f"{Voltage_1}_XRay_Hits_Map_zoom.png"), format='png', dpi=300)
    if debug:
        print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}_XRay_Hits_Map_zoom.png')}")
    plt.close(fig9)  # Close the figure

    # MISSING BUMPS FINAL MAPS
    # Missing Bumps Final Maps: This subplot shows two maps side-by-side:
        # Hit Map: Visualizes the hit data with a color bar indicating the number of hits.
        # Missing Map: Visualizes the status of each pixel (problematic, masked, missing, good) with a color bar.
        # Super Title: Provides a summary of the sensor analysis, including the number and percentage of missing and problematic bumps.
        # Aspect Ratio: The aspect ratio is set to 1 for better visualization.
    # fig6, (ax1, ax2) = plt.subplots(1,2, figsize=(13, 7.5))
    # plt.rcParams.update({'font.size': 16})
    
    # fig6.suptitle(f"Sensor {Sensor} -- Missing bumps (<{Thr} hits): {Missing} ({Perc_missing}%)")
    # imgplot = ax1.imshow(Data, vmax=VMAX, origin='lower')
    # ax1.set_title(f"Hit Map (Z Lim: {VMAX} hits)")
    # ax1.set_aspect(1)
    # ax1.spines["bottom"].set_linewidth(1)
    # ax1.spines["left"].set_linewidth(1)
    # ax1.spines["top"].set_linewidth(1)
    # ax1.spines["right"].set_linewidth(1)
    # plt.colorbar(imgplot, orientation='horizontal', ax=ax1, extend='max', label='Hits', shrink=1)

    # # Missing Map: missing bumps
    # # Create a new matrix for plotting, where missing bumps are marked distinctly
    # Emphasis_mat = np.copy(Missing_mat.T)
    # Emphasis_mat[Emphasis_mat != 1] = 0  # Set all non-missing pixels to 0
    # Emphasis_mat[Emphasis_mat == 1] = 1  # Missing bumps remain as 1

    # # Define a colormap with contrasting colors
    # cmap = matplotlib.colors.ListedColormap(['gray', 'red'])  # Non-missing pixels in gray, missing bumps in red
    # bounds = [-0.5, 0.5, 1.5]
    # norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)

    # # Plot the Emphasis Map
    # imgplot2 = ax2.imshow(Emphasis_mat, cmap=cmap, norm=norm, origin='lower', interpolation='nearest')
    # ax2.set_title("Open Bumps Map")
    # ax2.set_aspect(1)
    # ax2.spines["bottom"].set_linewidth(1)
    # ax2.spines["left"].set_linewidth(1)
    # ax2.spines["top"].set_linewidth(1)
    # ax2.spines["right"].set_linewidth(1)

    # cbar = plt.colorbar(imgplot2, ticks=[0, 1], orientation='horizontal', ax=ax2, shrink=1)
    # cbar.ax.set_xticklabels(['Good', 'Missing'])

    # fig6.savefig(os.path.join(output_path, f"{Voltage_1}V_Missing_Bumps_Thr_{Thr}.png"), format='png', dpi=300)
    # if debug:
    #     print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}V_Missing_Bumps_Thr_{Thr}.png')}")
    # plt.close(fig6)  # Close the figure
    

    fig6, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 7.5))
    plt.rcParams.update({'font.size': 16})

    # Set title with missing percentage
    fig6.suptitle(f"Sensor {Sensor} -- Missing bumps (<{Thr} hits): {Missing} ({Perc_missing}%)")

    # Correctly visualize the hit map
    imgplot = ax1.imshow(Data, vmax=VMAX, origin='lower')
    ax1.set_title(f"Hit Map (Z Lim: {VMAX} hits)")
    ax1.set_aspect(1)
    ax1.spines["bottom"].set_linewidth(1)
    ax1.spines["left"].set_linewidth(1)
    ax1.spines["top"].set_linewidth(1)
    ax1.spines["right"].set_linewidth(1)
    plt.colorbar(imgplot, orientation='horizontal', ax=ax1, extend='max', label='Hits', shrink=1)

    # Prepare the missing bumps map
    # Define a new matrix to highlight missing bumps (rows should be on the y-axis)
    Emphasis_mat = np.copy(Missing_mat)  # Use the transposed matrix directly if it aligns correctly
    Emphasis_mat[Emphasis_mat != 1] = 0  # Only keep missing bumps

    # Define a colormap to distinguish missing bumps
    cmap = matplotlib.colors.ListedColormap(['yellow', 'black'])
    bounds = [-0.5, 0.5, 1.5]
    norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)

    # Plot the missing bumps map with rows on the y-axis
    imgplot2 = ax2.imshow(Emphasis_mat, cmap=cmap, norm=norm, origin='lower', interpolation='nearest')
    ax2.set_title("Open Bump Map")
    ax2.set_xlabel("Column")
    ax2.set_ylabel("Row")
    ax2.set_aspect(1)
    ax2.spines["bottom"].set_linewidth(1)
    ax2.spines["left"].set_linewidth(1)
    ax2.spines["top"].set_linewidth(1)
    ax2.spines["right"].set_linewidth(1)

    # Color bar for the missing bumps map
    cbar = plt.colorbar(imgplot2, ticks=[0, 1], orientation='horizontal', ax=ax2, shrink=1)
    cbar.ax.set_xticklabels(['Good', 'Open Bump'])

    fig6.savefig(os.path.join(output_path, f"{Voltage_1}V_Missing_Bumps_Thr_{Thr}.png"), format='png', dpi=300)
    plt.close(fig6)  # Close the figure

    return

# ToT Histogram Function
def ToTHistogram(ToTMap, output_path):
    # Flatten the 2D ToT map to a 1D array
    ToT_flattened = ToTMap.flatten()
    
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111)
    ax.spines["bottom"].set_linewidth(1)
    ax.spines["left"].set_linewidth(1)
    ax.spines["top"].set_linewidth(1)
    ax.spines["right"].set_linewidth(1)

    plt.hist(ToT_flattened, bins=50, color='blue', alpha=0.7, label='ToT values')
    ax.set_xlabel('ToT')
    ax.set_ylabel('Entries')
    ax.set_yscale('log')
    ax.legend(loc='upper right')
    plt.title('1D Histogram of Time-over-Threshold (ToT)')
    plt.grid(True)

    fig.savefig(os.path.join(output_path, f"{Voltage_1}V_ToT_Histogram.png"), format='png', dpi=300)
    if debug:
        print(f"Saved plot: {os.path.join(output_path, f'{Voltage_1}V_ToT_Histogram.png')}")
    plt.close(fig)  # Close the figure

def list_enabled_pixels_below_threshold(ToTMap, Mask_before, threshold=0):
    Mask_before_transformed = To50x50SensorCoordinates(Mask_before.T)

    # Find pixels with ToT values below the given threshold, but only those that are enabled (not masked)
    low_ToT_pixels = np.argwhere((ToTMap < threshold) & (Mask_before_transformed == 1))

    # Print and store the coordinates of these pixels
    print(f"Enabled pixels with ToT below {threshold}:")
    pixel_list = []
    for pixel in low_ToT_pixels:
        row, col = pixel
        print(f"({row}, {col})")
        pixel_list.append((row, col))

    return pixel_list

# Terminal Information Printing Function
# Terminal Information Printing Function
def TerminalInfos(FitErrors, ReadoutErrors, Disabled, ReadoutErrorsXRay, Missing, Perc_missing, Missing_mat, num_zero_hits_pixels):
    print('##############################################################')
    print(' INFO')
    print('##############################################################')
    
    # Print the counts directly since they are scalars
    print(f"Failed fits (thr):\t{FitErrors}")
    print(f"Readout Errors (thr):\t{ReadoutErrors}")
    print(f"Readout Errors (xray):\t{ReadoutErrorsXRay}")
    
    # If no errors, confirm
    if FitErrors == 0 and ReadoutErrors == 0 and ReadoutErrorsXRay == 0:
        print("No errors detected.")
    
    # Continue with other information
    print(f"Masked before:\t\t{Disabled}")
    print(f"Missing (<{Thr} and ToT < 1):\t{Missing} ({Perc_missing}%)")
    print("Check from Final matrix:")
    print(f"Masked before:\t\t{np.where(Missing_mat == 0)[0].size}")
    print(f"Pixels with zero hits:\t{num_zero_hits_pixels}")
    print(f"Missing(<{Thr} and ToT<1): {np.where(Missing_mat == 1)[0].size}")
    print(f"Good:\t\t\t{np.where(Missing_mat == 3)[0].size}")
    total_pixels = (np.where(Missing_mat == 0)[0].size +
                    np.where(Missing_mat == 1)[0].size +
                    np.where(Missing_mat == 2)[0].size +
                    np.where(Missing_mat == 3)[0].size +
                    np.where(Missing_mat == -1)[0].size)
    print(f"Sum is: \t\t{total_pixels}")
    print(f"Total # of pixels:\t{num_cols * num_rows}")
    print('##############################################################\n')
    return



# Coordinate Transformation Functions
def To25x100SensorCoordinates(npArray):
    new_rows = num_rows * 2
    new_cols = num_cols // 2
    NewArray = np.zeros((new_rows, new_cols), dtype=npArray.dtype)
    for i in range(num_cols):
        for j in range(num_rows):
            # Conversion from CMSIT converter plugin for 25x100r0c0 of Mauro
            row = 2 * j + (i % 2)
            col = int(i / 2)
            NewArray[row, col] = npArray[j, i]
    return NewArray

def To50x50SensorCoordinates(npArray):
    return npArray

def print_pixel_info(Data, ToTMap, pixel_row, pixel_col):
    """
    Prints the number of hits and ToT value for a given pixel.

    Parameters:
    - Data: 2D numpy array with the number of hits.
    - ToTMap: 2D numpy array with the ToT values.
    - pixel_row: Row index of the pixel (integer).
    - pixel_col: Column index of the pixel (integer).
    """
    try:
        # Get the hits and ToT values for the pixel
        hits = Data[pixel_row, pixel_col]
        tot = ToTMap[pixel_row, pixel_col]
        print(f"Pixel (Row: {pixel_row}, Column: {pixel_col}) -> Hits: {hits}, ToT: {tot}")
    except IndexError as e:
        print(f"Error: The specified pixel (Row: {pixel_row}, Column: {pixel_col}) is out of bounds.")
    except Exception as e:
        print(f"Error while retrieving data for pixel (Row: {pixel_row}, Column: {pixel_col}): {e}")

def find_common_pixels(missing_pixels_file, zero_hits_pixels_file, output_path):
    """
    Finds common pixels between missing_pixels_file and zero_hits_pixels_file.
    Saves the common pixels to a new text file.
    
    Parameters:
    - missing_pixels_file: Path to the missing pixels text file.
    - zero_hits_pixels_file: Path to the zero-hit pixels text file.
    - output_path: Directory where the common pixels file will be saved.
    """
    def read_pixels(file_path):
        pixels = set()
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    if line.startswith("Missing") or line.startswith("Zero-Hit") or line.startswith("Pixels"):
                        continue
                    line = line.strip()
                    if not line:
                        continue  # Skip empty lines
                    # Format: (Row, Column)
                    if line.startswith("(") and line.endswith(")"):
                        try:
                            row, col = map(int, line[1:-1].split(","))
                            pixels.add((row, col))
                        except ValueError:
                            print(f"Warning: Could not parse line '{line}' in {file_path}. Skipping.")
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
        return pixels
    
    missing_pixels = read_pixels(missing_pixels_file)
    zero_hits_pixels = read_pixels(zero_hits_pixels_file)
    
    print(f"Total missing pixels: {len(missing_pixels)}")
    print(f"Total zero-hit pixels: {len(zero_hits_pixels)}")
    
    common_pixels = missing_pixels.intersection(zero_hits_pixels)
    print(f"Common pixels (present in both files): {len(common_pixels)}")
    
    common_pixels_file = os.path.join(output_path, "common_pixels.txt")
    try:
        with open(common_pixels_file, 'w') as f_common:
            f_common.write("Common Pixels Coordinates (Row, Column):\n")
            for pixel in sorted(common_pixels, key=lambda x: (x[0], x[1])):
                f_common.write(f"({pixel[0]}, {pixel[1]})\n")
        print(f"Common pixels saved to {common_pixels_file}")
    except Exception as e:
        print(f"Error writing common pixels to file: {e}")

# Main Function
def main():
    # Define hybrid mapping: All chips under Hybrid_0
    # hybrid_mapping = {
    #     12: '0',
    #     13: '0',
    #     14: '0',  # Changed from '1' to '0'
    #     15: '0'   # Changed from '1' to '0'
    # }

    for chip_id in chips:
        # SCurve mapping
        scurve_H_ID = scurve_hybrid_mapping.get(chip_id, '0')
        # Noise mapping
        noise_H_ID  = noise_hybrid_mapping.get(chip_id, '1')

        print(f"\nProcessing chip {chip_id} -> SCurve H_ID={scurve_H_ID}, Noise H_ID={noise_H_ID}")

        # C_ID = chip_id
        # H_ID = hybrid_mapping.get(C_ID, '0')  # Default to '0' if not specified
        # print(f"\nProcessing chip {chip_id} under Hybrid {H_ID}")
        
        # Adjust file names based on the chip ID
        Sensor = f"{args.sensor}_Chip{chip_id}"
        analyzed_txt_file = f"CMSIT_RD53_{args.sensor}_0_{chip_id}_OUT.txt"  # Adjust as needed

        # Check if analyzed_txt_file exists
        if not os.path.isfile(analyzed_txt_file):
            print(f"Analyzed text file {analyzed_txt_file} does not exist. Skipping chip {chip_id}.")
            continue

        # Create output directory for this chip if it doesn't exist
        output_path = os.path.join(Path, Sensor)
        if not os.path.exists(output_path):
            os.makedirs(output_path)
            print(f"Created directory: {output_path}")

        # Extract threshold data for this chip
        ThrMap, NoiseMap, ToTMap, ReadoutErrors, FitErrors, Noise_L, Thr_L = ExtractThrData(thr_data_file, C_ID=chip_id, H_ID=scurve_H_ID)
        # ThrMap, NoiseMap, ToTMap, ReadoutErrors, FitErrors, Noise_L, Thr_L = ExtractThrData(thr_data_file, C_ID, H_ID)
        if ThrMap is None:
            print(f"Skipping chip {chip_id}: SCurve ThrMap extraction failed.")
            continue

        # Analyze X-ray data for this chip
        Disabled, Data, Data_L, Missing_mat, Missing, ReadoutErrorsXRay, Perc_missing, ToTMapX, zero_hits_pixel_list_sorted = XRayAnalysis(nTrg, nBX, analyzed_data_file, C_ID=chip_id, H_ID=noise_H_ID, analyzed_txt_file=analyzed_txt_file, Sensor=Sensor, output_path=output_path)
        # XRayAnalysis(nTrg, nBX, analyzed_data_file, C_ID, H_ID, analyzed_txt_file, Sensor, output_path)
        
        
        
        
        if Missing_mat is None:
            # print(f"Skipping chip {C_ID} due to Missing_mat extraction failure.")
            print(f"Skipping chip {chip_id}: Missing_mat extraction failed.")

            continue

        # Obtain the mask array for this chip
        Mask_before = GetMaskFromTxt(analyzed_txt_file, num_rows, num_cols)
        if Mask_before is None:
            # print(f"Skipping chip {C_ID} due to Mask_before extraction failure.")
            print(f"Skipping chip {chip_id}: Mask extraction failure.")

            continue

        # Plot the results
        Plots(ToTMap, NoiseMap, Noise_L, ThrMap, Thr_L, Data, Data_L, Missing_mat,
              Missing, Perc_missing, Disabled, ToTMapX, FitErrors, Mask_before, Sensor, output_path)

        # Create a 1D histogram for all ToT data
        ToTHistogram(ToTMapX, output_path)

        # Plot hits vs ToT without excluding zero values
        HitsVsToTPlot(Data, ToTMapX, Mask_before, output_path)

        # List enabled pixels below threshold if needed
        low_ToT_pixels = list_enabled_pixels_below_threshold(ToTMapX, Mask_before, threshold=0)

        # Calculate the number of zero-hit pixels
        num_zero_hits_pixels = len(zero_hits_pixel_list_sorted)

        # Print terminal information
        TerminalInfos(FitErrors, ReadoutErrors, Disabled, ReadoutErrorsXRay, Missing,
                      Perc_missing, Missing_mat, num_zero_hits_pixels)
        
        # --- Compare Missing and Zero-Hit Pixels ---
        missing_pixels_file = os.path.join(output_path, "open_bumps.txt")
        zero_hits_pixels_file = os.path.join(output_path, "zero_hits_pixels.txt")
        
        if os.path.isfile(missing_pixels_file) and os.path.isfile(zero_hits_pixels_file):
            find_common_pixels(missing_pixels_file, zero_hits_pixels_file, output_path)
        else:
            print(f"One or both files do not exist for chip {chip_id}. Skipping comparison.")

        # # ---- Inquiry a pixel's ToT and number of hit.
        # example_pixels = [(1, 428), (8, 430), (15, 431), (17, 431), (0, 400)]
        # print("Querying specific pixel information:")
        # for pixel_row, pixel_col in example_pixels:
        #     print_pixel_info(Data, ToTMapX, pixel_row, pixel_col)

if __name__ == "__main__":
    main()
