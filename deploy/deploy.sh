#!/bin/bash
set -e

echo "=== Deploying latest Lila code ==="

cd /home/ec2-user/lila

echo "Pulling latest code..."
git pull origin main

echo "Updating Python dependencies..."
cd backend
source .venv/bin/activate
pip install -r requirements.txt

echo "Restarting services..."
sudo systemctl restart lila-api lila-agent

echo ""
echo "=== Deploy complete ==="
sudo systemctl status lila-api lila-agent --no-pager
