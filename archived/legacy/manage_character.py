import asyncio
import io
import json
import re
from urllib.parse import urlparse
import discord
from discord.ext import commands
from utils.database_utils import (
    get_player, 
    delete_player, 
    edit_player, 
    update_proficiency, 
    update_inventory, 
    update_history, 
    fetch_characters_from_db, 
    update_character_name_in_images
)

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

with open("emojis.json", encoding="utf-8") as f:
    config = json.load(f)

custom_emojis = config["custom_emojis"]

class Manage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        async def get_all_characters(ctx: discord.AutocompleteContext):
            player_id = None
            for option in ctx.interaction.data['options']:
                if option['name'] == 'player':
                    player_id = option['value']
                    break

            guild_id = ctx.interaction.guild.id
            characters = fetch_characters_from_db(player_id, guild_id)

            character_options = [
                discord.OptionChoice(
                    name=f"{character['name']} ({character['table_id']} - {character['sheet_system']})",
                    value=character['name']
                )
                for character in characters if ctx.value.lower() in character['name'].lower()
            ]

            return character_options

        async def get_all_members(interaction: discord.Interaction):
            return [member for member in interaction.guild.members]

        @bot.slash_command(name="ficha", description="Exibe a ficha de um personagem")
        async def ficha(interaction: discord.Interaction,
            player: discord.Option(discord.User, description="De quem é a ficha?:", autocomplete=get_all_members, required=True), # type: ignore
            character: discord.Option(str, description="Nome do personagem:", autocomplete=get_all_characters, required=True)): # type: ignore

            player = player.id
            guild_id = interaction.guild.id

            characters = fetch_characters_from_db(player, guild_id)
            selected_character = next((char for char in characters if char['name'] == character), None)

            if selected_character:
                sheet_system = selected_character['sheet_system']
                mesa = selected_character['table_id']
                character = selected_character['character']

            master_pattern = r"Table (\d+) Master"
            def has_matching_master_role(user_roles, mesa_name):
                mesa_number = re.match(r"Table (\d+)", mesa_name).group(1)
                for role in user_roles:
                    match = re.match(master_pattern, role.name)
                    if match and match.group(1) == mesa_number:
                        return True
                return False

            if player is not None:
                if get_player(player, interaction.guild.id, sheet_system, character, mesa):
                    is_master_of_table = has_matching_master_role(interaction.user.roles, mesa)
                    if str(player) != str(interaction.user.id) and is_master_of_table:
                        player_to_show = get_player(player, interaction.guild.id, sheet_system, character, mesa)
                        await send_character_sheet(interaction, player_to_show, for_master_edit=player, sheet_system=sheet_system, character=character, mesa=mesa)
                    elif str(player) != str(interaction.user.id) and not is_master_of_table:
                        await interaction.response.send_message("Apenas mestres podem ver a ficha de outros jogadores.", ephemeral=True)
                    elif str(player) == str(interaction.user.id):
                        player_to_show = get_player(interaction.user.id, interaction.guild.id, sheet_system, character, mesa)
                        await send_character_sheet(interaction, player_to_show, for_master_edit=interaction.user.id, sheet_system=sheet_system, character=character, mesa=mesa)
                else:
                    await interaction.response.send_message("Esta ficha não existe.", ephemeral=True)

        async def send_character_sheet(interaction, player_to_show, for_master_edit, sheet_system, character, mesa):
            level_emoji = custom_emojis["LEVEL"]
            hp_emoji = custom_emojis["HP"]
            race_emoji = custom_emojis["RACE"]
            class_emoji = custom_emojis["CLASS"]

            def create_embed(player_data):
                embed = discord.Embed(title=f"`{player_data[0]}` (Lvl {player_data[2]} {level_emoji})", description="", color=discord.Color.blue())
                if is_valid_url(player_data[26]):
                    embed.set_thumbnail(url=player_data[26])
                else:
                    embed.set_thumbnail(url="")

                fields = [
                    ("",f"📆 **Age:** {player_data[1]}", True),
                    ("",f"{hp_emoji} **HP:** {player_data[3]}", True),
                    ("",f"✨ **MP:** {player_data[4]}", True),
                    ("",f"{race_emoji} **Race:** {player_data[5]}", True),
                    ("",f"{class_emoji} **Class:** {player_data[6]}", True),
                    ("🧙‍♂️ Spells:", player_data[7], False),
                    ("🤹‍♂️ Skills:", player_data[8], False),
                    ("",f"🙌 **Worship:** {player_data[9]}", True),
                    ("",f"👾 **Submission:** {player_data[10]}", True),
                    ("🏅 Attributes:", (f'''```Strength: {player_data[13]}\nDexterity: {player_data[14]}\nAgility: {player_data[15]}\nIntelligence: {player_data[16]}\nWisdom: {player_data[17]}\nSocial: {player_data[18]}```'''), False),
                    ("🧩 Proficiencies:", ", ".join(player_data[19:26]), False),
                ]

                for name, value, inline in fields:
                    embed.add_field(name=name, value=value, inline=inline)

                return embed

            embed = create_embed(player_to_show)

            main_view = discord.ui.View()

            button_edit = discord.ui.Button(label="Edit", style=discord.ButtonStyle.secondary)
            back_button = discord.ui.Button(label="◀️ Back", style=discord.ButtonStyle.secondary)

            main_view.add_item(button_edit)

            async def edit(interaction: discord.Interaction):
                attributes = [
                    ("Name", "name"),
                    ("Age", "age"),
                    ("Level", "level"),
                    ("HP", "hp"),
                    ("MP", "mp"),
                    ("Race", "race"),
                    ("Class", "_class"),
                    ("Spell", "magic"),
                    ("Skills", "skills"),
                    ("Worship", "worship"),
                    ("Submission", "submission"),
                    ("Strength", "strength"),
                    ("Dexterity", "dexterity"),
                    ("Agility", "agility"),
                    ("Intelligence", "intelligence"),
                    ("Wisdom", "wisdom"),
                    ("Social", "social"),
                    ("Appearance", "avatar"),
                ]

                edit_view = discord.ui.View()
                background_view = discord.ui.View()

                history_button = discord.ui.Button(label="Update", style=discord.ButtonStyle.green)
                proficiency_button = discord.ui.Button(label="🧩 Proficiencies", style=discord.ButtonStyle.secondary)
                inventory_button = discord.ui.Button(label="🎒 Inventory", style=discord.ButtonStyle.secondary)
                background_button = discord.ui.Button(label="📝 Background", style=discord.ButtonStyle.secondary)

                select_options = [discord.SelectOption(label=label, value=value) for label, value in attributes]
                select = discord.ui.Select(placeholder="Selecione o campo para editar", options=select_options)

                edit_view.add_item(select)
                edit_view.add_item(back_button)
                edit_view.add_item(proficiency_button)
                edit_view.add_item(inventory_button)
                edit_view.add_item(background_button)

                proficiency_button.callback = proficiency_button_callback

                async def inventory_button_callback(interaction: discord.Interaction):
                    player_to_show = get_player(for_master_edit, interaction.guild.id, sheet_system, character, mesa)
                    inventory = player_to_show[11].split(", ") if player_to_show[11] else []

                    def create_inventory_embed():
                        embed = discord.Embed(title=f"{player_to_show[0]}'s Inventory")
                        for idx, item in enumerate(inventory, start=1):
                            embed.add_field(name=f"{idx}.", value=item, inline=False)
                        return embed

                    class AddItemModal(discord.ui.Modal):
                        def __init__(self, inventory):
                            super().__init__(title="Add Item to Inventory")
                            self.inventory = inventory
                            self.item_name = discord.ui.InputText(label="Item Name")
                            self.add_item(self.item_name)

                        async def callback(self, interaction: discord.Interaction):
                            new_item = self.item_name.value.strip()
                            if not new_item:
                                await interaction.response.send_message("Item name cannot be empty.", ephemeral=True)
                                return

                            update_inventory(for_master_edit, interaction.guild.id, sheet_system, character, mesa, new_item, "add")
                            self.inventory.append(new_item)

                            embed = create_inventory_embed()
                            await interaction.response.edit_message(embed=embed, view=inventory_view)
                            confirmation_inventory = await interaction.followup.send(f"Added **{new_item}** to the inventory.", ephemeral=True)

                            await asyncio.sleep(3)
                            await confirmation_inventory.delete()

                    class RemoveItemSelect(discord.ui.Select):
                        def __init__(self):
                            self.back_button = back_button
                            options = [
                                discord.SelectOption(label=item, value=item)
                                for item in inventory
                            ] if inventory else [discord.SelectOption(label="No items available", value="none", default=True)]
                            super().__init__(placeholder="Select an item to remove", options=options)

                        async def callback(self, interaction: discord.Interaction):
                            selected_item = self.values[0]

                            update_inventory(for_master_edit, interaction.guild.id, sheet_system, character, mesa, selected_item, "remove")
                            inventory.remove(selected_item)

                            self.options = [
                                discord.SelectOption(label=item, value=item)
                                for item in inventory
                            ] if inventory else [discord.SelectOption(label="No items available", value="none", default=True)]

                            view = discord.ui.View()
                            view.add_item(self)
                            view.add_item(self.back_button)

                            await interaction.response.edit_message(embed=create_inventory_embed(), view=view)
                            confirmation_inventory = await interaction.followup.send(f"Removed **{selected_item}** from the inventory.", ephemeral=True)

                            await asyncio.sleep(3)
                            await confirmation_inventory.delete()

                    async def add_item_callback(interaction: discord.Interaction):
                        await interaction.response.send_modal(AddItemModal(inventory))

                    async def remove_item_callback(interaction: discord.Interaction):
                        inventory_view.clear_items()
                        inventory_view.add_item(RemoveItemSelect())
                        inventory_view.add_item(back_button)
                        await interaction.response.edit_message(view=inventory_view)

                        async def back_button_callback(interaction: discord.Interaction):
                            inventory_view.clear_items()
                            inventory_view.add_item(back_button)
                            inventory_view.add_item(add_button)
                            inventory_view.add_item(remove_button)
                            back_button.callback = back_button_callback_main
                            await interaction.response.edit_message(view=inventory_view)
                        back_button.callback = back_button_callback

                    inventory_view = discord.ui.View()
                    add_button = discord.ui.Button(label="Add Item", style=discord.ButtonStyle.green)
                    remove_button = discord.ui.Button(label="Remove Item", style=discord.ButtonStyle.red)

                    inventory_view.add_item(back_button)
                    inventory_view.add_item(add_button)
                    inventory_view.add_item(remove_button)

                    add_button.callback = add_item_callback
                    remove_button.callback = remove_item_callback

                    await interaction.response.edit_message(embed=create_inventory_embed(), view=inventory_view)

                    async def back_button_callback_main(interaction: discord.Interaction):
                        player_to_show = get_player(for_master_edit, interaction.guild.id, sheet_system, character, mesa)
                        await interaction.response.edit_message(embed=create_embed(player_to_show), view=main_view)
                    back_button.callback = back_button_callback_main

                inventory_button.callback = inventory_button_callback

                async def process_history_file(interaction: discord.Interaction, file: discord.Attachment):
                    if not file.filename.endswith(".txt"):
                        await interaction.response.send_message("Por favor, envie um arquivo .txt válido.", ephemeral=True)
                        return

                    content = await file.read()
                    history = content.decode("utf-8")

                    update_history(for_master_edit, interaction.guild.id, sheet_system, character, mesa, history)
                    player_to_show = get_player(for_master_edit, interaction.guild.id, sheet_system, character, mesa)

                    txt_file = io.StringIO(player_to_show[12])
                    txt_file.seek(0)

                    await interaction.edit_original_response(content=None, view=background_view, file=discord.File(fp=txt_file, filename=f"{player_to_show[0]}_history.txt"))

                    confirmation_message = await interaction.followup.send(f"História atualizada! {interaction.user.mention}", ephemeral=True)

                    background_view.add_item(back_button)
                    background_view.add_item(history_button)

                    await asyncio.sleep(15)
                    await confirmation_message.delete()

                async def background_button_callback(interaction: discord.Interaction):
                    player_to_show = get_player(for_master_edit, interaction.guild.id, sheet_system, character, mesa)

                    background_view.add_item(back_button)
                    background_view.add_item(history_button)

                    txt_file = io.StringIO(player_to_show[12])
                    txt_file.seek(0)

                    background_message_ref = await interaction.response.send_message(embed=None, view=background_view, file=discord.File(fp=txt_file, filename=f"{player_to_show[0]}_history.txt"), ephemeral=True)

                    async def history_button_callback(interaction: discord.Interaction):
                        await interaction.response.send_message("Por favor, envie um arquivo `.txt` contendo a nova história em sua DM.", ephemeral=True)
                        await background_message_ref.delete_original_response()

                        dm_channel = await interaction.user.create_dm()
                        await dm_channel.send("Envie sua história aqui em formato de arquivo .txt. Apenas você verá este conteúdo.")

                        def check(msg: discord.Message):
                            return (msg.author == interaction.user and msg.channel == dm_channel and msg.attachments)

                        try:
                            msg = await interaction.client.wait_for("message", check=check, timeout=300)
                            file = msg.attachments[0]
                            await process_history_file(interaction, file)
                        except asyncio.TimeoutError:
                            await interaction.followup.send("Tempo esgotado! Por favor, tente novamente.", ephemeral=True)
                    history_button.callback = history_button_callback

                    async def back_button_callback_main(interaction: discord.Interaction):
                        await interaction.response.edit_message(content=None, embed=create_embed(player_to_show), view=main_view, attachments=[])
                    back_button.callback = back_button_callback_main

                background_button.callback = background_button_callback

                async def back_button_callback(interaction: discord.Interaction):
                    await interaction.response.edit_message(view=main_view)
                back_button.callback = back_button_callback

                async def select_callback(interaction: discord.Interaction):
                    selected_field = interaction.data["values"][0]
                    field_label = next((opt.label for opt in select.options if opt.value == selected_field), "Desconhecido")

                    if selected_field == "avatar":
                        input_label = "Image URL"
                    else:
                        input_label = f"Novo valor de {field_label}"

                    modal = discord.ui.Modal(title=f"Editar {field_label}")
                    input_field = discord.ui.InputText(label=input_label, style=discord.InputTextStyle.short)
                    modal.add_item(input_field)

                    async def modal_callback(interaction: discord.Interaction):
                        nonlocal player_to_show
                        new_value = interaction.data["components"][0]["components"][0]["value"]
                        try:
                            field_mapping = {
                                "name": 0,
                                "age": 1,
                                "level": 2,
                                "hp": 3,
                                "mp": 4,
                                "race": 5,
                                "_class": 6,
                                "magic": 7,
                                "skills": 8,
                                "worship": 9,
                                "submission": 10,
                                "inventory": 11,
                                "history": 12,
                                "strength": 13,
                                "dexterity": 14,
                                "agility": 15,
                                "intelligence": 16,
                                "wisdom": 17,
                                "social": 18,
                                "avatar": 26
                            }
                            updated_values = list(player_to_show)
                            index_to_update = field_mapping[selected_field]
                            updated_values[index_to_update] = new_value

                            if selected_field == "name":
                                old_name = player_to_show[field_mapping["name"]]
                                update_character_name_in_images(old_name, new_value)

                            edit_values = {key: updated_values[index] for key, index in field_mapping.items() if key not in ["inventory", "history"]}

                            edit_player(for_master_edit, interaction.guild.id, sheet_system, character, mesa, **edit_values)
                            player_to_show = get_player(for_master_edit, interaction.guild.id, sheet_system, character, mesa)
                            embed = create_embed(player_to_show)

                            await interaction.response.edit_message(embed=embed, view=edit_view)
                        except ValueError:
                            await interaction.response.send_message("Valor inválido. Insira um número válido.", ephemeral=True)

                    modal.callback = modal_callback
                    await interaction.response.send_modal(modal)

                select.callback = select_callback
                await interaction.response.edit_message(view=edit_view)

            async def button_edit_callback(interaction: discord.Interaction):
                await edit(interaction)
            button_edit.callback = button_edit_callback

            async def proficiency_description(interaction: discord.Interaction):
                description_embed = discord.Embed(title="Descrição das Proficiências", color=discord.Color.blue())

                proficiencies = {
                    "Força:": [
                        "**->** *Atletismo*: Habilidade em realizar proezas físicas, como escaladas, corridas e levantamento de peso.",
                        "**->** *Intimidação*: Capacidade de impor medo e influenciar outros por meio da força física.",
                        "**->** *Luta Desarmada*: Proficiência em combate sem armas, usando apenas o corpo para atacar e se defender."
                    ],
                    "Destreza:": [
                        "**->** *Arremesso*: Precisão e força ao arremessar objetos, como projéteis ou armas de arremesso.",
                        "**->** *Luta Armada*: Proficiência em combate com armas, usando espadas ou outros equipamentos para atacar e se defender."
                    ],
                    "Agilidade:": [
                        "**->** *Acrobacia*: Habilidade em realizar acrobacias, saltos e movimentos ágeis.",
                        "**->** *Furtividade*: Capacidade de se mover silenciosamente e evitar detecção.",
                        "**->** *Esquiva*: Agilidade em evitar ataques físicos por meio de movimentos rápidos e evasivos.",
                        "**->** *Equilíbrio*: Capacidade de manter o equilíbrio em superfícies instáveis ou realizar feitos de equilibrismo."
                    ],
                    "Inteligência:": [
                        "**->** *Manipulação de Elementos*: Controle e manipulação de elementos naturais, como fogo, água, terra ou ar.",
                        "**->** *Conjuração Rápida*: Habilidade em conjurar feitiços de forma rápida e eficiente.",
                        "**->** *Encantamento*: Aptidão em imbuir objetos com propriedades mágicas para diversos propósitos."
                    ],
                    "Sabedoria:": [
                        "**->** *Percepção Afiada*: Permite detectar armadilhas, mentiras ou situações perigosas, ajudando a identificar ameaças antes que elas se tornem um problema.",
                        "**->** *Sobrevivência*: Capacidade de encontrar alimentos, água e abrigo em ambientes selvagens, além de seguir rastros e reconhecer sinais da natureza."
                    ],
                    "Social:": [
                        "**->** *Persuasão*: Capacidade de convencer e influenciar outros por meio de palavras.",
                        "**->** *Intimidação Social*: Habilidade em impor respeito e medo através da presença e postura.",
                        "**->** *Diplomacia*: Proficiência em negociação e resolução de conflitos por meio do diálogo.",
                        "**->** *Enganação*: Aptidão em enganar e iludir, seja por meio de disfarces e/ou mentiras convincentes."
                    ]
                }

                selected_proficiencies = []

                for name, descriptions in proficiencies.items():
                    description_embed.add_field(name=name, value="\n".join(descriptions), inline=False)

                proficiency_view = discord.ui.View()
                proficiency_options = [
                    discord.SelectOption(label=desc.replace("**->**", "").replace("*", "").strip().split(":")[0], value=desc.replace("**->**", "").replace("*", "").strip().split(":")[0])
                    for descriptions in proficiencies.values() 
                    for desc in descriptions
                ]
                select_proficiency = discord.ui.Select(placeholder="Selecione 7 proficiências", options=proficiency_options)

                proficiency_view.add_item(select_proficiency)
                proficiency_view.add_item(back_button)

                async def select_proficiency_callback(interaction: discord.Interaction):
                    selected_proficiency = interaction.data["values"][0]
                    selected_proficiencies.append(selected_proficiency)
                    description_embed.set_footer(text=f"{', '.join(selected_proficiencies)}. ({len(selected_proficiencies)} Selecionadas)")
                    select_proficiency.options = [option for option in select_proficiency.options if option.value != selected_proficiency]
                    await interaction.response.edit_message(embed=description_embed, view=proficiency_view)

                    if len(selected_proficiencies) == 7:
                        update_proficiency(for_master_edit, interaction.guild.id, sheet_system, character, mesa, *selected_proficiencies[:7])
                        player_to_show = get_player(for_master_edit, interaction.guild.id, sheet_system, character, mesa)
                        proficiency_view.clear_items()

                        await interaction.followup.edit_message(message_id=interaction.message.id, embed=create_embed(player_to_show), view=main_view)

                select_proficiency.callback = select_proficiency_callback

                async def back_button_callback(interaction: discord.Interaction):
                        await interaction.response.edit_message(embed=create_embed(player_to_show), view=main_view)
                back_button.callback = back_button_callback

                await interaction.response.edit_message(embed=description_embed, view=proficiency_view)

            async def proficiency_button_callback(interaction: discord.Interaction):
                await proficiency_description(interaction)

            await interaction.response.send_message(embed=embed, view=main_view, ephemeral=True)

        @bot.slash_command(name="delete", description="Apaga a ficha de um personagem", ephemeral=True)
        async def apagar(interaction: discord.Interaction,
            player: discord.Option(discord.User, description="De quem é a ficha?:", autocomplete=get_all_members, required=True), # type: ignore
            character: discord.Option(str, description="Nome do personagem:", autocomplete=get_all_characters, required=True)): # type: ignore

            player = player.id
            guild_id = interaction.guild.id

            characters = fetch_characters_from_db(player, guild_id)
            selected_character = next((char for char in characters if char['name'] == character), None)

            if selected_character:
                sheet_system = selected_character['sheet_system']
                mesa = selected_character['table_id']
                character = selected_character['character']

            player = get_player(interaction.user.id, interaction.guild.id, sheet_system, character, mesa)
            if player:
                delete_player(interaction.user.id, interaction.guild.id, sheet_system, character, mesa)
                await interaction.response.send_message("Sua ficha foi apagada com sucesso.", ephemeral=True)
            else:
                await interaction.response.send_message("Você não tem uma ficha para apagar.", ephemeral=True)

def setup(bot):
    bot.add_cog(Manage(bot))
