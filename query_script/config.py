import requests
import talib
import pandas as pd
import numpy as np
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import mpl_finance as mpl
import datetime
from mplfinance.original_flavor import candlestick_ohlc

my_red = (192/255, 28/255, 29/255)
my_green = (13/255, 119/255, 9/255)
my_white = (48/255, 48/255, 48/255)
my_black = (31/255, 31/255, 31/255)

np.seterr(invalid='ignore', divide='ignore')
plt.rcParams['axes.unicode_minus'] = False

# initializations