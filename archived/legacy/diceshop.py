import discord
from discord.ext import commands

class DiceShop(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.dice_skins = [
            {
                "name": "Dado Clássico",
                "description": "Dado padrão, não faz nada demais.",
                "url": "https://i0.wp.com/pawleystudios.com/wp-content/uploads/2020/07/d20-dice-01.png?fit=510%2C510&ssl=1",
                "price": "0"
            },
            {
                "name": "Dado Flamejante",
                "description": "🔥 Brilha em chamas ao rolar!",
                "url": "https://img.freepik.com/vetores-premium/flamejante-em-chamas-queimando-dados-brancos_1056-3128.jpg",
                "price": "10.000"
            },
            {
                "name": "Dado Gélido",
                "description": "❄️ Um dado congelante que reluz azul!",
                "url": "https://diceimages.com/ice-dice.png",
                "price": "15.000"
            }
        ]

    @discord.slash_command(name="dice_skins", description="Obtenha skins para seus dados")
    async def browse_shop(self, interaction: discord.ApplicationContext):
            index = 0

            embed = self.create_embed(index)

            view = DiceShopView(self, index)

            await interaction.response.send_message(embed=embed, view=view)

    def create_embed(self, index: int):
        skin = self.dice_skins[index]
        embed = discord.Embed(
            title="",
            description=f"## {skin['name']}",
            color=discord.Color.blue()
        )
        embed.add_field(name="", value="")
        embed.set_field_at(0, name="", value=skin["description"])
        embed.set_thumbnail(url=skin["url"])
        embed.set_footer(text=f"{index + 1}/{len(self.dice_skins)}")
        return embed

class DiceShopView(discord.ui.View):
    def __init__(self, shop: DiceShop, index: int):
        super().__init__()
        self.shop = shop
        self.index = index

    @discord.ui.button(label="<", style=discord.ButtonStyle.gray)
    async def prev_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.index = (self.index - 1) % len(self.shop.dice_skins)
        await interaction.response.edit_message(embed=self.shop.create_embed(self.index), view=self)

    @discord.ui.button(label=">", style=discord.ButtonStyle.gray)
    async def next_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.index = (self.index + 1) % len(self.shop.dice_skins)
        await interaction.response.edit_message(embed=self.shop.create_embed(self.index), view=self)

    @discord.ui.button(label="Buy 💎 5.000", style=discord.ButtonStyle.green)
    async def buy_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message(f"Você comprou a skin **{self.shop.dice_skins[self.index]['name']}**!", ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(DiceShop(bot))
