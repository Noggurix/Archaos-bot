from dataclasses import dataclass, field
from typing import Optional, List
import asyncio
import discord

@dataclass
class TableInstance:
	id: str
	guild_id: int
	master: discord.Member
	table_number: int

	players: List[discord.Member] = field(default_factory=list)
	embed_message: Optional[discord.Message] = None
	reserved_cancel_task: Optional[asyncio.Task] = None

	creating: bool = False