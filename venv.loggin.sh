#!/bin/bash

# =============================================================================
# L4D2 Iptables Suite - Virtual Environment Manager
# =============================================================================
# Script to manage virtual environment for iptable.loggin.py
# Functions: install, activate, deactivate, verify dependencies
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Global variables
VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"
PYTHON_SCRIPT="iptable.loggin.py"

# Function to display colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_header() {
    echo -e "${CYAN}$1${NC}"
}

# Function to detect operating system
detect_os() {
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ -n "$WINDIR" ]]; then
        echo "windows"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    else
        echo "unix"  # Default fallback
    fi
}

# Function to get virtual environment activation script path
get_venv_activate_path() {
    local os_type=$(detect_os)
    
    if [[ "$os_type" == "windows" ]]; then
        echo "$VENV_DIR/Scripts/activate"
    else
        echo "$VENV_DIR/bin/activate"
    fi
}

# Function to get Python executable path in venv
get_venv_python_path() {
    local os_type=$(detect_os)
    
    if [[ "$os_type" == "windows" ]]; then
        echo "$VENV_DIR/Scripts/python.exe"
    else
        echo "$VENV_DIR/bin/python"
    fi
}

# Function to run the Python script with proper environment
run_python_script() {
    print_header "=== RUNNING IPTABLE.LOGGIN.PY ==="
    
    # Check if virtual environment exists
    if ! check_venv_exists; then
        print_error "Virtual environment does not exist"
        print_info "Use option 1 to install it first"
        return 1
    fi
    
    # Check if script file exists
    if [[ ! -f "$PYTHON_SCRIPT" ]]; then
        print_error "$PYTHON_SCRIPT not found in current directory"
        return 1
    fi
    
    # Check if .env file exists
    if [[ ! -f ".env" ]]; then
        print_warning ".env file not found"
        print_info "The script may not work properly without configuration"
        echo -n "Do you want to continue anyway? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            print_info "Execution cancelled"
            return 0
        fi
    fi
    
    local python_path=$(get_venv_python_path)
    local full_python_path="$(pwd)/$python_path"
    local os_type=$(detect_os)
    
    print_info "Preparing to run $PYTHON_SCRIPT..."
    echo ""
    
    # Different execution based on OS
    if [[ "$os_type" == "windows" ]]; then
        print_info "Windows detected - Running without sudo:"
        print_success "Command: $full_python_path $PYTHON_SCRIPT --env-file .env"
        echo ""
        "$full_python_path" "$PYTHON_SCRIPT" --env-file .env
    else
        print_info "Linux/Unix detected - Root privileges required for log access"
        print_success "Command: sudo $full_python_path $PYTHON_SCRIPT --env-file .env"
        echo ""
        print_warning "You may be prompted for your sudo password..."
        echo ""
        sudo "$full_python_path" "$PYTHON_SCRIPT" --env-file .env
    fi
    
    local exit_code=$?
    echo ""
    
    if [[ $exit_code -eq 0 ]]; then
        print_success "Script executed successfully"
    else
        print_error "Script execution failed (exit code: $exit_code)"
        print_info "Check the error messages above for troubleshooting"
    fi
    
    return $exit_code
}

# Function to check if we are in the virtual environment
check_venv_active() {
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        return 0  # Active
    else
        return 1  # Not active
    fi
}

# Function to check if the virtual environment exists
check_venv_exists() {
    local activate_path=$(get_venv_activate_path)
    
    if [[ -d "$VENV_DIR" && -f "$activate_path" ]]; then
        return 0  # Exists
    else
        return 1  # Does not exist
    fi
}

# Function to verify Python script dependencies
check_python_dependencies() {
    local required_modules=("pandas" "dotenv")
    local missing_modules=()
    
    print_info "Verifying dependencies for $PYTHON_SCRIPT..."
    
    for module in "${required_modules[@]}"; do
        if [[ "$module" == "dotenv" ]]; then
            # python-dotenv is imported as 'dotenv'
            python -c "from dotenv import load_dotenv" 2>/dev/null
        else
            python -c "import $module" 2>/dev/null
        fi
        
        if [[ $? -ne 0 ]]; then
            missing_modules+=("$module")
        fi
    done
    
    if [[ ${#missing_modules[@]} -eq 0 ]]; then
        print_success "All dependencies are installed"
        
        # Show versions
        echo ""
        print_info "Installed versions:"
        python -c "import pandas as pd; print(f'  • pandas: {pd.__version__}')" 2>/dev/null
        python -c "from dotenv import __version__; print(f'  • python-dotenv: {__version__}')" 2>/dev/null || echo "  • python-dotenv: installed"
        return 0
    else
        print_error "Missing the following dependencies:"
        for module in "${missing_modules[@]}"; do
            if [[ "$module" == "dotenv" ]]; then
                echo "  • python-dotenv"
            else
                echo "  • $module"
            fi
        done
        return 1
    fi
}

# Function to install the virtual environment
install_venv() {
    print_header "=== INSTALLING VIRTUAL ENVIRONMENT ==="
    
    if check_venv_exists; then
        print_warning "Virtual environment already exists in '$VENV_DIR'"
        echo -n "Do you want to reinstall it? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            print_info "Installation cancelled"
            return 0
        fi
        print_info "Removing existing virtual environment..."
        rm -rf "$VENV_DIR"
    fi
    
    # Verify that Python is available
    if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
        print_error "Python is not installed or not in PATH"
        return 1
    fi
    
    # Use python3 if available, otherwise python
    local python_cmd="python3"
    if ! command -v python3 &> /dev/null; then
        python_cmd="python"
    fi
    
    print_info "Creating virtual environment with $python_cmd..."
    $python_cmd -m venv "$VENV_DIR"
    
    if [[ $? -ne 0 ]]; then
        print_error "Error creating virtual environment"
        return 1
    fi
    
    print_success "Virtual environment created successfully"
    
    # Activate the virtual environment
    local activate_path=$(get_venv_activate_path)
    source "$activate_path"
    
    if [[ $? -ne 0 ]]; then
        print_error "Could not activate virtual environment"
        return 1
    fi
    
    # Update pip
    print_info "Updating pip..."
    pip install --upgrade pip > /dev/null 2>&1
    
    # Install dependencies
    if [[ -f "$REQUIREMENTS_FILE" ]]; then
        print_info "Installing dependencies from $REQUIREMENTS_FILE..."
        pip install -r "$REQUIREMENTS_FILE"
        
        if [[ $? -eq 0 ]]; then
            print_success "Dependencies installed correctly"
        else
            print_error "Error installing dependencies"
            return 1
        fi
    else
        print_warning "$REQUIREMENTS_FILE file not found"
        print_info "Installing dependencies manually..."
        pip install pandas python-dotenv
        
        if [[ $? -eq 0 ]]; then
            print_success "Dependencies installed correctly"
        else
            print_error "Error installing dependencies"
            return 1
        fi
    fi
    
    # Verify installation
    check_python_dependencies
    
    print_success "Virtual environment installed and configured completely"
}

# Function to activate the virtual environment
activate_venv() {
    if check_venv_active; then
        print_warning "Virtual environment is already active"
        return 0
    fi
    
    if ! check_venv_exists; then
        print_error "Virtual environment does not exist"
        print_info "Use option 1 to install it first"
        return 1
    fi
    
    print_info "Activating virtual environment..."
    
    # Activate the virtual environment
    local activate_path=$(get_venv_activate_path)
    source "$activate_path"
    
    if [[ $? -ne 0 ]]; then
        print_error "Could not activate virtual environment"
        return 1
    fi
    
    if check_venv_active; then
        print_success "Virtual environment activated: $(basename $VIRTUAL_ENV)"
        
        # Verify dependencies
        echo ""
        check_python_dependencies
        
        echo ""
        print_info "To deactivate the virtual environment, use: deactivate"
        print_info "Or use option 3 from the menu"
        
        # Switch to interactive shell with active environment
        echo ""
        print_header "=== INTERACTIVE SHELL ACTIVE ==="
        print_info "Virtual environment active. Available commands:"
        echo "  • python $PYTHON_SCRIPT --env-file .env  (direct execution)"
        echo "  • Use option 6 from menu to run with proper sudo handling"
        echo "  • python test_environment.py"
        echo "  • deactivate (to exit the environment)"
        echo "  • exit (to close the shell)"
        echo ""
        
        # Execute an interactive shell
        exec bash
    else
        print_error "Error activating virtual environment"
        return 1
    fi
}

# Function to deactivate the virtual environment
deactivate_venv() {
    if ! check_venv_active; then
        print_warning "Virtual environment is not active"
        return 0
    fi
    
    print_info "Deactivating virtual environment..."
    deactivate 2>/dev/null || true
    
    if ! check_venv_active; then
        print_success "Virtual environment deactivated"
    else
        print_warning "Virtual environment is still active"
        print_info "You can use 'deactivate' manually"
    fi
}

# Function to check the environment status
check_venv_status() {
    print_header "=== VIRTUAL ENVIRONMENT STATUS ==="
    
    # Check if it exists
    if check_venv_exists; then
        print_success "Virtual environment exists in: $VENV_DIR"
    else
        print_error "Virtual environment does NOT exist"
        print_info "Use option 1 to install it"
        return 1
    fi
    
    # Check if it's active
    if check_venv_active; then
        print_success "Virtual environment ACTIVE: $(basename $VIRTUAL_ENV)"
    else
        print_warning "Virtual environment is NOT active"
    fi
    
    # Check Python
    local python_path=$(get_venv_python_path)
    if check_venv_active || [[ -f "$python_path" ]]; then
        echo ""
        print_info "Python information:"
        if check_venv_active; then
            python --version
            echo "  Executable: $(which python)"
        else
            "$python_path" --version 2>/dev/null || echo "  Python version: Not available"
            echo "  Executable: $(pwd)/$python_path"
        fi
    fi
    
    # Check dependencies
    echo ""
    if check_venv_active; then
        check_python_dependencies
    else
        print_info "Temporarily activating to verify dependencies..."
        local activate_path=$(get_venv_activate_path)
        source "$activate_path"
        check_python_dependencies
        deactivate 2>/dev/null || true
    fi
    
    # Check required files
    echo ""
    print_info "Project files:"
    if [[ -f "$PYTHON_SCRIPT" ]]; then
        print_success "$PYTHON_SCRIPT found"
    else
        print_error "$PYTHON_SCRIPT NOT found"
    fi
    
    if [[ -f ".env" ]]; then
        print_success ".env file found"
    else
        print_warning ".env file NOT found"
    fi
    
    if [[ -f "$REQUIREMENTS_FILE" ]]; then
        print_success "$REQUIREMENTS_FILE found"
    else
        print_warning "$REQUIREMENTS_FILE NOT found"
    fi
}

# Function to reinstall dependencies
reinstall_dependencies() {
    print_header "=== REINSTALLING DEPENDENCIES ==="
    
    if ! check_venv_exists; then
        print_error "Virtual environment does not exist"
        print_info "Use option 1 to install it first"
        return 1
    fi
    
    # Activate if not active
    local was_active=false
    if check_venv_active; then
        was_active=true
    else
        local activate_path=$(get_venv_activate_path)
        source "$activate_path"
    fi
    
    print_info "Reinstalling dependencies..."
    
    if [[ -f "$REQUIREMENTS_FILE" ]]; then
        pip install --force-reinstall -r "$REQUIREMENTS_FILE"
    else
        pip install --force-reinstall pandas python-dotenv
    fi
    
    if [[ $? -eq 0 ]]; then
        print_success "Dependencies reinstalled correctly"
        echo ""
        check_python_dependencies
    else
        print_error "Error reinstalling dependencies"
    fi
    
    # Deactivate if it wasn't active before
    if [[ "$was_active" == false ]]; then
        deactivate 2>/dev/null || true
    fi
}

# Function to show help
show_help() {
    print_header "=== HELP - VIRTUAL ENVIRONMENT MANAGER ==="
    echo ""
    echo "This script manages the virtual environment for iptable.loggin.py"
    echo ""
    echo "Available functions:"
    echo "  1. Install virtual environment - Creates venv and installs dependencies"
    echo "  2. Activate virtual environment - Activates venv and opens interactive shell"
    echo "  3. Deactivate environment       - Deactivates current venv"
    echo "  4. Check status                 - Shows complete environment information"
    echo "  5. Reinstall dependencies       - Forces library reinstallation"
    echo "  6. Run iptable.loggin.py script - Executes the main script with proper environment"
    echo "  7. Help                         - Shows this information"
    echo "  8. Exit                         - Closes the script"
    echo ""
    echo "Required dependencies:"
    echo "  • pandas >= 1.3.0          - Data analysis"
    echo "  • python-dotenv >= 0.19.0  - Environment variables"
    echo ""
    echo "Required files:"
    echo "  • iptable.loggin.py         - Main script"
    echo "  • .env                      - Configuration"
    echo "  • requirements.txt          - Dependencies list (optional)"
    echo ""
    echo "Main script usage:"
    echo "  Use option 6 to run the script with proper environment handling"
    echo ""
    echo "Manual execution:"
    echo "  Linux/Debian: sudo /full/path/to/venv/bin/python iptable.loggin.py --env-file .env"
    echo ""
    echo "Why sudo is needed (Linux only):"
    echo "  • iptable.loggin.py requires root access to read system logs"
    echo "  • rsyslog configuration requires root privileges"
    echo "  • Log files in /var/log/ need root access"
    echo ""
}

# Function to show the main menu
show_menu() {
    clear
    print_header "======================================================"
    print_header "    L4D2 Iptables Suite - Virtual Environment Manager"
    print_header "======================================================"
    echo ""
    
    # Show system information
    local os_type=$(detect_os)
    case $os_type in
        "windows")
            print_info "System: Windows (using $(basename $SHELL))"
            ;;
        "linux")
            print_info "System: Linux/Debian"
            ;;
        "macos")
            print_info "System: macOS"
            ;;
        *)
            print_info "System: Unix-like"
            ;;
    esac
    
    # Show current status
    if check_venv_exists; then
        if check_venv_active; then
            print_success "Status: Virtual environment ACTIVE"
        else
            print_warning "Status: Virtual environment installed but NOT active"
        fi
    else
        print_error "Status: Virtual environment NOT installed"
    fi
    
    echo ""
    echo "Available options:"
    echo ""
    echo "  1. 🔧 Install virtual environment"
    echo "  2. ▶️  Activate virtual environment"
    echo "  3. ⏹️  Deactivate virtual environment"
    echo "  4. 📊 Check environment status"
    echo "  5. 🔄 Reinstall dependencies"
    echo "  6. 🐍 Run iptable.loggin.py script"
    echo "  7. ❓ Help"
    echo "  8. 🚪 Exit"
    echo ""
    echo -n "Select an option [1-8]: "
}

# Main function
main() {
    # Verify we are in the correct directory
    if [[ ! -f "$PYTHON_SCRIPT" ]]; then
        print_error "$PYTHON_SCRIPT script not found in current directory"
        print_info "Make sure to run this script from the project directory"
        exit 1
    fi
    
    while true; do
        show_menu
        read -r choice
        
        case $choice in
            1)
                echo ""
                install_venv
                echo ""
                echo -n "Press Enter to continue..."
                read -r
                ;;
            2)
                echo ""
                activate_venv
                # If we get here, it's because the interactive shell was closed
                ;;
            3)
                echo ""
                deactivate_venv
                echo ""
                echo -n "Press Enter to continue..."
                read -r
                ;;
            4)
                echo ""
                check_venv_status
                echo ""
                echo -n "Press Enter to continue..."
                read -r
                ;;
            5)
                echo ""
                reinstall_dependencies
                echo ""
                echo -n "Press Enter to continue..."
                read -r
                ;;
            6)
                echo ""
                run_python_script
                echo ""
                echo -n "Press Enter to continue..."
                read -r
                ;;
            7)
                echo ""
                show_help
                echo ""
                echo -n "Press Enter to continue..."
                read -r
                ;;
            8)
                echo ""
                print_info "Exiting virtual environment manager..."
                if check_venv_active; then
                    print_warning "Virtual environment is still active"
                    print_info "Use 'deactivate' to deactivate it if necessary"
                fi
                echo ""
                exit 0
                ;;
            *)
                echo ""
                print_error "Invalid option. Select a number from 1 to 8."
                echo ""
                echo -n "Press Enter to continue..."
                read -r
                ;;
        esac
    done
}

# Verify the script is executed with bash
if [[ -z "$BASH_VERSION" ]]; then
    echo "❌ This script must be executed with bash"
    exit 1
fi

# Execute main function
main "$@"
