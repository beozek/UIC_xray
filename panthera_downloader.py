#!/usr/bin/env python3

import os
import re
import sys
import shutil
import glob
import argparse

# Constants
BASE_DIR = "/home/tfpxxray/Desktop/Ph2_ACF/Ph2_ACF/module_testing"
DOWNLOADS_DIR = "/home/tfpxxray/Downloads"

def print_colored(message, color="green"):
    """Print colored messages to terminal"""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "reset": "\033[0m"
    }
    print(f"{colors.get(color, colors['green'])}{message}{colors['reset']}")

def copy_out_txt_files(module_name, chip_type):
    # Copy OUT.txt files from Downloads folder to the appropriate location
    try:
        # Source directory (Downloads)
        source_dir = DOWNLOADS_DIR
        
        # Target directory (create if it doesn't exist)
        target_dir = os.path.join(BASE_DIR, "xray_files/tuned_txt_files", module_name)
        os.makedirs(target_dir, exist_ok=True)
        
        # Expected file pattern in Downloads
        file_pattern = f"CMSIT_RD53_{module_name}_0_*_OUT.txt"
        
        # Find all matching files
        source_files = glob.glob(os.path.join(source_dir, file_pattern))
        
        if not source_files:
            print_colored(f"No files matching pattern '{file_pattern}' found in {source_dir}", "red")
            return False
        
        # Expected number of files based on chip type
        expected_count = 4 if chip_type.lower() == "quad" else 2
        
        # Warn if file count doesn't match expectation
        if len(source_files) != expected_count:
            print_colored(f"Warning: Found {len(source_files)} files, but expected {expected_count} for {chip_type} chip type.", "yellow")
        
        print_colored(f"Found {len(source_files)} OUT.txt files to copy", "blue")
        
        # Copy files without renaming
        copied_count = 0
        for source_file in source_files:
            file_name = os.path.basename(source_file)
            target_file = os.path.join(target_dir, file_name)
            
            # Copy the file
            shutil.copy2(source_file, target_file)
            print_colored(f"Copied {file_name}", "green")
            copied_count += 1
        
        if copied_count > 0:
            print_colored(f"Successfully copied {copied_count} files to {target_dir}", "green")
            return True
        else:
            print_colored("Failed to copy any files", "red")
            return False
    
    except Exception as e:
        print_colored(f"Error copying files: {e}", "red")
        return False

def main():
    # Main function to orchestrate the file copying process"""
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description='Copy calibration files from Downloads folder')
    parser.add_argument('--module', '-m', help='Module name (e.g., SH0058)')
    parser.add_argument('--chip-type', '-c', choices=['dual', 'quad'], help='Chip type (dual or quad)')
    args = parser.parse_args()
    
    # Get module name from command line or prompt
    if args.module:
        module_name = args.module
        print_colored(f"Using module name from command line: {module_name}", "blue")
    else:
        module_name = input("Enter the module name (e.g., SH0058): ").strip()
    
    if not module_name:
        print_colored("Module name cannot be empty!", "red")
        return
    
    # Get chip type from command line or prompt
    if args.chip_type:
        chip_type = args.chip_type
        print_colored(f"Using chip type from command line: {chip_type}", "blue")
    else:
        chip_type = input("Enter the chip type (dual or quad): ").strip().lower()
        while chip_type not in ["dual", "quad"]:
            print_colored("Invalid chip type. Please enter 'dual' or 'quad'.", "red")
            chip_type = input("Enter the chip type (dual or quad): ").strip().lower()
    
    # Copy the files
    if copy_out_txt_files(module_name, chip_type):
        print_colored("=" * 50, "blue")
        print_colored(f"All files copied for module {module_name}", "green")
        print_colored(f"Files saved to: {os.path.join(BASE_DIR, 'xray_files/tuned_txt_files', module_name)}", "green")
        print_colored("=" * 50, "blue")

if __name__ == "__main__":
    main()