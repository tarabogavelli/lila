#!/bin/bash
set -e

echo "=== Setting up Cloudflare Tunnel ==="
echo ""

TUNNEL_NAME="${1:-lila-backend}"

echo "Step 1: Installing cloudflared..."
curl -fsSL https://pkg.cloudflare.com/cloudflared-ascii.repo | sudo tee /etc/yum.repos.d/cloudflared.repo
sudo dnf install -y cloudflared

echo ""
echo "Step 2: Logging in to Cloudflare..."
echo "  A browser URL will appear. Open it, log in, and authorize."
echo "  (If you're on EC2 with no browser, copy the URL and open it on your laptop.)"
echo ""
cloudflared tunnel login

echo ""
echo "Step 3: Creating tunnel '$TUNNEL_NAME'..."
cloudflared tunnel create "$TUNNEL_NAME"

TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
echo "  Tunnel ID: $TUNNEL_ID"

echo ""
echo "Step 4: Writing tunnel config..."
mkdir -p /home/ec2-user/.cloudflared
cat > /home/ec2-user/.cloudflared/config.yml << EOF
tunnel: $TUNNEL_ID
credentials-file: /home/ec2-user/.cloudflared/$TUNNEL_ID.json

ingress:
  - service: http://localhost:8000
EOF

echo ""
echo "Step 5: Installing as systemd service..."
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

echo ""
echo "Step 6: Setting up DNS route..."
echo "  You need a domain on Cloudflare to create a DNS route."
echo "  If you don't have one, you can use the tunnel URL directly."
echo ""
echo "  To get your tunnel URL, run:"
echo "    cloudflared tunnel info $TUNNEL_NAME"
echo ""
echo "  To route a domain (if you have one on Cloudflare), run:"
echo "    cloudflared tunnel route dns $TUNNEL_NAME api.yourdomain.com"
echo ""

TUNNEL_URL="https://${TUNNEL_ID}.cfargotunnel.com"
echo "=== Setup complete ==="
echo ""
echo "Your backend is available at:"
echo "  $TUNNEL_URL"
echo ""
echo "Update your Vercel environment variable:"
echo "  VITE_API_BASE_URL = $TUNNEL_URL"
echo ""
echo "Then redeploy on Vercel."
echo ""
echo "Useful commands:"
echo "  Check status:  sudo systemctl status cloudflared"
echo "  View logs:     journalctl -u cloudflared -f"
echo "  Restart:       sudo systemctl restart cloudflared"
