import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from mmpy_bot import Plugin, listen_to, schedule
from mmpy_bot import Message

from ClickUpBot.services import clickup_client


@dataclass
class TaskSnapshot:
    """Snapshot of a task at a specific point in time for tracking changes."""
    task_id: str
    name: str
    status: str
    assignee: Optional[str]
    due_date: Optional[str]
    created_date: str
    updated_date: str
    list_id: str
    list_name: str
    space_name: str
    team_name: str
    timestamp: datetime


@dataclass
class ReportingDraft:
    """State for interactive reporting flows."""
    operation: str = "report"  # report, analytics, overdue, completed
    step: str = "team_selection"  # team_selection -> date_range -> confirm
    team_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    # Team selection state
    current_teams: List[clickup_client.ClickUpItem] = field(default_factory=list)
    selected_team_id: Optional[str] = None


class ReportingPlugin(Plugin):
    """
    Comprehensive reporting and analytics for ClickUp tasks.
    Provides insights into task completion, overdue items, team performance, and more.
    """

    def __init__(self):
        super().__init__()
        self.user_states: Dict[str, ReportingDraft] = {}
        self.task_snapshots: Dict[str, List[TaskSnapshot]] = {}  # team_id -> snapshots
        self.last_snapshot_time: Dict[str, datetime] = {}  # team_id -> last snapshot

    # Entry triggers for reporting operations
    @listen_to(r"^daily\s+report$", re.IGNORECASE)
    async def start_daily_report(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = ReportingDraft(operation="daily_report")
        await self._start_team_selection(message, self.user_states[user_id])

    @listen_to(r"^weekly\s+report$", re.IGNORECASE)
    async def start_weekly_report(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = ReportingDraft(operation="weekly_report")
        await self._start_team_selection(message, self.user_states[user_id])

    @listen_to(r"^overdue\s+tasks$", re.IGNORECASE)
    async def start_overdue_report(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = ReportingDraft(operation="overdue")
        await self._start_team_selection(message, self.user_states[user_id])

    @listen_to(r"^completed\s+tasks$", re.IGNORECASE)
    async def start_completed_report(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = ReportingDraft(operation="completed")
        await self._start_team_selection(message, self.user_states[user_id])

    @listen_to(r"^team\s+analytics$", re.IGNORECASE)
    async def start_team_analytics(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = ReportingDraft(operation="analytics")
        await self._start_team_selection(message, self.user_states[user_id])

    @listen_to(r"^task\s+summary$", re.IGNORECASE)
    async def start_task_summary(self, message: Message):
        user_id = message.user_id
        self.user_states[user_id] = ReportingDraft(operation="summary")
        await self._start_team_selection(message, self.user_states[user_id])

    # Catch-all for reporting flows
    @listen_to(r"^(?!daily\s+report$|weekly\s+report$|overdue\s+tasks$|completed\s+tasks$|team\s+analytics$|task\s+summary$).+", re.IGNORECASE)
    async def handle_reporting_interaction(self, message: Message):
        user_id = message.user_id
        draft = self.user_states.get(user_id)

        if not draft:
            return

        content = message.text.strip()

        if content.lower() == "cancel":
            self.driver.reply_to(message, "Cancelled reporting operation.")
            self.user_states.pop(user_id, None)
            return

        if draft.step == "team_selection":
            await self._handle_team_selection(message, draft, content)
        elif draft.step == "date_range":
            await self._handle_date_range_selection(message, draft, content)
        elif draft.step == "confirm":
            await self._handle_report_confirmation(message, draft, content)

    async def _start_team_selection(self, message: Message, draft: ReportingDraft):
        """Start team selection for reporting."""
        self.driver.reply_to(message, "Let's generate a report. First, select your team...")
        
        success, teams_or_error = clickup_client.get_teams()
        if not success:
            self.driver.reply_to(message, f"Failed to fetch teams: {teams_or_error}")
            self.user_states.pop(message.user_id, None)
            return
        
        draft.current_teams = teams_or_error
        draft.step = "team_selection"
        
        if not draft.current_teams:
            self.driver.reply_to(message, "No teams found. Operation cancelled.")
            self.user_states.pop(message.user_id, None)
            return
        
        teams_text = "Available teams:\n"
        for i, team in enumerate(draft.current_teams, 1):
            team_name = team.name if hasattr(team, 'name') and team.name else f"Team {i}"
            teams_text += f"{i}. {team_name}\n"
        teams_text += "\nType the number of the team you want to report on, or 'cancel' to abort."
        
        self.driver.reply_to(message, teams_text)

    async def _handle_team_selection(self, message: Message, draft: ReportingDraft, content: str):
        """Handle team selection."""
        try:
            selection = int(content)
            if 1 <= selection <= len(draft.current_teams):
                selected_team = draft.current_teams[selection - 1]
                draft.selected_team_id = selected_team.id
                draft.team_id = selected_team.id
                
                # Set date ranges based on operation type
                now = datetime.now(timezone.utc)
                
                if draft.operation == "daily_report":
                    draft.start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    draft.end_date = now
                    draft.step = "confirm"
                    await self._execute_daily_report(message, draft)
                    
                elif draft.operation == "weekly_report":
                    draft.start_date = now - timedelta(days=7)
                    draft.end_date = now
                    draft.step = "confirm"
                    await self._execute_weekly_report(message, draft)
                    
                elif draft.operation == "overdue":
                    await self._execute_overdue_report(message, draft)
                    
                elif draft.operation == "completed":
                    draft.start_date = now - timedelta(days=7)
                    draft.end_date = now
                    draft.step = "confirm"
                    await self._execute_completed_report(message, draft)
                    
                elif draft.operation == "analytics":
                    draft.step = "confirm"
                    await self._execute_team_analytics(message, draft)
                    
                elif draft.operation == "summary":
                    draft.step = "confirm"
                    await self._execute_task_summary(message, draft)
                
                self.user_states.pop(message.user_id, None)
                return
            else:
                self.driver.reply_to(message, f"Please enter a number between 1 and {len(draft.current_teams)}.")
        except ValueError:
            self.driver.reply_to(message, "Please enter a valid number or 'cancel' to abort.")

    async def _handle_date_range_selection(self, message: Message, draft: ReportingDraft, content: str):
        """Handle date range selection (for custom reports)."""
        # This would be implemented for custom date range reports
        pass

    async def _handle_report_confirmation(self, message: Message, draft: ReportingDraft, content: str):
        """Handle report confirmation."""
        if content.lower() == "confirm":
            # Execute the appropriate report
            pass
        elif content.lower() == "cancel":
            self.driver.reply_to(message, "Cancelled reporting operation.")
            self.user_states.pop(message.user_id, None)

    async def _execute_daily_report(self, message: Message, draft: ReportingDraft):
        """Generate and display daily report."""
        self.driver.reply_to(message, f"📊 Generating daily report for {draft.current_teams[0].name}...")
        
        # Get today's tasks
        success, tasks_data = clickup_client.get_team_tasks(
            draft.team_id, 
            include_closed=True
        )
        
        if not success:
            self.driver.reply_to(message, f"Failed to fetch tasks: {tasks_data}")
            return
        
        if not isinstance(tasks_data, dict) or "tasks" not in tasks_data:
            self.driver.reply_to(message, "Unexpected response format from ClickUp API.")
            return
        
        tasks = tasks_data["tasks"]
        report = self._generate_daily_report(tasks, draft.start_date, draft.end_date)
        self.driver.reply_to(message, report)

    async def _execute_weekly_report(self, message: Message, draft: ReportingDraft):
        """Generate and display weekly report."""
        self.driver.reply_to(message, f"📊 Generating weekly report for {draft.current_teams[0].name}...")
        
        success, tasks_data = clickup_client.get_team_tasks(
            draft.team_id, 
            include_closed=True
        )
        
        if not success:
            self.driver.reply_to(message, f"Failed to fetch tasks: {tasks_data}")
            return
        
        if not isinstance(tasks_data, dict) or "tasks" not in tasks_data:
            self.driver.reply_to(message, "Unexpected response format from ClickUp API.")
            return
        
        tasks = tasks_data["tasks"]
        report = self._generate_weekly_report(tasks, draft.start_date, draft.end_date)
        self.driver.reply_to(message, report)

    async def _execute_overdue_report(self, message: Message, draft: ReportingDraft):
        """Generate and display overdue tasks report."""
        self.driver.reply_to(message, f"⚠️ Finding overdue tasks for {draft.current_teams[0].name}...")
        
        success, tasks_data = clickup_client.get_team_tasks(
            draft.team_id, 
            include_closed=True  # Include closed tasks to get all tasks
        )
        
        if not success:
            self.driver.reply_to(message, f"Failed to fetch tasks: {tasks_data}")
            self.user_states.pop(message.user_id, None)
            return
        
        if not isinstance(tasks_data, dict) or "tasks" not in tasks_data:
            self.driver.reply_to(message, "Unexpected response format from ClickUp API.")
            self.user_states.pop(message.user_id, None)
            return
        
        tasks = tasks_data["tasks"]
        try:
            report = self._generate_overdue_report(tasks)
            self.driver.reply_to(message, report)
        except Exception as e:
            print(f"ERROR: Failed to generate overdue report: {e}")
            self.driver.reply_to(message, f"Error generating overdue report: {str(e)}")
        
        # Clear user state after completion
        self.user_states.pop(message.user_id, None)

    async def _execute_completed_report(self, message: Message, draft: ReportingDraft):
        """Generate and display completed tasks report."""
        self.driver.reply_to(message, f"✅ Finding completed tasks for {draft.current_teams[0].name}...")
        
        success, tasks_data = clickup_client.get_team_tasks(
            draft.team_id, 
            include_closed=True
        )
        
        if not success:
            self.driver.reply_to(message, f"Failed to fetch tasks: {tasks_data}")
            return
        
        if not isinstance(tasks_data, dict) or "tasks" not in tasks_data:
            self.driver.reply_to(message, "Unexpected response format from ClickUp API.")
            return
        
        tasks = tasks_data["tasks"]
        report = self._generate_completed_report(tasks, draft.start_date, draft.end_date)
        self.driver.reply_to(message, report)

    async def _execute_team_analytics(self, message: Message, draft: ReportingDraft):
        """Generate and display team analytics."""
        self.driver.reply_to(message, f"📈 Generating team analytics for {draft.current_teams[0].name}...")
        
        success, tasks_data = clickup_client.get_team_tasks(
            draft.team_id, 
            include_closed=True
        )
        
        if not success:
            self.driver.reply_to(message, f"Failed to fetch tasks: {tasks_data}")
            return
        
        if not isinstance(tasks_data, dict) or "tasks" not in tasks_data:
            self.driver.reply_to(message, "Unexpected response format from ClickUp API.")
            return
        
        tasks = tasks_data["tasks"]
        
        # Get team members for analytics
        success, members_data = clickup_client.get_team_members(draft.team_id)
        members = members_data.get("members", []) if success else []
        
        report = self._generate_team_analytics(tasks, members)
        self.driver.reply_to(message, report)

    async def _execute_task_summary(self, message: Message, draft: ReportingDraft):
        """Generate and display task summary."""
        self.driver.reply_to(message, f"📋 Generating task summary for {draft.current_teams[0].name}...")
        
        success, tasks_data = clickup_client.get_team_tasks(
            draft.team_id, 
            include_closed=True
        )
        
        if not success:
            self.driver.reply_to(message, f"Failed to fetch tasks: {tasks_data}")
            return
        
        if not isinstance(tasks_data, dict) or "tasks" not in tasks_data:
            self.driver.reply_to(message, "Unexpected response format from ClickUp API.")
            return
        
        tasks = tasks_data["tasks"]
        report = self._generate_task_summary(tasks)
        self.driver.reply_to(message, report)

    def _generate_daily_report(self, tasks: List[Dict], start_date: datetime, end_date: datetime) -> str:
        """Generate daily report content."""
        today_tasks = []
        completed_today = []
        created_today = []
        overdue = []
        
        for task in tasks:
            task_date_created = self._parse_date(task.get('date_created'))
            task_date_updated = self._parse_date(task.get('date_updated'))
            due_date = self._parse_date(task.get('due_date'))
            status = task.get('status', {}).get('status', 'Unknown')
            
            # Tasks created today
            if task_date_created and task_date_created.date() == start_date.date():
                created_today.append(task)
            
            # Tasks completed today
            if status.lower() in ['complete', 'completed', 'done'] and task_date_updated and task_date_updated.date() == start_date.date():
                completed_today.append(task)
            
            # Overdue tasks
            if due_date and due_date < end_date and status.lower() not in ['complete', 'completed', 'done']:
                overdue.append(task)
            
            # All tasks for today
            if task_date_created and task_date_created.date() == start_date.date():
                today_tasks.append(task)
        
        report = f"📊 **Daily Report - {start_date.strftime('%Y-%m-%d')}**\n\n"
        
        # Summary stats
        report += f"**📈 Summary:**\n"
        report += f"• Tasks created today: {len(created_today)}\n"
        report += f"• Tasks completed today: {len(completed_today)}\n"
        report += f"• Overdue tasks: {len(overdue)}\n"
        report += f"• Total active tasks: {len([t for t in tasks if t.get('status', {}).get('status', '').lower() not in ['complete', 'completed', 'done']])}\n\n"
        
        # New tasks
        if created_today:
            report += f"**🆕 New Tasks ({len(created_today)}):**\n"
            for task in created_today[:5]:  # Limit to 5
                report += f"• {task.get('name', 'Unnamed')} (ID: {task.get('id', '?')})\n"
            if len(created_today) > 5:
                report += f"... and {len(created_today) - 5} more\n"
            report += "\n"
        
        # Completed tasks
        if completed_today:
            report += f"**✅ Completed Today ({len(completed_today)}):**\n"
            for task in completed_today[:5]:  # Limit to 5
                report += f"• {task.get('name', 'Unnamed')} (ID: {task.get('id', '?')})\n"
            if len(completed_today) > 5:
                report += f"... and {len(completed_today) - 5} more\n"
            report += "\n"
        
        # Overdue tasks
        if overdue:
            report += f"**⚠️ Overdue Tasks ({len(overdue)}):**\n"
            for task in overdue[:5]:  # Limit to 5
                due_date = self._parse_date(task.get('due_date'))
                days_overdue = (end_date.date() - due_date.date()).days if due_date else 0
                report += f"• {task.get('name', 'Unnamed')} - {days_overdue} days overdue\n"
            if len(overdue) > 5:
                report += f"... and {len(overdue) - 5} more\n"
        
        return report

    def _generate_weekly_report(self, tasks: List[Dict], start_date: datetime, end_date: datetime) -> str:
        """Generate weekly report content."""
        week_tasks = []
        completed_this_week = []
        created_this_week = []
        overdue = []
        
        for task in tasks:
            task_date_created = self._parse_date(task.get('date_created'))
            task_date_updated = self._parse_date(task.get('date_updated'))
            due_date = self._parse_date(task.get('due_date'))
            status = task.get('status', {}).get('status', 'Unknown')
            
            # Tasks created this week
            if task_date_created and start_date <= task_date_created <= end_date:
                created_this_week.append(task)
            
            # Tasks completed this week
            if status.lower() in ['complete', 'completed', 'done'] and task_date_updated and start_date <= task_date_updated <= end_date:
                completed_this_week.append(task)
            
            # Overdue tasks
            if due_date and due_date < end_date and status.lower() not in ['complete', 'completed', 'done']:
                overdue.append(task)
        
        report = f"📊 **Weekly Report - {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}**\n\n"
        
        # Summary stats
        report += f"**📈 Summary:**\n"
        report += f"• Tasks created this week: {len(created_this_week)}\n"
        report += f"• Tasks completed this week: {len(completed_this_week)}\n"
        report += f"• Overdue tasks: {len(overdue)}\n"
        report += f"• Completion rate: {(len(completed_this_week) / max(len(created_this_week), 1) * 100):.1f}%\n\n"
        
        # Top performers (by completion)
        completion_by_assignee = {}
        for task in completed_this_week:
            assignees = task.get('assignees', [])
            for assignee in assignees:
                username = assignee.get('username', 'Unassigned')
                completion_by_assignee[username] = completion_by_assignee.get(username, 0) + 1
        
        if completion_by_assignee:
            report += f"**🏆 Top Performers (Tasks Completed):**\n"
            sorted_assignees = sorted(completion_by_assignee.items(), key=lambda x: x[1], reverse=True)
            for username, count in sorted_assignees[:3]:
                report += f"• {username}: {count} tasks\n"
            report += "\n"
        
        # Overdue tasks
        if overdue:
            report += f"**⚠️ Overdue Tasks ({len(overdue)}):**\n"
            for task in overdue[:5]:  # Limit to 5
                due_date = self._parse_date(task.get('due_date'))
                days_overdue = (end_date.date() - due_date.date()).days if due_date else 0
                report += f"• {task.get('name', 'Unnamed')} - {days_overdue} days overdue\n"
            if len(overdue) > 5:
                report += f"... and {len(overdue) - 5} more\n"
        
        return report

    def _generate_overdue_report(self, tasks: List[Dict]) -> str:
        """Generate overdue tasks report."""
        overdue = []
        now = datetime.now(timezone.utc)
        
        print(f"DEBUG: Generating overdue report for {len(tasks)} tasks")
        
        for task in tasks:
            due_date_raw = task.get('due_date')
            due_date = self._parse_date(due_date_raw)
            status = task.get('status', {}).get('status', 'Unknown')
            
            if due_date and due_date < now and status.lower() not in ['complete', 'completed', 'done']:
                days_overdue = (now.date() - due_date.date()).days
                overdue.append((task, days_overdue))
        
        print(f"DEBUG: Found {len(overdue)} overdue tasks")
        
        # Sort by days overdue (most overdue first)
        overdue.sort(key=lambda x: x[1], reverse=True)
        
        report = f"⚠️ **Overdue Tasks Report**\n\n"
        report += f"**Total Overdue Tasks: {len(overdue)}**\n\n"
        
        if not overdue:
            report += "🎉 **Great job! No overdue tasks found.**"
            return report
        
        # Group by days overdue
        critical = [(t, d) for t, d in overdue if d > 7]  # More than a week
        urgent = [(t, d) for t, d in overdue if 3 < d <= 7]  # 3-7 days
        recent = [(t, d) for t, d in overdue if d <= 3]  # 1-3 days
        
        if critical:
            report += f"🚨 **Critical ({len(critical)} tasks - Over 7 days overdue):**\n"
            for task, days in critical[:5]:
                report += f"• {task.get('name', 'Unnamed')} - {days} days overdue\n"
            if len(critical) > 5:
                report += f"... and {len(critical) - 5} more\n"
            report += "\n"
        
        if urgent:
            report += f"⚠️ **Urgent ({len(urgent)} tasks - 3-7 days overdue):**\n"
            for task, days in urgent[:5]:
                report += f"• {task.get('name', 'Unnamed')} - {days} days overdue\n"
            if len(urgent) > 5:
                report += f"... and {len(urgent) - 5} more\n"
            report += "\n"
        
        if recent:
            report += f"📅 **Recent ({len(recent)} tasks - 1-3 days overdue):**\n"
            for task, days in recent[:5]:
                report += f"• {task.get('name', 'Unnamed')} - {days} days overdue\n"
            if len(recent) > 5:
                report += f"... and {len(recent) - 5} more\n"
        
        print(f"DEBUG: Generated report length: {len(report)} characters")
        print(f"DEBUG: Report preview: {report[:200]}...")
        return report

    def _generate_completed_report(self, tasks: List[Dict], start_date: datetime, end_date: datetime) -> str:
        """Generate completed tasks report."""
        completed = []
        
        for task in tasks:
            task_date_updated = self._parse_date(task.get('date_updated'))
            status = task.get('status', {}).get('status', 'Unknown')
            
            if status.lower() in ['complete', 'completed', 'done'] and task_date_updated and start_date <= task_date_updated <= end_date:
                completed.append(task)
        
        # Sort by completion date (most recent first)
        completed.sort(key=lambda x: self._parse_date(x.get('date_updated')) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        
        report = f"✅ **Completed Tasks Report**\n\n"
        report += f"**Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n"
        report += f"**Total Completed:** {len(completed)}\n\n"
        
        if not completed:
            report += "No tasks completed in this period."
            return report
        
        # Group by completion date
        completion_by_date = {}
        for task in completed:
            completion_date = self._parse_date(task.get('date_updated'))
            if completion_date:
                date_str = completion_date.strftime('%Y-%m-%d')
                if date_str not in completion_by_date:
                    completion_by_date[date_str] = []
                completion_by_date[date_str].append(task)
        
        # Show recent completions
        report += f"**📋 Recent Completions:**\n"
        for task in completed[:10]:  # Show last 10
            completion_date = self._parse_date(task.get('date_updated'))
            date_str = completion_date.strftime('%Y-%m-%d') if completion_date else 'Unknown'
            assignees = [a.get('username', 'Unassigned') for a in task.get('assignees', [])]
            assignee_str = ', '.join(assignees) if assignees else 'Unassigned'
            report += f"• {task.get('name', 'Unnamed')} - {assignee_str} ({date_str})\n"
        
        if len(completed) > 10:
            report += f"... and {len(completed) - 10} more\n"
        
        return report

    def _generate_team_analytics(self, tasks: List[Dict], members: List[Dict]) -> str:
        """Generate team analytics report."""
        report = f"📈 **Team Analytics Report**\n\n"
        
        # Basic stats
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t.get('status', {}).get('status', '').lower() in ['complete', 'completed', 'done']])
        active_tasks = total_tasks - completed_tasks
        
        report += f"**📊 Overall Statistics:**\n"
        report += f"• Total tasks: {total_tasks}\n"
        report += f"• Completed tasks: {completed_tasks}\n"
        report += f"• Active tasks: {active_tasks}\n"
        report += f"• Completion rate: {(completed_tasks / max(total_tasks, 1) * 100):.1f}%\n\n"
        
        # Task status breakdown
        status_counts = {}
        for task in tasks:
            status = task.get('status', {}).get('status', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        if status_counts:
            report += f"**📋 Task Status Breakdown:**\n"
            for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_tasks * 100) if total_tasks > 0 else 0
                report += f"• {status}: {count} ({percentage:.1f}%)\n"
            report += "\n"
        
        # Assignee performance
        assignee_stats = {}
        for task in tasks:
            assignees = task.get('assignees', [])
            if not assignees:
                assignee_stats['Unassigned'] = assignee_stats.get('Unassigned', {'total': 0, 'completed': 0})
                assignee_stats['Unassigned']['total'] += 1
                if task.get('status', {}).get('status', '').lower() in ['complete', 'completed', 'done']:
                    assignee_stats['Unassigned']['completed'] += 1
            else:
                for assignee in assignees:
                    username = assignee.get('username', 'Unknown')
                    if username not in assignee_stats:
                        assignee_stats[username] = {'total': 0, 'completed': 0}
                    assignee_stats[username]['total'] += 1
                    if task.get('status', {}).get('status', '').lower() in ['complete', 'completed', 'done']:
                        assignee_stats[username]['completed'] += 1
        
        if assignee_stats:
            report += f"**👥 Team Performance:**\n"
            for username, stats in sorted(assignee_stats.items(), key=lambda x: x[1]['completed'], reverse=True):
                completion_rate = (stats['completed'] / max(stats['total'], 1) * 100)
                report += f"• {username}: {stats['completed']}/{stats['total']} ({completion_rate:.1f}%)\n"
            report += "\n"
        
        # Priority analysis
        priority_counts = {}
        for task in tasks:
            priority = task.get('priority', {}).get('priority', 'Normal')
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        if priority_counts:
            report += f"**⚡ Priority Distribution:**\n"
            for priority, count in sorted(priority_counts.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_tasks * 100) if total_tasks > 0 else 0
                report += f"• {priority}: {count} ({percentage:.1f}%)\n"
        
        return report

    def _generate_task_summary(self, tasks: List[Dict]) -> str:
        """Generate task summary report."""
        report = f"📋 **Task Summary Report**\n\n"
        
        # Basic counts
        total_tasks = len(tasks)
        completed = len([t for t in tasks if t.get('status', {}).get('status', '').lower() in ['complete', 'completed', 'done']])
        active = total_tasks - completed
        
        report += f"**📊 Quick Overview:**\n"
        report += f"• Total tasks: {total_tasks}\n"
        report += f"• Active tasks: {active}\n"
        report += f"• Completed tasks: {completed}\n\n"
        
        # Upcoming deadlines
        now = datetime.now(timezone.utc)
        upcoming = []
        overdue = []
        
        for task in tasks:
            due_date = self._parse_date(task.get('due_date'))
            status = task.get('status', {}).get('status', 'Unknown')
            
            if due_date and status.lower() not in ['complete', 'completed', 'done']:
                days_until_due = (due_date.date() - now.date()).days
                if days_until_due < 0:
                    overdue.append((task, abs(days_until_due)))
                elif days_until_due <= 7:
                    upcoming.append((task, days_until_due))
        
        if upcoming:
            report += f"**📅 Upcoming Deadlines (Next 7 Days):**\n"
            upcoming.sort(key=lambda x: x[1])
            for task, days in upcoming[:5]:
                report += f"• {task.get('name', 'Unnamed')} - Due in {days} days\n"
            if len(upcoming) > 5:
                report += f"... and {len(upcoming) - 5} more\n"
            report += "\n"
        
        if overdue:
            report += f"**⚠️ Overdue Tasks ({len(overdue)}):**\n"
            overdue.sort(key=lambda x: x[1], reverse=True)
            for task, days in overdue[:5]:
                report += f"• {task.get('name', 'Unnamed')} - {days} days overdue\n"
            if len(overdue) > 5:
                report += f"... and {len(overdue) - 5} more\n"
        
        return report

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_str:
            return None
        
        try:
            # Handle different date formats
            if isinstance(date_str, str):
                # Try timestamp in milliseconds first (ClickUp format)
                if date_str.isdigit() and len(date_str) == 13:
                    timestamp = int(date_str) / 1000  # Convert milliseconds to seconds
                    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
                # Try ISO format
                elif 'T' in date_str:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                # Try simple date format
                else:
                    return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass
        
        return None

    # # Scheduled reports (can be enabled with @schedule decorator)
    # @schedule("0 9 * * 1-5")  # 9 AM on weekdays
    # async def daily_standup_reminder(self):
    #     """Send daily standup reminder with task summary."""
    #     # This would be implemented to send daily reports to specific channels
    #     pass

    # @schedule("0 17 * * 5")  # 5 PM on Fridays
    # async def weekly_summary(self):
    #     """Send weekly summary report."""
    #     # This would be implemented to send weekly reports
    #     pass
