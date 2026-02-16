"""Platform-level defaults for sl-ot-tools.

These are merged with company-level and engagement-level configs,
with more specific configs taking precedence.
"""

PLATFORM_SKIP_SENDERS = [
    "no-reply@zoom.us",
    "noreply@github.com",
    "no-reply@amazonaws.com",
    "notifications@github.com",
    "mailer-daemon@",
    "postmaster@",
    "calendar-notification@google.com",
    "noreply@microsoft.com",
    "no-reply@sns.amazonaws.com",
    "donotreply@myworkday.com",
]

KNOWLEDGE_TYPES = [
    "decision",
    "technical",
    "status",
    "action",
    "blocker",
    "timeline",
    "budget",
    "risk",
]
