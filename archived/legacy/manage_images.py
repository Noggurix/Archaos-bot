import asyncio
from datetime import datetime
from io import BytesIO
import aiohttp
import discord
from discord.ext import commands
from PIL import Image
from utils.database_utils import (
    fetch_characters, 
    add_images_to_album, 
    pick_character_url_images, 
    autocomplete_character_with_images, 
    remove_image, 
    urls_in_row
)

class ManageImages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_valid_image(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return False, "A URL não é acessível ou válida.", False

                    content_type = response.headers.get("Content-Type", "")
                    if not content_type.startswith("image/"):
                        return False, "A URL fornecida não aponta para uma imagem.", False

                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) > 2 * 1024 * 1024:
                        return False, "A imagem é maior do que 2 MB, por favor envie uma imagem menor.", False

                    image_data = await response.read()
                    image = Image.open(BytesIO(image_data))
                    max_dimensions = (1500, 1500)
                    needs_resize = image.size[0] > max_dimensions[0] or image.size[1] > max_dimensions[1]

            return True, "", needs_resize
        except Exception as e:
            return False, f"Erro ao processar a imagem: {e}", False

    async def resize_image(self, url, max_width=1024, max_height=1024):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            return None

                        image_data = await response.read()
                        image = Image.open(BytesIO(image_data))

                        image.thumbnail((max_width, max_height))

                        buffer = BytesIO()
                        image_format = image.format if image.format else "PNG"
                        image.save(buffer, format=image_format)
                        buffer.seek(0)

                        return buffer

            except Exception as e:
                print(f"Erro ao redimensionar a imagem: {e}")
                return None

    @commands.slash_command(name="manage_album", description="Personalize seu álbum.")
    async def manage_images(self, ctx):
        user_id = ctx.author.id
        guild_id = ctx.guild.id

        characters = fetch_characters(user_id, guild_id)

        if not characters:
            await ctx.respond("Você não possui personagens registrados.", ephemeral=True)
            return

        options = [discord.SelectOption(label=char) for char in characters]
        select_menu = discord.ui.Select(placeholder="Escolha um personagem", options=options)

        async def select_callback(interaction):
            selected_char = select_menu.values[0]

            add_button = discord.ui.Button(label="Adicionar Imagem", style=discord.ButtonStyle.success)
            remove_button = discord.ui.Button(label="Remover Imagem", style=discord.ButtonStyle.danger)
            await char_select_message.delete_original_response()

            async def add_callback(interaction):
                request_message = await interaction.response.send_message(
                    f"Envie uma URL de imagem válida ou anexe uma imagem para associar ao personagem.", 
                    ephemeral=True
                )

                def check(msg):
                    return msg.author == ctx.author and msg.channel == ctx.channel

                timesup_message = None

                try:
                    msg = await self.bot.wait_for("message", timeout=60.0, check=check)

                    image_url = msg.attachments[0].url if msg.attachments else (msg.content.strip() if msg.content.startswith("http") else None)

                    if not image_url:
                        await interaction.followup.send("Nenhuma imagem válida fornecida.", ephemeral=True)
                        return

                    is_valid, message, needs_resize = await self.is_valid_image(image_url)

                    if not is_valid:
                        error_message = await interaction.followup.send(message, ephemeral=True)
                        await msg.delete()
                        await request_message.delete_original_response()
                        if error_message:
                            await asyncio.sleep(5)
                            await error_message.delete()
                        return
                    
                    description = None

                    if not msg.attachments:
                        parts = msg.content.split(maxsplit=1)
                        if len(parts) > 1:
                            description = parts[1].strip()
                    else:
                        description = msg.content.strip()

                    if needs_resize:
                        resized_image = await self.resize_image(image_url)
                        if resized_image:
                            sent_message = await interaction.followup.send(
                                "A imagem foi adicionada com as dimensões de 1024x1024:",
                                file=discord.File(resized_image, filename="resized_image.png"),
                                ephemeral=False
                            )
                    else:
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(image_url) as response:
                                    if response.status != 200:
                                        await interaction.followup.send("Falha ao obter a imagem.", ephemeral=True)
                                        return

                                    original_image_data = await response.read()
                                    buffer = BytesIO(original_image_data)
                                    sent_message = await interaction.followup.send(
                                        "Imagem adicionada:",
                                        file=discord.File(buffer, filename="original_image.png"),
                                        ephemeral=False
                                    )
                        except Exception as e:
                            await interaction.followup.send(f"Falha ao obter a imagem {e}.", ephemeral=True)
                            return

                    image_url = sent_message.attachments[0].url

                    add_images_to_album(selected_char, image_url, description)

                    await request_message.delete_original_response()
                except asyncio.TimeoutError:
                    timesup_message = await interaction.followup.send("Tempo esgotado. Por favor, tente novamente.", ephemeral=True)

                if timesup_message:
                    await asyncio.sleep(5)
                    await timesup_message.delete()

            async def remove_callback(interaction):
                images = pick_character_url_images(selected_char)

                if not images:
                    await interaction.response.send_message(f"Não há imagens associadas ao personagem **{selected_char}**.", ephemeral=True)
                    return

                options = [
                    discord.SelectOption(label=f"Imagem {index + 1}", value=str(index))
                    for index, url in enumerate(images)
                ]
                remove_menu = discord.ui.Select(placeholder="Escolha uma imagem para remover", options=options)

                async def remove_image_callback(interaction):
                    selected_index = int(remove_menu.values[0])
                    selected_url = images[selected_index][0] 

                    remove_image(selected_char, selected_url)

                    image_removed_message = await interaction.response.send_message(f"Imagem removida do personagem **{selected_char}**.", ephemeral=True)
                    await image_choice.delete_original_response()
                    await asyncio.sleep(5)
                    await image_removed_message.delete_original_response()

                remove_menu.callback = remove_image_callback
                view = discord.ui.View()
                view.add_item(remove_menu)
                image_choice = await interaction.response.send_message(f"Escolha uma imagem para remover do personagem **{selected_char}**:", view=view, ephemeral=True)

            add_button.callback = add_callback
            remove_button.callback = remove_callback

            view = discord.ui.View()
            view.add_item(add_button)
            view.add_item(remove_button)

            await interaction.response.send_message(f"Album de **{selected_char}**", view=view, ephemeral=True)

        select_menu.callback = select_callback

        view = discord.ui.View()
        view.add_item(select_menu)

        char_select_message = await ctx.respond("Selecione um personagem para gerenciar as imagens:", view=view, ephemeral=True)

    async def all_characters_autocomplete(ctx: discord.AutocompleteContext):
        guild_id = ctx.interaction.guild_id
        guild = ctx.interaction.guild
        characters = autocomplete_character_with_images(guild_id)
        results = []

        for char_name, user_id in characters:
            member = guild.get_member(user_id)
            if member:
                display_name = member.display_name
                results.append(f"{char_name} ({display_name})")

        return results[:25]

    @commands.slash_command(name="album", description="Veja os albuns existentes no server")
    async def view_images(
        self,
        ctx,
        character_name: discord.Option(str, description="Quer ver o álbum de quem?", autocomplete=all_characters_autocomplete, required=True) #type: ignore
    ):

        if " (" in character_name:
            character_name = character_name.split(" (")[0]

        images = urls_in_row(character_name)

        if not images:
            await ctx.respond(f"O personagem **{character_name}** não possui imagens em seu álbum, adicione com `/manage_album`.", ephemeral=True)
            return

        current_index = 0

        async def show_image(index):
            image_url, added_date, description = images[index]
            added_date = datetime.strptime(added_date, '%Y-%m-%d %H:%M:%S')

            embed = discord.Embed(
                title=f"`{character_name}`",
                color=discord.Color.blue())

            if description:
                embed.description =f"*{description}*"

            embed.add_field(name="", value=f"Adicionada em {added_date.strftime('%d/%m/%Y')}", inline=False)
            embed.set_image(url=image_url)
            embed.set_footer(text=f"{index + 1}/{len(images)}")

            return embed

        await ctx.respond(embed=await show_image(current_index))
        message = await ctx.interaction.original_response()
        await message.add_reaction("◀")
        await message.add_reaction("▶")

        def check(reaction, user):
            return (
                user == ctx.author
                and reaction.message.id == message.id
                and str(reaction.emoji) in ["◀", "▶"]
            )

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)

                if str(reaction.emoji) == "◀":
                    current_index = (current_index - 1) % len(images)
                elif str(reaction.emoji) == "▶":
                    current_index = (current_index + 1) % len(images)

                await message.edit(embed=await show_image(current_index))
                await message.remove_reaction(reaction, user)
            except:
                break

def setup(bot):
    bot.add_cog(ManageImages(bot))
