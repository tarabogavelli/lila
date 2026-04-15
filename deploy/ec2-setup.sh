#!/bin/bash
set -e

echo "=== Lila EC2 Setup ==="
echo ""

REPO_URL="${1:-}"
if [ -z "$REPO_URL" ]; then
    echo "Usage: bash ec2-setup.sh <git-repo-url>"
    echo "Example: bash ec2-setup.sh https://github.com/youruser/lila.git"
    exit 1
fi

echo "Step 1: Installing system dependencies..."
sudo dnf update -y
sudo dnf install -y python3.12 python3.12-pip git

echo ""
echo "Step 2: Cloning repository..."
cd /home/ec2-user
if [ -d "lila" ]; then
    echo "  lila/ already exists, pulling latest..."
    cd lila && git pull origin main && cd ..
else
    git clone "$REPO_URL" lila
fi

echo ""
echo "Step 3: Creating Python virtual environment..."
cd /home/ec2-user/lila/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Step 4: Setting up environment file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env from .env.example"
    echo "  *** You MUST edit .env and fill in your API keys ***"
    echo "  Run: nano /home/ec2-user/lila/backend/.env"
else
    echo "  .env already exists, skipping"
fi

echo ""
echo "Step 5: Installing systemd services..."
sudo cp /home/ec2-user/lila/deploy/lila-api.service /etc/systemd/system/
sudo cp /home/ec2-user/lila/deploy/lila-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lila-api lila-agent

echo ""
echo "Step 6: Opening port 8000..."
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit your API keys:  nano /home/ec2-user/lila/backend/.env"
echo "  2. Copy PDFs to:        /home/ec2-user/lila/backend/data/"
echo "  3. Run RAG ingestion:   cd /home/ec2-user/lila/backend && source .venv/bin/activate && python -m rag.ingest"
echo "  4. Start services:      sudo systemctl start lila-api lila-agent"
echo "  5. Check status:        sudo systemctl status lila-api lila-agent"
echo "  6. View logs:           journalctl -u lila-api -f"
echo "                          journalctl -u lila-agent -f"
