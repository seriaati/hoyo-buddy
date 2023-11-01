import discord
from PIL import Image

from ..bot.translator import Translator

LIGHT_1 = Image.open("hoyo-buddy-assets/assets/check-in/LIGHT_1.png")
LIGHT_2 = Image.open("hoyo-buddy-assets/assets/check-in/LIGHT_2.png")
LIGHT_CHECK = Image.open("hoyo-buddy-assets/assets/check-in/LIGHT_CHECK.png")
LIGHT_MASK = Image.open("hoyo-buddy-assets/assets/check-in/LIGHT_MASK.png")

DARK_1 = Image.open("hoyo-buddy-assets/assets/check-in/DARK_1.png")
DARK_2 = Image.open("hoyo-buddy-assets/assets/check-in/DARK_2.png")
DARK_CHECK = Image.open("hoyo-buddy-assets/assets/check-in/DARK_CHECK.png")
DARK_MASK = Image.open("hoyo-buddy-assets/assets/check-in/DARK_MASK.png")


def draw(locale: discord.Locale, translator: Translator, dark_mode: bool):
    pass
