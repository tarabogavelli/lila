#!/bin/bash
set -e

echo "=== Setting up Cloudflare Quick Tunnel ==="
echo ""

echo "Step 1: Installing cloudflared..."
curl -fsSL https://pkg.cloudflare.com/cloudflared-ascii.repo | sudo tee /etc/yum.repos.d/cloudflared.repo
sudo dnf install -y cloudflared

echo ""
echo "Step 2: Starting quick tunnel..."
echo "  The tunnel URL will be saved to /tmp/cloudflared.log"
echo ""

nohup cloudflared tunnel --url http://localhost:8000 > /tmp/cloudflared.log 2>&1 &

sleep 5

TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/cloudflared.log | head -1)

if [ -z "$TUNNEL_URL" ]; then
    echo "Waiting a few more seconds for tunnel..."
    sleep 5
    TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/cloudflared.log | head -1)
fi

echo ""
echo "=== Setup complete ==="
echo ""
if [ -n "$TUNNEL_URL" ]; then
    echo "Your backend is available at:"
    echo "  $TUNNEL_URL"
    echo ""
    echo "Update your Vercel environment variable:"
    echo "  VITE_API_BASE_URL = $TUNNEL_URL"
    echo ""
    echo "Then redeploy on Vercel."
else
    echo "Could not detect tunnel URL. Check the log:"
    echo "  cat /tmp/cloudflared.log"
fi
echo ""
echo "Useful commands:"
echo "  View tunnel log:   cat /tmp/cloudflared.log"
echo "  Check if running:  pgrep -a cloudflared"
echo "  Stop tunnel:       pkill cloudflared"
echo "  Restart tunnel:    bash /home/ec2-user/lila/deploy/setup-tunnel.sh"
echo ""
echo "Note: The tunnel URL changes if the process restarts."
echo "If that happens, update VITE_API_BASE_URL in Vercel and redeploy."
