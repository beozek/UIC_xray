#!/bin/bash

# Paths
BASE_DIR="/home/tfpxxray/Ph2_ACF/Ph2_ACF"
MODULE_TESTING_DIR="${BASE_DIR}/module_testing"
PYTHON_SCRIPT="xray_test.py"
PANTHERA_SCRIPT="panthera_downloader.py"

# Use the full path to run_xray_analysis.py
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
XRAY_ANALYSIS_SCRIPT="${SCRIPT_DIR}/run_xray_analysis.py"
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
RESET="\033[0m"

echo -e "${GREEN}=== Starting the Ph2 ACF Automation Script ===${RESET}"

# Step 1: Prompt the user for module name, thermal cycle, and chip type
echo -e "${GREEN}Please provide the required module information. This is for PH2 ACF commands${RESET}"
read -p "Enter the module name: " MODULE_NAME
# read -p "Enter the thermal cycle number: " THERMAL_CYCLE
read -p "Enter the chip type (dual or quad): " CHIP_TYPE

# Validate chip type
while [[ ! "$CHIP_TYPE" =~ ^(dual|quad)$ ]]; do
    echo -e "${RED}Invalid chip type. Please enter 'dual' or 'quad'.${RESET}"
    read -p "Enter the chip type (dual or quad): " CHIP_TYPE
done

# For quad modules, ask for chip version
CHIP_VERSION="v2"
# if [[ "$CHIP_TYPE" == "quad" ]]; then
#     read -p "Enter the chip version (v1 or v2): " CHIP_VERSION
#     while [[ ! "$CHIP_VERSION" =~ ^(v1|v2)$ ]]; do
#         echo -e "${RED}Invalid chip version. Please enter 'v1' or 'v2'.${RESET}"
#         read -p "Enter the chip version (v1 or v2): " CHIP_VERSION
#     done
# fi

# Set bias voltage to 80V (always)
BIAS_VOLTAGE=80

echo "Module Name: $MODULE_NAME"
# echo "Thermal Cycle Number: $THERMAL_CYCLE"
echo "Chip Type: $CHIP_TYPE"
if [[ -n "$CHIP_VERSION" ]]; then
    echo "Chip Version: $CHIP_VERSION"
fi
echo "Bias Voltage: $BIAS_VOLTAGE V"

# Step 1.5: Ask if the user wants to copy files from Downloads
read -p "Do you want to copy calibration files from the Downloads folder? (y/n): " COPY_FROM_DOWNLOADS
if [[ "$COPY_FROM_DOWNLOADS" =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}=== Copying files from Downloads folder ===${RESET}"
    
    # Check if panthera_downloader.py exists
    if [ ! -f "$PANTHERA_SCRIPT" ]; then
        echo -e "${RED}Error: File copy script $PANTHERA_SCRIPT not found!${RESET}"
        echo -e "${YELLOW}Continuing without copying files from Downloads...${RESET}"
    else
        # Run the file copy script with the module name and chip type as arguments
        python "$PANTHERA_SCRIPT" --module "$MODULE_NAME" --chip-type "$CHIP_TYPE" || { 
            echo -e "${RED}Error: Copying files from Downloads failed!${RESET}"
            
            read -p "Do you want to continue without copying files? (y/n): " CONTINUE_WITHOUT_COPY
            if [[ ! "$CONTINUE_WITHOUT_COPY" =~ ^[Yy]$ ]]; then
                echo "Exiting..."
                exit 1
            fi
        }
        echo -e "${GREEN}Files copied successfully.${RESET}"
    fi
fi

# Step 2: (removed) The analysis script (xray_test.py) is NOT run here.
# Running it with no arguments made it fall back to its default -sensor (SH0054)
# and run before the noise scan even existed. The analysis is run later in
# Step 5 via run_xray_analysis.py, which passes the correct module name.

# Construct and create the per-module xray directory (no thermal cycle info)
XRAY_DIR="${MODULE_TESTING_DIR}/${MODULE_NAME}/xray"
echo "Constructed xray directory path: $XRAY_DIR"
mkdir -p "$XRAY_DIR" || { echo -e "${RED}Error: Failed to create $XRAY_DIR${RESET}"; exit 1; }
echo "xray directory ready. Proceeding..."

# Step 3: Source setup.sh
echo -e "${GREEN}Sourcing setup.sh to configure the environment...${RESET}"
cd "$BASE_DIR" || { echo "Error: Failed to navigate to $BASE_DIR"; exit 1; }
if [ ! -f "setup.sh" ]; then
    echo "Error: setup.sh not found in $BASE_DIR!"
    exit 1
fi
source setup.sh
echo -e "${GREEN}Environment setup completed.${RESET}"

# Navigate to the per-module xray directory
echo "Navigating to the xray directory: $XRAY_DIR"
cd "$XRAY_DIR" || { echo "Error: Failed to navigate to $XRAY_DIR"; exit 1; }

# Select the source XML for the chosen chip type (from the script/xray_area directory)
echo -e "${GREEN}Looking for the ${CHIP_TYPE} XML file...${RESET}"
SRC_XML="${SCRIPT_DIR}/CMSIT_xray_noise_CROC${CHIP_VERSION}_${CHIP_TYPE}.xml"
if [ ! -f "$SRC_XML" ]; then
    echo -e "${RED}Error: XML file $SRC_XML not found!${RESET}"
    exit 1
fi
echo "XML file found: $SRC_XML"

# Copy the XML into the per-module xray directory and work on that copy
# (keeps the source XML in xray_area unchanged)
XML_FILE="${XRAY_DIR}/$(basename "$SRC_XML")"
cp "$SRC_XML" "$XML_FILE" || { echo -e "${RED}Error: Failed to copy XML to $XRAY_DIR${RESET}"; exit 1; }
echo "Copied XML to: $XML_FILE"

# Copy the tuned _OUT.txt config files for this module into the xray directory
TUNED_DIR="${MODULE_TESTING_DIR}/tuned_txt_files/${MODULE_NAME}"
echo -e "${GREEN}Copying tuned config files from ${TUNED_DIR}...${RESET}"
if [ ! -d "$TUNED_DIR" ]; then
    echo -e "${RED}Error: Tuned config directory $TUNED_DIR not found!${RESET}"
    exit 1
fi
cp "${TUNED_DIR}/CMSIT_RD53_${MODULE_NAME}_0_"*_OUT.txt "$XRAY_DIR"/ || { echo -e "${RED}Error: Failed to copy tuned txt files${RESET}"; exit 1; }
echo "Copied tuned config files to: $XRAY_DIR"

# Point each per-chip configFile at the copied tuned _OUT.txt file in the xray directory
# (correct module name from the prompt, _OUT suffix). The chip number is preserved.
echo -e "${GREEN}Setting tuned config files in $(basename "$XML_FILE")...${RESET}"
sed -i -E "s|configFile=\"[^\"]*CMSIT_RD53_[A-Za-z0-9]+_0_([0-9]+)[^\"]*\.txt\"|configFile=\"${XRAY_DIR}/CMSIT_RD53_${MODULE_NAME}_0_\1_OUT.txt\"|g" "$XML_FILE"

# Modify GTX RX polarity in XML file based on module name
# if [[ "$CHIP_TYPE" == "quad" && "$CHIP_VERSION" == "v2" ]]; then
#     echo -e "${GREEN}Checking if GTX RX polarity needs to be modified...${RESET}"
    
#     # Set gtx_rx_polarity based on module name
#     if [[ "$MODULE_NAME" == SH01* ]]; then
#         echo -e "${GREEN}Module $MODULE_NAME starts with SH01, setting gtx_rx_polarity fmc_l12 to 0b1001${RESET}"
#         NEW_POLARITY="0b1001"
#     elif [[ "$MODULE_NAME" == SH00* ]]; then
#         echo -e "${GREEN}Module $MODULE_NAME starts with SH00, setting gtx_rx_polarity fmc_l12 to 0b1101${RESET}"
#         NEW_POLARITY="0b1101"
#     else
#         echo -e "${YELLOW}Module $MODULE_NAME does not start with SH00 or SH01. Not modifying XML.${RESET}"
#     fi
    
#     # Update the XML file if NEW_POLARITY is set
#     if [[ -n "$NEW_POLARITY" ]]; then
#         # Create a backup of the original file
#         cp "$XML_FILE" "${XML_FILE}.bak"
        
#         # Use sed to replace the gtx_rx_polarity value
#         sed -i "s/<Register name=\"fmc_l12\">0b[01]\{4\}<\/Register>/<Register name=\"fmc_l12\">$NEW_POLARITY<\/Register>/g" "$XML_FILE"
        
#         echo -e "${GREEN}Updated gtx_rx_polarity in $XML_FILE${RESET}"
#     fi
# else
#     echo -e "${YELLOW}Not a quad v2 module. No need to modify GTX RX polarity.${RESET}"
# fi

# Step 4: Run Ph2 ACF commands
echo -e "${GREEN}=== Running Ph2 ACF Commands ===${RESET}"

echo "1. Running fpgaconfig to upload the firmware..."
fpgaconfig -c "$XML_FILE" -i QUAD_ELE_CROC_v5-0.bit || { echo "Error: fpgaconfig failed"; exit 1; }
echo "Firmware uploaded successfully."

echo "2. Running CMSITminiDAQ for resetting..."
CMSITminiDAQ -f "$XML_FILE" -r || { echo "Error: CMSITminiDAQ reset failed"; exit 1; }
echo "CMSITminiDAQ reset completed successfully."

echo "3. Running CMSITminiDAQ for noise scan..."
CMSITminiDAQ -f "$XML_FILE" -c noise || { echo "Error: CMSITminiDAQ noise scan failed"; exit 1; }
echo "CMSITminiDAQ noise scan completed successfully."

echo -e "${GREEN}=== All commands executed successfully! === ${RESET}"

# Step 5: Ask if the user wants to run X-ray analysis
read -p "Do you want to run the X-ray analysis now? (y/n): " RUN_XRAY_ANALYSIS
if [[ "$RUN_XRAY_ANALYSIS" =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}=== Running X-ray Analysis ===${RESET}"
    
    # Check if the analysis script exists
    if [ ! -f "$XRAY_ANALYSIS_SCRIPT" ]; then
        echo -e "${RED}Error: X-ray analysis script $XRAY_ANALYSIS_SCRIPT not found!${RESET}"
        echo -e "${YELLOW}Skipping X-ray analysis...${RESET}"
    else
        # Navigate back to the script directory
        cd "$SCRIPT_DIR" || { echo "Error: Failed to navigate to script directory"; exit 1; }
        
        # Run the analysis script
        python "$XRAY_ANALYSIS_SCRIPT" \
            --module "$MODULE_NAME" \
            --chip-type "$CHIP_TYPE" \
            --bias "$BIAS_VOLTAGE" || {
            echo -e "${RED}Error: X-ray analysis failed!${RESET}"
        }
    fi
else
    echo -e "${YELLOW}Skipping X-ray analysis. You can run it later using:${RESET}"
    echo -e "${YELLOW}python $XRAY_ANALYSIS_SCRIPT --module $MODULE_NAME --chip-type $CHIP_TYPE --bias $BIAS_VOLTAGE${RESET}"
    echo -e "${GREEN}Note: The analysis script will automatically find the latest SCurve.root file in your Downloads folder.${RESET}"
fi

echo -e "${GREEN}=== Workflow completed! === ${RESET}"