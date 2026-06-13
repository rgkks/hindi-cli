#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ╔═══════════════════════════════════════════════╗"
echo "  ║          hindi-cli - Installation             ║"
echo "  ╚═══════════════════════════════════════════════╝"
echo -e "${NC}"

detect_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *)          echo "unknown";;
    esac
}

OS=$(detect_os)
echo -e "${BLUE}Detected OS: ${OS}${NC}"

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $1 found"
        return 0
    else
        echo -e "  ${RED}✗${NC} $1 not found"
        return 1
    fi
}

INSTALL_PYTHON=false
INSTALL_MPV=false
INSTALL_FZF=false
INSTALL_YTDLP=false

echo ""
echo -e "${YELLOW}Checking dependencies...${NC}"

if ! check_command "python3"; then
    if ! check_command "python"; then
        INSTALL_PYTHON=true
    fi
fi

check_command "mpv" || INSTALL_MPV=true
check_command "fzf" || INSTALL_FZF=true
check_command "yt-dlp" || INSTALL_YTDLP=true

PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

if [ "$INSTALL_PYTHON" = true ]; then
    echo ""
    echo -e "${YELLOW}Python not found. Please install Python 3.8+:${NC}"
    echo "  Linux:  sudo apt install python3 python3-pip"
    echo "  macOS:  brew install python"
    echo "  Windows: https://python.org/downloads/"
fi

if [ "$INSTALL_MPV" = true ]; then
    echo ""
    echo -e "${YELLOW}Installing mpv...${NC}"
    case "$OS" in
        linux)
            if command -v apt &> /dev/null; then
                sudo apt update && sudo apt install -y mpv
            elif command -v pacman &> /dev/null; then
                sudo pacman -S mpv
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y mpv
            else
                echo "Please install mpv manually: https://mpv.io/installation/"
            fi
            ;;
        macos)
            if command -v brew &> /dev/null; then
                brew install mpv
            else
                echo "Please install mpv manually: https://mpv.io/installation/"
            fi
            ;;
        *)
            echo "Please install mpv manually: https://mpv.io/installation/"
            ;;
    esac
fi

if [ "$INSTALL_FZF" = true ]; then
    echo ""
    echo -e "${YELLOW}Installing fzf...${NC}"
    case "$OS" in
        linux)
            if command -v apt &> /dev/null; then
                sudo apt update && sudo apt install -y fzf
            elif command -v pacman &> /dev/null; then
                sudo pacman -S fzf
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y fzf
            else
                git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf
                ~/.fzf/install
            fi
            ;;
        macos)
            if command -v brew &> /dev/null; then
                brew install fzf
            else
                git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf
                ~/.fzf/install
            fi
            ;;
        windows)
            echo "Please install fzf manually: https://github.com/junegunn/fzf#installation"
            ;;
    esac
fi

echo ""
echo -e "${YELLOW}Installing Python dependencies...${NC}"
"$PYTHON_CMD" -m pip install --upgrade pip --break-system-packages
"$PYTHON_CMD" -m pip install --break-system-packages -r requirements.txt

echo ""
echo -e "${YELLOW}Installing hindi-cli...${NC}"
"$PYTHON_CMD" -m pip install --break-system-packages -e .

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          hindi-cli installed!                  ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Run ${CYAN}hindi-cli${NC} to start streaming!"
echo ""
