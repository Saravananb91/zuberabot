from __future__ import annotations
"""Ticket management tool for creating and tracking user tickets."""

from typing import Any
from loguru import logger

from zuberabot.agent.tools.base import Tool

from zuberabot.agent.tools.base import Tool
# Use generic naming, but typed for the injected manager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from zuberabot.database.postgres import DatabaseManager



class TicketTool(Tool):
    """Tool for managing support tickets."""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.user_id = None
    
    def set_context(self, user_id: str):
        """Set the context for the current user."""
        self.user_id = user_id
    
    @property
    def name(self) -> str:
        return "ticket_manager"
    
    @property
    def description(self) -> str:
        return "Create and manage support tickets. Use this when a user reports an issue, makes a request, or needs follow-up. Actions: 'create', 'get', 'update', 'list'"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "get", "update", "list"],
                    "description": "Action to perform"
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID (Auto-detected, only provide if performing action for another user)"
                },
                "ticket_id": {
                    "type": "integer",
                    "description": "Ticket ID (required for get/update)"
                },
                "channel": {
                    "type": "string",
                    "description": "Channel (whatsapp)"
                },
                "chat_id": {
                    "type": "string",
                    "description": "Chat ID"
                },
                "subject": {
                    "type": "string",
                    "description": "Ticket subject"
                },
                "description": {
                    "type": "string",
                    "description": "Ticket description"
                },
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "resolved", "closed"],
                    "description": "Ticket status (for update)"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Priority level"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, action: str, **kwargs) -> str:
        """Execute ticket operation."""
        try:
            # Use tool context if user_id not provided by LLM
            user_id = kwargs.get('user_id') or self.user_id
            
            if action == "create":
                if not user_id:
                    return "❌ Error: User ID not detected and not provided"
                return await self._create_ticket(user_id=user_id, **kwargs)
            elif action == "get":
                return await self._get_ticket(**kwargs)
            elif action == "update":
                return await self._update_ticket(**kwargs)
            elif action == "list":
                if not user_id:
                    return "❌ Error: User ID not detected and not provided"
                return await self._list_tickets(user_id=user_id, **kwargs)
            else:
                return f"Unknown action: {action}"
        except Exception as e:
            logger.error(f"Ticket tool error: {e}")
            return f"Error: {str(e)}"
    
    async def _create_ticket(self, user_id: str | int, channel: str = "whatsapp", chat_id: str | None = None, subject: str = "Support Ticket", **kwargs) -> str:
        """Create a new ticket."""
        ticket = self.db.create_ticket(
            user_id=user_id,
            channel=channel,
            chat_id=chat_id or str(user_id),
            subject=subject,
            description=kwargs.get('description', ''),
            priority=kwargs.get('priority', 'medium')
        )
        return f"✅ Ticket #{ticket.id} created: {subject}"
    
    async def _get_ticket(self, ticket_id: int, **kwargs) -> str:
        """Get ticket details."""
        ticket = self.db.get_ticket(ticket_id)
        if not ticket:
            return f"❌ Ticket #{ticket_id} not found"
        
        t = ticket.to_dict()
        return f"📋 Ticket #{t['id']}\nStatus: {t['status']}\nSubject: {t['subject']}\nCreated: {t['created_at']}\nPriority: {t['priority']}"
    
    async def _update_ticket(self, ticket_id: int, status: str, **kwargs) -> str:
        """Update ticket status."""
        success = self.db.update_ticket_status(ticket_id, status)
        if success:
            return f"✅ Ticket #{ticket_id} updated to: {status}"
        return f"❌ Failed to update ticket #{ticket_id}"
    
    async def _list_tickets(self, user_id: int, **kwargs) -> str:
        """List user's tickets."""
        status_filter = kwargs.get('status')
        tickets = self.db.get_user_tickets(user_id, status_filter)
        
        if not tickets:
            return "No tickets found"
        
        result = f"📋 Found {len(tickets)} ticket(s):\n"
        for ticket in tickets[:10]:  # Limit to 10
            t = ticket.to_dict()
            result += f"\n#{t['id']} - {t['subject']} [{t['status']}]"
        
        return result
