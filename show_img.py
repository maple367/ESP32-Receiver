# main.py -- put your code here!

from ST7735 import TFT,TFTColor
from machine import SPI,Pin,deepsleep
from font5x8 import FONT

spi = SPI(1, baudrate=20000000, polarity=0, phase=0, sck=Pin(3), mosi=Pin(4))
#  def __init__( self, spi, aDC, aReset, aCS) :
tft=TFT(spi,0,5,2)
tft.initr()
# tft.rgb(True)
tft.fill(TFT.BLACK)

import os

def normal_show_img(fn='test128x160'):
    f = open(fn + '.bmp', 'rb')
    g = open(fn + '.b16', 'wb')
    if f.read(2) == b'BM':  # header
        _ = f.read(8)  # file size(4), creator bytes(4)
        offset  = int.from_bytes(f.read(4), 'little')
        hdrsize = int.from_bytes(f.read(4), 'little')
        width   = int.from_bytes(f.read(4), 'little')
        height  = int.from_bytes(f.read(4), 'little')
        if int.from_bytes(f.read(2), 'little') == 1:  # planes must be 1
            depth = int.from_bytes(f.read(2), 'little')
            comp  = int.from_bytes(f.read(4), 'little')
            if depth == 24 and comp == 0:  # uncompressed
                print("Image size:", width, "x", height)
                rowsize = (width * 3 + 3) & ~3  # BMP 每行4字节对齐
                if height < 0:
                    height = -height
                    flip = False
                else:
                    flip = True
                w, h = width, height
                if w > 128: w = 128
                if h > 128: h = 128
                tft._setwindowloc((0, 0), (w - 1, h - 1))
                # 写 b16 头：小端宽高各2字节（原来 [w,0,h,0] 在 w/h>255 时会错）
                g.write(w.to_bytes(2, 'little'))
                g.write(h.to_bytes(2, 'little'))
                # 行缓冲（16位色：2*w 字节）
                data = bytearray(2 * w)
                for row in range(h):
                    # 计算BMP源行位置（自顶向下 or 自底向上）
                    pos = offset + ((height - 1 - row) * rowsize if flip else row * rowsize)
                    if f.tell() != pos:
                        f.seek(pos)
                    # 读取一整行的 BGR888
                    frow = f.read(3 * width)
                    iy = 0
                    ix = 0
                    for _ in range(w):
                        # BMP是 B,G,R 顺序；TFTColor 需要 R,G,B —— 交换 R/B
                        b = frow[ix]
                        g8 = frow[ix + 1]
                        r = frow[ix + 2]
                        ix += 3
                        # 888 → 565
                        aColor = ((r & 0xF8) << 8) | ((g8 & 0xFC) << 3) | (b >> 3)
                        # 高字节在前（大端顺序），这一句原来就是对的
                        data[iy] = aColor >> 8
                        # 低字节应写 0xFF 掩码，原来用了 and 8（布尔与），导致颜色错
                        data[iy + 1] = aColor & 0xFF
                        iy += 2
                    # 输出到屏幕 & 写入缓存文件
                    tft.dc(1); tft.cs(0)
                    tft.spi.write(data)     # display one row
                    tft.cs(1)
                    g.write(data)           # add row data to the .b16 file
    f.close()
    g.close()


def fast_show_img(fn='test128x160'):
    f=open(fn+'.b16', 'rb')
    w = int.from_bytes(f.read(2), 'little')
    h = int.from_bytes(f.read(2), 'little')
    tft._setwindowloc((0,0),(w - 1,h - 1))
    tft.dc(1)
    tft.cs(0)
    for row in range(h):
        row = f.read(2 * w)
        tft.spi.write(row) # send one row
    tft.cs(1) # display

# fn = 'test128x160'
# force_normal = True
# if fn + '.b16' in os.listdir() and not force_normal:
#     fast_show_img(fn)
# elif fn + '.bmp' in os.listdir():
#     normal_show_img(fn)
# else:
#     # tft.text((10,10),"No image file!",TFT.WHITE,FONT,3)
#     for x in [1, 126]:
#         for y in [1, 126]:
#             tft.fillrect((x-1,y-1),(x+2,y+2),TFT.WHITE)
#             tft.pixel((x,y),TFT.BLACK)
#     # ABCDEFGHIJKLMNOPQRSTUVWXYZ
#     # 1234567890.,!?-+/():;%&`'*#=[]"_<>
#     colors = [TFT.RED, TFT.MAROON, TFT.GREEN, TFT.FOREST, TFT.BLUE, TFT.NAVY, TFT.CYAN, TFT.YELLOW, TFT.PURPLE, TFT.WHITE, TFT.GRAY]
#     texts = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'+'1234567890.,!?-+/():;%&`\'*#=[]"_<>'
#     for i in range(len(texts)):
#         i_color = i % len(colors)
#         x = (i * 16) % 128
#         y = (i * 16) // 128 * 16
#         tft.text((x, y), texts[i], colors[i_color], FONT, 2)
# spi.deinit()
