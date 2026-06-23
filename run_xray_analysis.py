import os
import argparse
import subprocess
import glob
import shutil
import sys

# Constants
BASE_DIR = "/home/tfpxxray/Ph2_ACF/Ph2_ACF/module_testing"
DOWNLOADS_DIR = "/home/tfpxxray/Downloads"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
XRAY_ANALYSIS_SCRIPT = os.path.join(SCRIPT_DIR, "xray_test.py")

def print_colored(message, color="green"):
    # Print colored messages to terminal
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "reset": "\033[0m"
    }
    print(f"{colors.get(color, colors['green'])}{message}{colors['reset']}")

def find_scurve_file(module_name, downloads_dir=DOWNLOADS_DIR):
    # Find the latest *SCurve*.root file in the Downloads directory.
    # The run number/name changes from module to module, so just take the
    # most recently modified SCurve file rather than matching on the name.
    scurve_files = glob.glob(os.path.join(downloads_dir, "*SCurve*.root"))

    if not scurve_files:
        print_colored("No *SCurve*.root files found in downloads directory", "yellow")
        return None

    # Sort by modification time to get the latest file
    latest_file = max(scurve_files, key=os.path.getmtime)
    print_colored(f"Found latest SCurve file: {latest_file}", "green")
    print_colored(f"File modification time: {os.path.getmtime(latest_file)}", "blue")
    return latest_file

def find_xray_noise_root(module_name):
    # Find the latest *NoiseScan*.root file produced by the noise scan.
    # The scan runs from the module's xray directory, so its output lands in
    # that folder (e.g. xray/Results/...). Search recursively to cover the
    # Results subfolder or any per-board subdirectory. The run number/name
    # changes per module, so just take the most recently modified file.
    xray_dir = os.path.join(BASE_DIR, module_name, "xray")

    if not os.path.exists(xray_dir):
        print_colored(f"xray directory not found: {xray_dir}", "red")
        return None

    noise_files = glob.glob(os.path.join(xray_dir, "**", "*NoiseScan*.root"), recursive=True)

    if not noise_files:
        print_colored(f"No *NoiseScan*.root files found under {xray_dir}", "yellow")
        return None

    latest_file = max(noise_files, key=os.path.getmtime)
    print_colored(f"Found latest NoiseScan file: {latest_file}", "green")
    return latest_file

def copy_txt_files_for_analysis(module_name, chip_type, output_dir):
    # Copy OUT.txt files to the current directory for analysis
    # Source directory with the OUT.txt files
    source_dir = os.path.join(BASE_DIR, "tuned_txt_files", module_name)
    
    if not os.path.exists(source_dir):
        print_colored(f"Source directory not found: {source_dir}", "red")
        return False
    
    # Find all OUT.txt files for this module
    file_pattern = f"CMSIT_RD53_{module_name}_0_*_OUT.txt"
    source_files = glob.glob(os.path.join(source_dir, file_pattern))
    
    if not source_files:
        print_colored(f"No OUT.txt files found in {source_dir}", "red")
        return False
    
    # Number of expected files
    expected_count = 4 if chip_type.lower() == "quad" else 2
    if len(source_files) != expected_count:
        print_colored(f"Warning: Found {len(source_files)} OUT.txt files, but expected {expected_count} for {chip_type} chip type", "yellow")
    
    # Copy files to the output directory
    for source_file in source_files:
        try:
            dest_file = os.path.join(output_dir, os.path.basename(source_file))
            shutil.copy2(source_file, dest_file)
            print_colored(f"Copied {os.path.basename(source_file)} to {output_dir}", "green")
        except Exception as e:
            print_colored(f"Error copying file {source_file}: {e}", "red")
            return False
    
    return True

def copy_scurve_root_for_analysis(scurve_file, output_dir):
    # Copy SCurve.root file to the current directory for analysis
    if not scurve_file:
        print_colored("No SCurve file provided", "red")
        return False
    
    try:
        dest_file = os.path.join(output_dir, os.path.basename(scurve_file))
        shutil.copy2(scurve_file, dest_file)
        print_colored(f"Copied SCurve file to {output_dir}", "green")
        return dest_file
    except Exception as e:
        print_colored(f"Error copying SCurve file: {e}", "red")
        return False

def run_xray_analysis(module_name, scurve_file, noise_file, bias, output_dir, chip_type, chip_ids=None):
    # Run the xray_test.py script with appropriate parameters"""
    if not os.path.exists(XRAY_ANALYSIS_SCRIPT):
        print_colored(f"X-ray analysis script not found: {XRAY_ANALYSIS_SCRIPT}", "red")
        return False
    
    # Default to all chips if not specified
    if not chip_ids:
        chip_ids = [12, 13, 14, 15]
    
    # Get the base name of SCurve and noise files without extension
    if scurve_file:
        scurve_base = os.path.splitext(os.path.basename(scurve_file))[0]
        # Copy the SCurve file to the output directory with the correct name
        try:
            new_scurve_path = os.path.join(output_dir, f"{scurve_base}.root")
            if not os.path.exists(new_scurve_path):
                shutil.copy2(scurve_file, new_scurve_path)
                print_colored(f"Copied SCurve file to {new_scurve_path}", "green")
        except Exception as e:
            print_colored(f"Error copying SCurve file: {e}", "red")
    else:
        print_colored("No SCurve file available. Using Run000000 as placeholder", "yellow")
        scurve_base = "Run000000"
    
    if noise_file:
        noise_base = os.path.splitext(os.path.basename(noise_file))[0]
        # Copy the noise file to the output directory with the correct name
        try:
            new_noise_path = os.path.join(output_dir, f"{noise_base}.root")
            if not os.path.exists(new_noise_path):
                shutil.copy2(noise_file, new_noise_path)
                print_colored(f"Copied NoiseScan file to {new_noise_path}", "green")
        except Exception as e:
            print_colored(f"Error copying NoiseScan file: {e}", "red")
    else:
        print_colored("No NoiseScan file available. Using Run000000 as placeholder", "yellow")
        noise_base = "Run000000"
    
    # Set up the command
    cmd = [
        sys.executable,  # Use the current Python interpreter
        XRAY_ANALYSIS_SCRIPT,
        "-scurve", scurve_base,
        "-noise", noise_base,
        "-outpath", "analysis_results",
        "-sensor", module_name,
        "-bias", str(bias),
        "-chiptype", chip_type.lower()
    ]
    
    # Create the xray analysis output directory if it doesn't exist
    analysis_results_dir = os.path.join(output_dir, "analysis_results")
    os.makedirs(analysis_results_dir, exist_ok=True)
    
    print_colored(f"Running X-ray analysis with command:", "blue")
    print_colored(" ".join(cmd), "blue")
    
    try:
        # Run the analysis script as a subprocess
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=output_dir,  # Run in the output directory
            universal_newlines=True
        )
        
        # Display output in real-time
        for line in process.stdout:
            print(line, end='')
        
        # Wait for the process to complete
        process.wait()
        
        if process.returncode != 0:
            stderr = process.stderr.read()
            print_colored(f"Error running X-ray analysis: {stderr}", "red")
            return False
        
        print_colored("X-ray analysis completed successfully", "green")
        return True
    except Exception as e:
        print_colored(f"Error running X-ray analysis: {e}", "red")
        return False

def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Run X-ray analysis on test results')
    parser.add_argument('--module', '-m', help='Module name (e.g., SH0058)', required=True)
    parser.add_argument('--thermal-cycle', '-t', help='Thermal cycle number', default='0')
    parser.add_argument('--chip-type', '-c', choices=['dual', 'quad'], help='Chip type (dual or quad)', required=True)
    parser.add_argument('--bias', '-b', help='Bias voltage (V)', type=float, default=80.0)
    parser.add_argument('--scurve-file', '-s', help='SCurve root file (optional, will search Downloads if not provided)')
    args = parser.parse_args()
    
    # Create output directory for analysis
    output_dir = os.path.join(BASE_DIR, args.module, "xray", f"ThermalCycle_{args.thermal_cycle}", "Analysis")
    os.makedirs(output_dir, exist_ok=True)
    print_colored(f"Analysis results will be saved to: {output_dir}", "blue")
    
    # 1. Copy the OUT.txt files to the output directory
    if not copy_txt_files_for_analysis(args.module, args.chip_type, output_dir):
        print_colored("Failed to copy OUT.txt files. Aborting.", "red")
        return
    
    # 2. Find or use provided SCurve file
    scurve_file = args.scurve_file
    if not scurve_file:
        scurve_file = find_scurve_file(args.module)
        if not scurve_file:
            print_colored("No SCurve file found. X-ray analysis might not work correctly.", "yellow")
    
    # 3. Find the noise root file
    noise_file = find_xray_noise_root(args.module)
    if not noise_file:
        print_colored("No NoiseScan.root file found. X-ray analysis might not work correctly.", "yellow")
    
    # 4. Run the X-ray analysis
    success = run_xray_analysis(
        module_name=args.module,
        scurve_file=scurve_file,
        noise_file=noise_file,
        bias=args.bias,
        output_dir=output_dir,
        chip_type=args.chip_type
    )
    
    if success:
        print_colored("=" * 50, "green")
        print_colored("X-ray analysis completed successfully", "green")
        print_colored(f"Results saved to: {output_dir}/analysis_results", "green")
        print_colored("=" * 50, "green")
    else:
        print_colored("X-ray analysis failed", "red")

if __name__ == "__main__":
    main()