#!/bin/bash

# S3 Sync Tool - Path Alias Uninstallation Script
# This script removes the s3-sync command from the system PATH

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🗑️  S3 Sync Tool - Path Alias Uninstallation${NC}"
echo "=================================================="

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Determine the shell configuration file to use
if [ -n "$ZSH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
    SHELL_NAME="zsh"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_CONFIG="$HOME/.bashrc"
    SHELL_NAME="bash"
else
    # Default to bash if we can't determine
    SHELL_CONFIG="$HOME/.bashrc"
    SHELL_NAME="bash"
fi

# Check if the path is in the shell config
if grep -q "$SCRIPT_DIR" "$SHELL_CONFIG" 2>/dev/null; then
    echo -e "${YELLOW}Found path alias in $SHELL_CONFIG${NC}"
    
    # Create a backup
    BACKUP_FILE="$SHELL_CONFIG.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$SHELL_CONFIG" "$BACKUP_FILE"
    echo -e "${BLUE}Created backup: $BACKUP_FILE${NC}"
    
    # Remove the lines containing the script directory
    # This removes the export line and the comment line
    sed -i.tmp "/# S3 Sync Tool - Path Alias/d" "$SHELL_CONFIG"
    sed -i.tmp "/export PATH.*$SCRIPT_DIR/d" "$SHELL_CONFIG"
    rm -f "$SHELL_CONFIG.tmp"
    
    echo -e "${GREEN}✅ Removed path alias from $SHELL_CONFIG${NC}"
    echo -e "${YELLOW}Note:${NC} You may need to restart your terminal for the changes to take effect."
else
    echo -e "${YELLOW}⚠️  No path alias found in $SHELL_CONFIG${NC}"
    echo -e "${BLUE}The s3-sync command was not installed via this method.${NC}"
fi

echo -e "${GREEN}✅ Uninstallation complete!${NC}" 