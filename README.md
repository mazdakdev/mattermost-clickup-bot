## Mattermost Bot - Project Structure

### Layout
- `ClickUpBot/`
  - `settings.py`: Environment-driven app settings mapped to `mmpy_bot.Settings`.
  - `plugins/`
    - `__init__.py`
    - `my_plugin.py`: Example plugin with `wake up`, `hi`, and mention-only `hey`.
- `my_bot.py`: Entrypoint that builds settings and runs the bot.
- `.gitignore`: Common Python and env ignores.

### Configuration
Create a `.env` file (or export env vars) with your bot configuration:

```
MATTERMOST_URL=http://127.0.0.1
MATTERMOST_PORT=8065
BOT_TOKEN=your_bot_token
BOT_TEAM=your_team
SSL_VERIFY=false
RESPOND_CHANNEL_HELP=false
WEBHOOK_HOST_ENABLED=false
# WEBHOOK_HOST_URL=http://0.0.0.0
# WEBHOOK_HOST_PORT=5001

# ClickUp
CLICKUP_API_TOKEN=your_clickup_token
# CLICKUP_LIST_ID is now optional - the bot will let you select interactively
```

All values have sensible defaults except `BOT_TOKEN` and `BOT_TEAM` which you should set.

### Run

#### Local Development
```bash
python my_bot.py
```

#### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

#### Production Deployment on VPS
1. **Setup VPS** (run once):
   ```bash
   # Make deploy script executable and run it
   chmod +x deploy.sh
   ./deploy.sh
   ```

2. **Configure Environment**:
   ```bash
   # Copy environment template
   cp env.production.template .env
   
   # Edit with your actual values
   nano .env
   ```

3. **Deploy**:
   ```bash
   # Start the service
   sudo systemctl start mattermost-clickup-bot
   
   # Check status
   sudo systemctl status mattermost-clickup-bot
   
   # View logs
   docker-compose logs -f
   ```

Send `wake up` in a channel where the bot is present, or `@botname hey` to test mention-only.

### Customize
- Add your own plugins under `ClickUpBot/plugins/` and include them in `my_bot.py` plugins list.
- For advanced features (regex, direct-only, allowed users/channels, click commands, webhooks, scheduling), follow `mmpy_bot` docs and use the examples in `my_plugin.py` as a starting point.

### ClickUp Task Management (CRUD Operations)

The bot provides complete CRUD (Create, Read, Update, Delete) functionality for ClickUp tasks with interactive flows:

#### **Create Task** - `create task`
1. **Task name** - Enter the name of your task
2. **Description** - Add a description (or type 'skip')
3. **Due date** - Set due date in YYYY-MM-DD format (or type 'skip')
4. **List selection** - Navigate through your ClickUp hierarchy:
   - Select a team from available teams
   - Select a space from the chosen team
   - Select a folder (or choose to use lists directly in the space)
   - Select the final list where the task will be created
5. **Confirmation** - Review all details and confirm creation

#### **View Task** - `view task`
1. **List selection** - Navigate through your ClickUp hierarchy to select a list
2. **Task selection** - Choose from available tasks in the selected list
3. **Task details** - View comprehensive task information including name, description, status, due date, assignees, tags, and more

#### **List Tasks** - `list tasks`
1. **List selection** - Navigate through your ClickUp hierarchy to select a list
2. **Task listing** - View all tasks in the selected list with key details

#### **Search Tasks** - `search tasks`
1. **Search query** - Enter what you want to search for
2. **Search results** - View matching tasks across your ClickUp workspace

#### **Update Task** - `update task`
1. **Task ID** - Provide the ID of the task to update
2. **Field selection** - Choose which field to update (name, description, due_date, status)
3. **New value** - Enter the new value for the selected field
4. **Confirmation** - Review and confirm the update

#### **Delete Task** - `delete task`
1. **Task ID** - Provide the ID of the task to delete
2. **Confirmation** - Review task details and confirm deletion (requires typing 'DELETE')

#### **Common Features**
- The bot dynamically fetches your ClickUp teams, spaces, folders, and lists
- You can navigate back through the selection process using 'back' or cancel anytime with 'cancel'
- Only `CLICKUP_API_TOKEN` is required - no need to hardcode list IDs
- All operations include safety confirmations and detailed error handling

### ClickUp Reporting and Analytics

The bot provides comprehensive reporting and analytics features to track team performance and task progress:

#### **Daily Report** - `daily report`
- Shows tasks created and completed today
- Identifies overdue tasks
- Provides daily productivity summary
- Tracks team activity and progress

#### **Weekly Report** - `weekly report`
- Weekly task completion statistics
- Team performance metrics
- Completion rate analysis
- Top performer recognition
- Overdue task tracking

#### **Overdue Tasks** - `overdue tasks`
- Lists all overdue tasks with days overdue
- Categorizes by urgency (Critical, Urgent, Recent)
- Helps prioritize work and catch up on delays
- Provides clear visibility into bottlenecks

#### **Completed Tasks** - `completed tasks`
- Shows tasks completed in the last 7 days
- Tracks completion trends
- Identifies productive team members
- Provides completion history

#### **Team Analytics** - `team analytics`
- Comprehensive team performance metrics
- Task status breakdown and distribution
- Individual team member performance
- Priority analysis and workload distribution
- Completion rates and productivity insights

#### **Task Summary** - `task summary`
- Quick overview of all tasks
- Upcoming deadlines (next 7 days)
- Overdue task alerts
- High-level project status

#### **Reporting Features**
- **Interactive Selection** - Choose teams and date ranges
- **Rich Analytics** - Detailed metrics and insights
- **Performance Tracking** - Monitor team and individual progress
- **Deadline Management** - Stay on top of upcoming and overdue tasks
- **Trend Analysis** - Track completion rates and productivity patterns

### GitHub CI/CD Setup

The project includes automated deployment to your VPS via GitHub Actions.

#### **Required GitHub Secrets**
Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

- `VPS_HOST` - Your VPS IP address or domain
- `VPS_USERNAME` - SSH username for your VPS
- `VPS_SSH_KEY` - Private SSH key for VPS access
- `VPS_PORT` - SSH port (optional, defaults to 22)

#### **Deployment Flow**
1. Push to `main` or `master` branch
2. GitHub Actions automatically:
   - Runs tests and linting
   - Builds Docker image
   - Pushes to GitHub Container Registry
   - Deploys to your VPS via SSH
   - Restarts the bot service

#### **Manual Deployment**
```bash
# SSH into your VPS
ssh user@your-vps-ip

# Navigate to project directory
cd /opt/mattermost-clickup-bot

# Pull latest changes and restart
git pull origin main
docker-compose down
docker-compose up -d
```

### Health Monitoring

The bot includes a health check endpoint at `http://your-vps:5001/health` for monitoring and Docker health checks.

