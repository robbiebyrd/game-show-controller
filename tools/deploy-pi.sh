#!/usr/bin/env bash
# Deploys game-show-controller on a Raspberry Pi as a systemd service.
# Usage: sudo ./deploy-pi.sh
set -euo pipefail

REPO_URL="https://github.com/robbiebyrd/game-show-controller.git"
BRANCH="main"
INSTALL_DIR="/opt/gameshow"
SERVICE_NAME="gameshow"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
VENV_DIR="${INSTALL_DIR}/.venv"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
die()  { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run as root: sudo $0"

# ── System packages ────────────────────────────────────────────────────────────
log "Updating package lists..."
apt-get update -qq

log "Installing system prerequisites..."
apt-get install -y \
    git \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libsdl2-dev \
    libsdl2-mixer-dev \
    libsdl2-image-dev \
    libsdl2-ttf-dev \
    libasound2-dev \
    python3-xlib \
    python3-evdev

# ── Repository ─────────────────────────────────────────────────────────────────
if [[ -d "${INSTALL_DIR}/.git" ]]; then
    log "Updating existing install to branch '${BRANCH}'..."
    git -C "${INSTALL_DIR}" fetch origin
    git -C "${INSTALL_DIR}" checkout "${BRANCH}"
    git -C "${INSTALL_DIR}" reset --hard "origin/${BRANCH}"
else
    log "Cloning ${REPO_URL} (branch: ${BRANCH}) into ${INSTALL_DIR}..."
    git clone --branch "${BRANCH}" "${REPO_URL}" "${INSTALL_DIR}"
fi

# ── Python environment ─────────────────────────────────────────────────────────
log "Creating Python virtual environment..."
python3 -m venv "${VENV_DIR}"

log "Installing Python dependencies..."
"${VENV_DIR}/bin/pip" install --upgrade pip -q
"${VENV_DIR}/bin/pip" install -r "${INSTALL_DIR}/requirements.txt" -q

# ── systemd service ────────────────────────────────────────────────────────────
log "Installing systemd service: ${SERVICE_NAME}..."
cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Game Show Controller
After=network.target sound.target
Wants=sound.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
# pynput on headless Linux: keyboard uses uinput (needs root + dumpkeys), mouse uses dummy
Environment=PYNPUT_BACKEND_KEYBOARD=uinput
Environment=PYNPUT_BACKEND_MOUSE=dummy
ExecStart=${VENV_DIR}/bin/python main.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

# ── Done ───────────────────────────────────────────────────────────────────────
log "Deployment complete."
echo
systemctl status "${SERVICE_NAME}" --no-pager || true
echo
log "Follow logs with: journalctl -u ${SERVICE_NAME} -f"
log "Restart service:  sudo systemctl restart ${SERVICE_NAME}"
log "Stop service:     sudo systemctl stop ${SERVICE_NAME}"
