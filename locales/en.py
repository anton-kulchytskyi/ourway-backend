messages = {
    # Auth
    "email_already_registered": "Email already registered",
    "invalid_credentials": "Invalid email or password",
    "account_disabled": "Account is disabled",
    "invalid_token": "Invalid or expired token",
    "user_not_found": "User not found",

    # Organization
    "no_organization": "User has no organization",

    # Spaces
    "space_not_found": "Space not found",
    "supervised_cannot_create_spaces": "Supervised children cannot create spaces",

    # Tasks
    "task_not_found": "Task not found",
    "viewers_cannot_modify_tasks": "Viewers cannot modify tasks",

    # Gamification
    "reward_not_found": "Reward not found",
    "insufficient_points": "Not enough points",

    # General
    "forbidden": "Access denied",
    "not_found": "Not found",
    "plan_already_completed": "Plan is already completed",

    # Schedule / Events / Daily plan permissions
    "children_cannot_create_schedules": "Children cannot create schedules",
    "only_owner_can_create_for_others": "Only owner can create schedules for others",
    "children_cannot_create_events": "Children cannot create events",
    "children_cannot_edit_events": "Children cannot edit events",
    "children_cannot_delete_events": "Children cannot delete events",

    # Morning briefing (bot notification)
    "morning_greeting": "☀️ <b>Good morning, {name}!</b>",
    "morning_free_day": "Today is a free day 🎉",
    "morning_footer": "Go for it! You can do it 💪",
    "task_overdue": "overdue {days}d",
    "task_due_today": "today",

    # Evening ritual (bot notification)
    "evening_ritual_prompt": "🌙 <b>Time to plan tomorrow with {name}!</b>",
    "evening_ritual_prompt_multi": "🌙 <b>Time to plan tomorrow with your kids!</b>",
    "evening_ritual_body": "Review the schedule and tasks together.",
    "evening_reminder_solo": "🌙 <b>Time to plan tomorrow!</b>\nCheck your schedule and tasks.",

    # Bot — account linking
    "start_not_linked": (
        "👋 Hello! I'm OurWay bot.\n\n"
        "To get started, link your account:\n"
        "Open the app → Settings → Connect Telegram"
    ),
    "start_linked": "👋 Hello, {name}! Your account is already linked.",
    "account_linked_success": "✅ Account linked! Welcome, {name}.",
    "account_already_linked": "This Telegram account is already linked to another user.",
    "invalid_link_token": "Invalid or expired link. Please generate a new one in the app.",

    # Bot — tasks
    "my_tasks_empty": "You have no active tasks right now.",
    "my_tasks_header": "📋 <b>Your tasks:</b>",
    "task_done_success": "✅ Task marked as done!",
    "task_done_points": "✅ Done! +{points} pts",

    # Task assignment notification
    "task_assigned_title": "New task assigned to you",
    "task_assigned_by": "Assigned by: {name}",

    # Evening — plan confirmed notification to child
    "plan_ready_for_child": "🌙 <b>{name} made your plan for tomorrow!</b>\n\nUse /today to see it.",

    # Task statuses
    "status_backlog": "Backlog",
    "status_todo": "To Do",
    "status_in_progress": "In Progress",
    "status_blocked": "Blocked",
    "status_done": "Done",
}
