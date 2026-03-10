"""Agent loop: the core processing engine."""

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger

from zuberabot.bus.events import InboundMessage, OutboundMessage
from zuberabot.bus.queue import MessageBus
from zuberabot.providers.base import LLMProvider
from zuberabot.agent.context import ContextBuilder
from zuberabot.agent.tools.registry import ToolRegistry
from zuberabot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from zuberabot.agent.tools.shell import ExecTool
from zuberabot.agent.tools.web import WebSearchTool, WebFetchTool
from zuberabot.agent.tools.message import MessageTool
from zuberabot.agent.tools.spawn import SpawnTool
from zuberabot.agent.tools.spawn import SpawnTool
from zuberabot.agent.subagent import SubagentManager
from zuberabot.session.manager import SessionManager
from zuberabot.agent.tools.knowledge import StoreKnowledgeTool



from zuberabot.database.postgres import get_db_manager
from zuberabot.ai.retriever import HybridRetriever

class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """
    
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 20,
        brave_api_key: str | None = None
    ):
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        
        # Initialize Database
        self.db = get_db_manager()
        
        self.context = ContextBuilder(workspace)
        self.sessions = SessionManager(workspace, db_manager=self.db)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
        )
        
        self._running = False
        self._register_default_tools()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools
        self.tools.register(ReadFileTool())
        self.tools.register(WriteFileTool())
        self.tools.register(EditFileTool())
        # self.tools.register(ListDirTool()) # Latency optimization
        
        # Shell tool
        self.tools.register(ExecTool(working_dir=str(self.workspace)))
        
        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        # self.tools.register(WebFetchTool()) # Latency optimization
        
        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)
        
        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)
        
        # Ticket tool
        from zuberabot.agent.tools.ticket import TicketTool
        self.tools.register(TicketTool(db=self.db))
        
        # Knowledge tool
        self.tools.register(StoreKnowledgeTool())
        
        # Expense tool
        from zuberabot.agent.tools.expense import ExpenseTool
        self.tools.register(ExpenseTool(db=self.db))
        
        # RAG Search tool
        from zuberabot.agent.tools.rag import RAGTool
        self.tools.register(RAGTool())
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")
        
        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message to process.
        
        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            return await self._process_system_message(msg)
        
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")
        
        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)
            
        knowledge_tool = self.tools.get("store_knowledge")
        if hasattr(knowledge_tool, "set_context"):
            knowledge_tool.set_context(msg.sender_id)
        
        # Retrieve relevant contexts using RAG only for actual questions
        retrieved_context = ""
        
        # Skip RAG for simple greetings or too short messages
        is_greeting = msg.content.lower().strip() in [
            "hi", "hello", "hey", "hi bot", "hello bot", "hey bot", "ping", "test"
        ]
        
        if len(msg.content.strip()) > 5 and not is_greeting:
            try:
                with self.db.get_session() as db_session:
                    retriever = HybridRetriever(db_session)
                    docs = retriever.retrieve(msg.content, top_k=2) # Reduced from 3 to 2 to save tokens
                    if docs:
                        # Cap retrieval text so local LLMs don't block for minutes
                        context_strs = []
                        for doc in docs:
                            content = doc.content[:2000] + "..." if len(doc.content) > 2000 else doc.content
                            context_strs.append(content)
                        
                        retrieved_context = "\n\n[System retrieved relevant knowledge base content:]\n" + "\n---\n".join(context_strs)
            except Exception as e:
                logger.error(f"RAG retrieval failed: {e}")
            
        augmented_message = msg.content
        if retrieved_context:
            augmented_message += retrieved_context

        # Build initial messages (use get_history for LLM-formatted messages)
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=augmented_message,
            media=msg.media if msg.media else None,
        )
        
        # Agent loop
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Call LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            
            # Handle tool calls
            if response.has_tool_calls:
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)  # Must be JSON string
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                # Execute tools concurrently instead of blocking sequentially
                async def execute_tool(tc):
                    try:
                        args_str = json.dumps(tc.arguments)
                        logger.debug(f"Executing tool: {tc.name} with arguments: {args_str}")
                        res = await self.tools.execute(tc.name, tc.arguments)
                        return tc.id, tc.name, res
                    except Exception as e:
                        logger.error(f"Error in tool {tc.name}: {e}")
                        return tc.id, tc.name, f"Error: {str(e)}"
                        
                tool_results = await asyncio.gather(
                    *(execute_tool(tc) for tc in response.tool_calls)
                )
                
                for tc_id, tc_name, result in tool_results:
                    messages = self.context.add_tool_result(
                        messages, tc_id, tc_name, result
                    )
            else:
                # No tool calls, we're done
                final_content = response.content
                
                # Check if content is a JSON string (common with local models)
                if final_content and final_content.strip().startswith("{"):
                    try:
                        data = json.loads(final_content)
                        if isinstance(data, dict):
                            # Check for message schema leak
                            if "message" in data and "channel" in data and "chat_id" in data:
                                # This is the internal message format leaking
                                final_content = data.get("message", "")
                            # Try to extract content/message
                            elif "content" in data and data["content"]:
                                final_content = data["content"]
                            elif "message" in data and data["message"]:
                                final_content = data["message"]
                            elif "response" in data and data["response"]:
                                final_content = data["response"]
                    except json.JSONDecodeError:
                        pass  # Not JSON, keep as is
                
                # Filter out tool schemas and function definitions (local model issue)
                if final_content:
                    # Check for function/tool schema patterns
                    schema_patterns = [
                        '"type": "function"',
                        '"type":"function"',
                        '"function":',
                        '"parameters":',
                        '"properties":',
                        '"required":',
                        '"schema":',
                        '"description":',
                        'OpenAI format',
                        'tool definition'
                    ]
                    
                    # If response contains schema patterns, it's likely echoing tools
                    if any(pattern in final_content for pattern in schema_patterns):
                        # Check if it's mostly JSON/schema (not just mentioning it)
                        schema_count = sum(1 for p in schema_patterns if p in final_content)
                        if schema_count >= 3:  # Multiple schema markers = likely a schema dump
                            final_content = "Hello! I'm Zubera Bot, your financial assistant. How can I help you today? 💼"
                
                break
        
        if final_content is None:
            final_content = "I've completed processing but have no response to give."
        
        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content
        )
    
    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).
        
        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info(f"Processing system message from {msg.sender_id}")
        
        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id
        
        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)
        
        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content
        )
        
        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            
            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "Background task completed."
        
        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )
    
    async def process_direct(self, content: str, session_key: str = "cli:direct") -> str:
        """
        Process a message directly (for CLI usage).
        
        Args:
            content: The message content.
            session_key: Session identifier.
        
        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel="cli",
            sender_id="user",
            chat_id="direct",
            content=content
        )
        
        response = await self._process_message(msg)
        return response.content if response else ""
