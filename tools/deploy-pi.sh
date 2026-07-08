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
    python3-evdev \
    libhidapi-libusb0

# ── DMX USB access ───────────────────────────────────────────────────────────
# The OLA container runs olad unprivileged (olad refuses to run as root), so the
# ENTTEC Open DMX USB (FTDI FT232, 0403:6001) must be world-accessible for the
# ftdidmx plugin to open it via libusb and detach the ftdi_sio kernel driver.
DMX_RULES_FILE="/etc/udev/rules.d/99-enttec-dmx.rules"
log "Installing udev rule for ENTTEC Open DMX USB..."
cat > "${DMX_RULES_FILE}" <<'EOF'
# ENTTEC Open DMX USB (FTDI FT232) — grant non-root access for OLA's ftdidmx plugin
SUBSYSTEM=="usb", ATTR{idVendor}=="0403", ATTR{idProduct}=="6001", MODE="0666"
EOF
udevadm control --reload-rules
udevadm trigger --subsystem-match=usb

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
"${VENV_DIR}/bin/pip" install "${INSTALL_DIR}" -q

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

# ── GitHub auto-update (systemd timer, every 1 min) ───────────────────────────
UPDATE_SCRIPT="/usr/local/bin/${SERVICE_NAME}-update"
UPDATE_SERVICE="/etc/systemd/system/${SERVICE_NAME}-update.service"
UPDATE_TIMER="/etc/systemd/system/${SERVICE_NAME}-update.timer"

log "Installing auto-update script: ${UPDATE_SCRIPT}..."
cat > "${UPDATE_SCRIPT}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR}"
BRANCH="${BRANCH}"
VENV_DIR="${VENV_DIR}"
SERVICE_NAME="${SERVICE_NAME}"

git -C "\${INSTALL_DIR}" fetch origin --quiet

LOCAL=\$(git -C "\${INSTALL_DIR}" rev-parse HEAD)
REMOTE=\$(git -C "\${INSTALL_DIR}" rev-parse "origin/\${BRANCH}")

[[ "\${LOCAL}" == "\${REMOTE}" ]] && exit 0

DEPS_CHANGED=false
if ! git -C "\${INSTALL_DIR}" diff --quiet "\${LOCAL}" "\${REMOTE}" -- pyproject.toml poetry.lock; then
    DEPS_CHANGED=true
fi

git -C "\${INSTALL_DIR}" reset --hard "origin/\${BRANCH}"

if [[ "\${DEPS_CHANGED}" == "true" ]]; then
    "\${VENV_DIR}/bin/pip" install "\${INSTALL_DIR}" -q
fi

systemctl restart "\${SERVICE_NAME}"
EOF
chmod +x "${UPDATE_SCRIPT}"

log "Installing auto-update systemd units..."
cat > "${UPDATE_SERVICE}" <<EOF
[Unit]
Description=Game Show Controller – GitHub auto-update
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=${UPDATE_SCRIPT}
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}-update
EOF

cat > "${UPDATE_TIMER}" <<EOF
[Unit]
Description=Poll GitHub for Game Show Controller updates every minute

[Timer]
OnBootSec=60
OnUnitActiveSec=60
Unit=${SERVICE_NAME}-update.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}-update.timer"
log "Auto-update timer active. Check with: systemctl list-timers ${SERVICE_NAME}-update.timer"

# ── OLA DMX container ─────────────────────────────────────────────────────────
# Runs olad (Open Lighting Architecture) in Docker to drive the ENTTEC Open DMX
# USB. `restart: unless-stopped` in the compose file + the enabled docker service
# bring it back on reboot, so no separate systemd unit is needed.
if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

log "Building and starting OLA container..."
docker compose -f "${INSTALL_DIR}/docker-compose.yml" up -d --build

# ── Done ───────────────────────────────────────────────────────────────────────
log "Deployment complete."
echo
systemctl status "${SERVICE_NAME}" --no-pager || true
echo
log "Follow logs with: journalctl -u ${SERVICE_NAME} -f"
log "Restart service:  sudo systemctl restart ${SERVICE_NAME}"
echo
log "OLA web UI:       http://\$(hostname -i | awk '{print \$1}'):9090"
log "OLA logs:         docker compose -f ${INSTALL_DIR}/docker-compose.yml logs -f"
log "Restart OLA:      docker compose -f ${INSTALL_DIR}/docker-compose.yml restart"
log "Stop service:     sudo systemctl stop ${SERVICE_NAME}"
log "Auto-update logs: journalctl -u ${SERVICE_NAME}-update -f"
log "Update now:       sudo ${UPDATE_SCRIPT}"
log "Timer status:     systemctl list-timers ${SERVICE_NAME}-update.timer"
