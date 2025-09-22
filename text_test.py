from machine import SPI,Pin
from ST7735 import TFT
from vga1_16x16 import FONT

spi = SPI(1, baudrate=20000000, polarity=0, phase=0, sck=Pin(3), mosi=Pin(4))
tft=TFT(spi,0,5,2)
tft.initr()
tft.rgb(True)
tft.fill(TFT.BLACK)

tft.text((10,10),"Hello World!",TFT.WHITE,FONT)
