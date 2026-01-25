from typing import Dict, List
import discord
from ..models.table_instance import TableInstance

def parse_max_role_number(guild: discord.Guild) -> int:
	max_n = 0
	for role in guild.roles:
		parts = role.name.split()
		if len(parts) == 3 and parts[0] == "Mesa" and parts[1].isdigit() and parts[2] in ("Jogador", "Mestre"):
			try:
				max_n = max(max_n, int(parts[1]))
			except Exception:
				pass
	return max_n

def make_embed(inst: TableInstance) -> discord.Embed:
	embed = discord.Embed(
		title=f"Criação da Mesa {inst.table_number}",
		description="Clique em **Participar** para entrar na mesa.",
		color=discord.Color.blue()
	)
	embed.add_field(name="Mestre", value=inst.master.mention, inline=False)
	embed.add_field(
		name=f"Jogadores: {len(inst.players)}",
		value="\n".join(p.mention for p in inst.players) if inst.players else "Nenhum jogador entrou ainda...",
		inline=False
	)
	embed.set_footer(text="• Mestre: clique em 'Criar mesa' quando estiver pronto")
	return embed

def get_overwrites(
	guild: discord.Guild,
	table_role: discord.Role,
	master_role: discord.Role,
	*,
	player_send_messages: bool = True,
	is_voice: bool = False,
	is_category: bool = False,
) -> Dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
	default = discord.PermissionOverwrite(view_channel=False)
	player = discord.PermissionOverwrite(view_channel=True)
	master = discord.PermissionOverwrite(view_channel=True, manage_channels=True)

	if is_voice:
		default.connect = False
		player.connect = True
		master.connect = True
	else:
		player.send_messages = player_send_messages
		master.send_messages = True
		master.manage_messages = True

	if is_category:
		player = discord.PermissionOverwrite(view_channel=True)
		master = discord.PermissionOverwrite(view_channel=True, manage_channels=True)

	return {
		guild.default_role: default,
		table_role: player,
		master_role: master,
	}
 
async def reorder_category_channels(
   guild: discord.Guild, 
   category: discord.CategoryChannel, 
   desired_order_names: list, 
   created_channels: Dict[str, discord.abc.GuildChannel], *, 
   wait_before=0.15
) -> None:
	try:
		if wait_before and wait_before > 0:
			await discord.utils.sleep_until
			import asyncio
			await asyncio.sleep(wait_before)

		base_pos = getattr(category, "position", None)
		if base_pos is None:
			cat_channels = [c for c in guild.channels if getattr(c, "category", None) == category]
			if cat_channels:
				base_pos = min(c.position for c in cat_channels) - 1
			else:
				base_pos = max((c.position for c in guild.channels), default=0)
		base_pos = int(base_pos) + 1

		desired_channels = []
		for name in desired_order_names:
			ch = created_channels.get(name)
			if ch:
				desired_channels.append(ch)
		if not desired_channels:
			return

		edits = []
		for offset, ch in enumerate(desired_channels):
			edits.append({"id": ch.id, "position": base_pos + offset})

		await guild.edit_channel_positions(edits)
	except Exception:
		pass