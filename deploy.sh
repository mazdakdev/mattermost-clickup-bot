#!/bin/bash

# Mattermost ClickUp Bot Deployment Script
# This script sets up the bot on your VPS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/opt/mattermost-clickup-bot"
SERVICE_NAME="mattermost-clickup-bot"

echo -e "${GREEN}🚀 Starting Mattermost ClickUp Bot deployment...${NC}"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}❌ This script should not be run as root${NC}"
   exit 1
fi

# Create project directory
echo -e "${YELLOW}📁 Creating project directory...${NC}"
sudo mkdir -p $PROJECT_DIR
sudo chown $USER:$USER $PROJECT_DIR

# Install Docker if not installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}🐳 Installing Docker...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${GREEN}✅ Docker installed. Please log out and back in for group changes to take effect.${NC}"
fi

# Install Docker Compose if not installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}🐳 Installing Docker Compose...${NC}"
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Create environment file template
echo -e "${YELLOW}📝 Creating environment file template...${NC}"
cat > $PROJECT_DIR/.env.template << EOF
# Mattermost Bot Configuration
MATTERMOST_URL=http://your-mattermost-server.com
MATTERMOST_PORT=8065
BOT_TOKEN=your_bot_token_here
BOT_TEAM=your_team_name
SSL_VERIFY=false
RESPOND_CHANNEL_HELP=false

# Webhook Configuration (optional)
WEBHOOK_HOST_ENABLED=false
WEBHOOK_HOST_URL=http://0.0.0.0
WEBHOOK_HOST_PORT=5001

# ClickUp Configuration
CLICKUP_API_TOKEN=your_clickup_api_token
CLICKUP_LIST_ID=
CLICKUP_BASE_URL=https://api.clickup.com/api/v2
EOF

# Create systemd service file
echo -e "${YELLOW}⚙️ Creating systemd service...${NC}"
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=Mattermost ClickUp Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0
User=$USER

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

echo -e "${GREEN}✅ Deployment setup complete!${NC}"
echo -e "${YELLOW}📋 Next steps:${NC}"
echo "1. Copy your project files to $PROJECT_DIR"
echo "2. Copy .env.template to .env and fill in your configuration"
echo "3. Run: sudo systemctl start $SERVICE_NAME"
echo "4. Check status: sudo systemctl status $SERVICE_NAME"
echo "5. View logs: docker-compose -f $PROJECT_DIR/docker-compose.yml logs -f"

echo -e "${GREEN}🎉 Setup complete!${NC}"
