#!/bin/bash
# deploy.sh — One-shot VPS deployment script
# Run once on your Ubuntu 22.04 VPS as a non-root user
# Usage: chmod +x deploy.sh && ./deploy.sh

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  RCMaaS Deployment Script"
echo "  Immigration Compliance Daily"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. System deps
echo "[1/7] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y python3.11 python3.11-venv python3-pip git -qq

# 2. Project directory
echo "[2/7] Setting up project directory..."
PROJECT_DIR="$HOME/rcmaas"
mkdir -p "$PROJECT_DIR/data" "$PROJECT_DIR/logs"
cd "$PROJECT_DIR"

# 3. Python venv
echo "[3/7] Creating Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "     ✓ Dependencies installed"

# 4. .env setup
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  .env file created from template."
    echo "    Edit it now: nano $PROJECT_DIR/.env"
    echo "    Then re-run this script."
    exit 0
fi
echo "[4/7] .env file found ✓"

# 5. Test pipeline (dry run)
echo "[5/7] Running dry-run test..."
DRY_RUN=true python pipeline.py
echo "     ✓ Dry run passed"

# 6. systemd service
echo "[6/7] Installing systemd service..."
SERVICE_NAME="rcmaas"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=RCMaaS - Immigration Compliance Daily
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/pipeline.py --schedule
Restart=on-failure
RestartSec=60
StandardOutput=append:$PROJECT_DIR/logs/service.log
StandardError=append:$PROJECT_DIR/logs/service.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"
echo "     ✓ Service installed and started"

# 7. Status
echo "[7/7] Checking service status..."
sudo systemctl status "$SERVICE_NAME" --no-pager -l

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ DEPLOYMENT COMPLETE"
echo ""
echo "  Commands:"
echo "  • Check logs:    tail -f $PROJECT_DIR/logs/rcmaas.log"
echo "  • Service status: sudo systemctl status rcmaas"
echo "  • Restart:        sudo systemctl restart rcmaas"
echo "  • Run now:        cd $PROJECT_DIR && source venv/bin/activate && python pipeline.py"
echo ""
echo "  Next: Set DRY_RUN=false in .env when ready to go live."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
