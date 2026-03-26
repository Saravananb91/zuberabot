from __future__ import annotations
"""Expense tracking tool for personal finance management."""

from typing import Any
from datetime import datetime
from loguru import logger

from zuberabot.agent.tools.base import Tool

from zuberabot.agent.tools.base import Tool
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from zuberabot.database.postgres import DatabaseManager



class ExpenseTool(Tool):
    """Tool for tracking expenses and managing budgets."""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.user_id = None
    
    def set_context(self, user_id: str):
        """Set the context for the current user."""
        self.user_id = user_id
    
    name = "expense_tracker"
    description = "Track expenses (spent, bought, paid, etc.) and manage budgets"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add_expense", "get_expenses", "monthly_summary"],
                "description": "The action to perform. Use 'add_expense' for new spending."
            },
            "category": {
                "type": "string",
                "description": "Category (food, transport, bills, entertainment, shopping, healthcare, other)"
            },
            "amount": {
                "type": "number",
                "description": "The numeric amount spent in INR"
            },
            "description": {
                "type": "string",
                "description": "Short description of what was bought"
            },
            "month": {
                "type": "string",
                "description": "Month in YYYY-MM format (for queries)"
            }
        },
        "required": ["action"]
    }
    

    async def execute(self, action: str, user_id: int | str | None = None, **kwargs: Any) -> str:
        try:
            # Ensure DB is available
            if not self.db:
                return "❌ Error: Database not configured"

            # Use tool context if user_id not provided by LLM
            effective_user_id = user_id or self.user_id
            
            if not effective_user_id:
                return "❌ Error: User ID not detected and not provided"

            if action == "add_expense":
                category = kwargs.get('category', 'other')
                amount = kwargs.get('amount')
                description = kwargs.get('description', '')
                
                if not amount:
                    return "❌ Error: Amount is required"
                
                expense = self.db.add_expense(
                    user_id=effective_user_id,
                    amount=float(amount),
                    category=category,
                    description=description
                )
                return f"✅ Expense added: ₹{expense.amount} for {expense.category}"
            
            elif action == "get_expenses":
                month = kwargs.get('month')
                category = kwargs.get('category')
                
                expenses = self.db.get_expenses(effective_user_id, month, category)
                
                if not expenses:
                    return "No expenses found for this criteria."
                
                total = sum(e.amount for e in expenses)
                summary = "\n".join([f"- {e.date.date()}: ₹{e.amount} ({e.category})" for e in expenses[:10]])
                
                if len(expenses) > 10:
                    summary += f"\n...and {len(expenses) - 10} more"
                    
                return f"📊 EXPENSE REPORT\nTotal: ₹{total}\n\n{summary}"
            
            elif action == "monthly_summary":
                # Re-use get_expenses for now, improved later
                month = kwargs.get('month', datetime.now().strftime('%Y-%m'))
                expenses = self.db.get_expenses(effective_user_id, month=month)
                
                if not expenses:
                    return f"No expenses found for {month}"
                
                total = sum(e.amount for e in expenses)
                by_category = {}
                for e in expenses:
                    by_category[e.category] = by_category.get(e.category, 0) + e.amount
                
                cat_summary = "\n".join([f"{k}: ₹{v}" for k, v in by_category.items()])
                
                return f"📈 SUMMARY for {month}\nTotal: ₹{total}\n\nBreakdown:\n{cat_summary}"
            
            return f"Unknown action: {action}"
            
        except Exception as e:
            logger.error(f"Expense tool error: {e}")
            return f"❌ Error: {str(e)}"
