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

```
python my_bot.py
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

