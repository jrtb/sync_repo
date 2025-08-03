#!/bin/bash

# S3 Sync Tool - Path Alias Installation Script
# This script installs the s3-sync command to be available system-wide

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 S3 Sync Tool - Path Alias Installation${NC}"
echo "================================================"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_SCRIPT="$SCRIPT_DIR/s3-sync"

# Check if the sync script exists
if [ ! -f "$SYNC_SCRIPT" ]; then
    echo -e "${RED}❌ Error: s3-sync script not found at $SYNC_SCRIPT${NC}"
    exit 1
fi

# Make sure the sync script is executable
chmod +x "$SYNC_SCRIPT"

# Determine the shell configuration file to use
if [ -n "$ZSH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
    SHELL_NAME="zsh"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
    SHELL_NAME="bash"
else
    # Check what shell is actually being used
    CURRENT_SHELL=$(basename "$SHELL")
    if [ "$CURRENT_SHELL" = "zsh" ]; then
        SHELL_CONFIG="$HOME/.zshrc"
        SHELL_NAME="zsh"
    else
        SHELL_CONFIG="$HOME/.bashrc"
        SHELL_NAME="bash"
    fi
fi

# Check if the path is already in the shell config
if grep -q "$SCRIPT_DIR" "$SHELL_CONFIG" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Path alias already exists in $SHELL_CONFIG${NC}"
    echo -e "${BLUE}The s3-sync command should already be available.${NC}"
else
    # Add the path to the shell configuration
    echo "" >> "$SHELL_CONFIG"
    echo "# S3 Sync Tool - Path Alias" >> "$SHELL_CONFIG"
    echo "export PATH=\"$SCRIPT_DIR:\$PATH\"" >> "$SHELL_CONFIG"
    
    echo -e "${GREEN}✅ Added path alias to $SHELL_CONFIG${NC}"
fi

# Test the installation
echo -e "${BLUE}🧪 Testing installation...${NC}"

# Source the shell config to test immediately
if [ -f "$SHELL_CONFIG" ]; then
    source "$SHELL_CONFIG"
fi

# Test if the command is available
if command -v s3-sync >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Installation successful!${NC}"
    echo -e "${BLUE}You can now use 's3-sync' from any directory.${NC}"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  s3-sync --help                    # Show help"
    echo "  s3-sync --dry-run                 # Preview sync"
    echo "  s3-sync --local-path ./photos     # Sync specific directory"
    echo ""
    echo -e "${YELLOW}Note:${NC} You may need to restart your terminal or run 'source $SHELL_CONFIG' for the changes to take effect."
else
    echo -e "${RED}❌ Installation failed. Please check the setup.${NC}"
    echo -e "${YELLOW}You can still run the tool using:${NC}"
    echo "  $SYNC_SCRIPT --help"
fi 