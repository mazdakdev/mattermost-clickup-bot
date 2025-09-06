# Deployment Guide

This guide walks you through setting up automated deployment of the Mattermost ClickUp bot to your VPS.

## Prerequisites

- A VPS with Ubuntu/Debian
- SSH access to your VPS
- GitHub repository with the bot code
- Docker and Docker Compose installed on VPS

## Step 1: VPS Setup

1. **SSH into your VPS**:
   ```bash
   ssh user@your-vps-ip
   ```

2. **Run the deployment script**:
   ```bash
   # Download and run the setup script
   curl -fsSL https://raw.githubusercontent.com/your-username/your-repo/main/deploy.sh | bash
   ```

3. **Configure environment**:
   ```bash
   cd /opt/mattermost-clickup-bot
   cp env.production.template .env
   nano .env  # Fill in your actual values
   ```

## Step 2: GitHub Secrets Setup

1. **Go to your GitHub repository**
2. **Navigate to Settings → Secrets and variables → Actions**
3. **Add the following secrets**:

   | Secret Name | Description | Example |
   |-------------|-------------|---------|
   | `VPS_HOST` | Your VPS IP or domain | `192.168.1.100` or `bot.yourdomain.com` |
   | `VPS_USERNAME` | SSH username | `ubuntu` or `root` |
   | `VPS_SSH_KEY` | Private SSH key content | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
   | `VPS_PORT` | SSH port (optional) | `22` |

### Getting Your SSH Key

If you don't have an SSH key pair:

```bash
# Generate new SSH key
ssh-keygen -t ed25519 -C "your-email@example.com"

# Copy public key to VPS
ssh-copy-id user@your-vps-ip

# Display private key (copy this to GitHub secret)
cat ~/.ssh/id_ed25519
```

## Step 3: Test Deployment

1. **Push to main branch**:
   ```bash
   git add .
   git commit -m "feat: add Docker deployment setup"
   git push origin main
   ```

2. **Check GitHub Actions**:
   - Go to your repository → Actions tab
   - Watch the deployment workflow run
   - Check for any errors

3. **Verify on VPS**:
   ```bash
   ssh user@your-vps-ip
   sudo systemctl status mattermost-clickup-bot
   docker-compose -f /opt/mattermost-clickup-bot/docker-compose.yml ps
   ```

## Step 4: Monitoring

### Health Check
```bash
# Check if bot is healthy
curl http://your-vps-ip:5001/health
```

### Logs
```bash
# View bot logs
docker-compose -f /opt/mattermost-clickup-bot/docker-compose.yml logs -f

# View systemd service logs
sudo journalctl -u mattermost-clickup-bot -f
```

### Service Management
```bash
# Start/stop/restart service
sudo systemctl start mattermost-clickup-bot
sudo systemctl stop mattermost-clickup-bot
sudo systemctl restart mattermost-clickup-bot

# Check service status
sudo systemctl status mattermost-clickup-bot
```

## Troubleshooting

### Common Issues

1. **SSH Connection Failed**:
   - Verify VPS_HOST and VPS_USERNAME are correct
   - Check SSH key format (should include headers)
   - Ensure VPS allows SSH connections

2. **Docker Build Failed**:
   - Check GitHub Actions logs for specific errors
   - Verify all files are committed to repository

3. **Bot Not Starting**:
   - Check environment variables in .env file
   - Verify BOT_TOKEN and CLICKUP_API_TOKEN are valid
   - Check Docker logs for errors

4. **Health Check Failing**:
   - Ensure port 5001 is not blocked by firewall
   - Check if bot is actually running

### Manual Deployment

If automated deployment fails:

```bash
# SSH into VPS
ssh user@your-vps-ip

# Navigate to project directory
cd /opt/mattermost-clickup-bot

# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Security Considerations

1. **Firewall**: Only expose necessary ports (22 for SSH, 5001 for health check if needed)
2. **SSH Keys**: Use strong SSH keys and consider key rotation
3. **Environment Variables**: Never commit .env files to git
4. **Updates**: Keep your VPS and Docker images updated
5. **Monitoring**: Set up monitoring for the health check endpoint

## Rollback

If you need to rollback to a previous version:

```bash
# SSH into VPS
ssh user@your-vps-ip

# Navigate to project directory
cd /opt/mattermost-clickup-bot

# Checkout previous commit
git log --oneline  # Find the commit hash
git checkout <previous-commit-hash>

# Rebuild and restart
docker-compose down
docker-compose up -d
```
