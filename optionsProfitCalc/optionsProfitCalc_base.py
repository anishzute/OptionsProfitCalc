import datetime
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.units as munits
import numpy as np
import seaborn as sb
import requests
import tdameritrade
from bs4 import BeautifulSoup
from scipy.interpolate import interp1d
from tdameritrade import auth
import matplotlib.colors as mcolors
from mpldatacursor import datacursor
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from mpl_toolkits.axes_grid1.axes_divider import make_axes_locatable

# from optionsProfitCalc.option.option_object import Option
from optionsProfitCalc.option.option_object import Option

client_id = os.getenv('TDAMERITRADE_CLIENT_ID')
account_id = os.getenv('TDAMERITRADE_ACCOUNT_ID')
redirect_uri = os.getenv('REDIRECT_URL')
TREASURY_URL = "http://www.treasury.gov/resource-center/data-chart-center/interest-rates/Pages/TextView.aspx?data=yield"
OVERNIGHT_RATE = 0
FALLBACK_RISK_FREE_RATE = 0.02


def getTokens():
    if os.getenv('TDAUSER') is None or os.getenv('TDAPASS') is None:
        auth = tdameritrade.auth.authentication(client_id, redirect_uri)
    else:
        auth = tdameritrade.auth.authentication(client_id, redirect_uri, os.getenv('TDAUSER'), os.getenv('TDAPASS'))
    os.environ['TDAMERITRADE_REFRESH_TOKEN'] = auth['refresh_token']
    os.environ['ACCESS_TOKEN'] = auth['access_token']


def authenticateAndLoad():
    print("Authenticating with TDAmeritrade...")
    try:
        td = tdameritrade.TDClient()
        td.quote('SPY')
    except tdameritrade.exceptions.InvalidAuthToken:
        print("Token Expired: Getting new token.")
        getTokens()
        td = tdameritrade.TDClient()
    except KeyError:
        print('Invalid Auth Token. Getting new Token.')
        getTokens()
        td = tdameritrade.TDClient()
    print("\n")
    return td


def loadOptions(symbol, fromDate=None, opType='ALL', budget=None):
    optionsChain = []
    td = authenticateAndLoad()
    eqQuote = td.quoteDF(symbol)
    # print("Current " + symbol + " price: " + str(eqQuote['mark'].values[0]))
    print(f"Current {symbol} price: {eqQuote['mark'].values[0]:.2f}")
    # print("Loading " + symbol + " options from TDAmeritrade.")
    if budget is not None:
        print(f"Loading {symbol} options from TDAmeritrade... (Max contract price: {budget / 100:.2f})")
    else:
        print(f"Loading {symbol} options from TDAmeritrade...")

    if fromDate is not None:
        optionsDF = td.optionsDF(symbol, fromDate=fromDate.isoformat(), contractType=opType)
    else:
        optionsDF = td.optionsDF(symbol, contractType=opType)

    for index, row in optionsDF.iterrows():
        optionIn = row
        expDate = str(optionIn['expirationDate'])
        sym = optionIn['symbol']
        # print(optionIn['description'])
        option = Option(symbol=sym[:sym.find('_')],
                        description=optionIn['description'],
                        type=optionIn['putCall'],
                        strikePrice=optionIn['strikePrice'],
                        expirationDate=datetime.date.fromisoformat(expDate[:expDate.find(' ')]),
                        bid=optionIn['bid'],
                        ask=optionIn['ask'],
                        mark=optionIn['mark'],
                        volatility=optionIn['volatility'],
                        delta=optionIn['delta'],
                        gamma=optionIn['gamma'],
                        theta=optionIn['theta'],
                        vega=optionIn['vega'],
                        rho=optionIn['rho'],
                        openInterest=optionIn['openInterest'],
                        volume=optionIn['totalVolume'],
                        underlyingMark=eqQuote['mark'].values[0])
        if budget is not None:
            if ((option.mark * 100) <= budget):
                optionsChain.append(option)
        else:
            optionsChain.append(option)

        # print(option)

    print("Loading Successful.\n")
    optionsChain = removeDuplicateOptions(optionsChain)
    return optionsChain


def getRiskFree():
    ####adapted from wallstreet by Mike Dallas @mcdallas used under MIT License
    try:
        r = requests.get(TREASURY_URL)
        soup = BeautifulSoup(r.text, 'html.parser')

        table = soup.find("table", attrs={'class': 't-chart'})
        rows = table.find_all('tr')
        lastrow = len(rows) - 1
        cells = rows[lastrow].find_all("td")
        date = cells[0].get_text()
        m1 = float(cells[1].get_text())
        m2 = float(cells[2].get_text())
        m3 = float(cells[3].get_text())
        m6 = float(cells[4].get_text())
        y1 = float(cells[5].get_text())
        y2 = float(cells[6].get_text())
        y3 = float(cells[7].get_text())
        y5 = float(cells[8].get_text())
        y7 = float(cells[9].get_text())
        y10 = float(cells[10].get_text())
        y20 = float(cells[11].get_text())
        y30 = float(cells[12].get_text())

        years = (0, 1 / 12, 2 / 12, 3 / 12, 6 / 12, 1, 2, 3, 5, 7, 10, 20, 30)
        rates = (OVERNIGHT_RATE, m1, m2, m3, m6, y1, y2, y3, y5, y7, y10, y20, y30)
        # print(years, rates)
        return interp1d(years, rates)
    # If scraping treasury data fails use the constant fallback risk free rate
    except Exception:
        print('Exception getting current risk free rate: using default.')
        return lambda x: FALLBACK_RISK_FREE_RATE


def calculateValues(optionsChain, underlyingPrice, expectedDate):
    cp = optionsChain[0].calculateCP(optionsChain[0].underlyingMark, underlyingPrice)
    print(
        f"Calculating expected options values for {optionsChain[1].symbol} at {underlyingPrice:.2f} ({cp:+.2f}%) on {expectedDate.isoformat()}...")
    interestRate = getRiskFree()
    profitChain = []
    numOptions = len(optionsChain)
    x = 1
    for option in optionsChain:
        if option.expirationDate > expectedDate or option.expirationDate == expectedDate:
            # print(f'Calculating: {x}/{numOptions}')
            option.getExpectedValue(underlyingPrice, expectedDate, interestRate)
            profitChain.append(option)
        # else:
        #     print(f'Skipped OOB: {x}/{numOptions}')
        x += 1
    print("Calculation Successful.\n")
    return profitChain


def removeDuplicateOptions(optionsChain):
    print("Removing duplicates in chain...")
    sChain = sorted(optionsChain, key=lambda option: option.strikePrice)
    newChain = []
    lastStrike = 0
    lastDate = datetime.date.today()
    type = ''
    for option in sChain:
        if option.expirationDate == lastDate and option.strikePrice == lastStrike and option.type == type:
            print("Removing found duplicate.")
        else:
            newChain.append(option)
        lastDate = option.expirationDate
        lastStrike = option.strikePrice
        type = option.type
    return newChain


def sortChainByProfit(optionsChain):
    print("Sorting options chain by expected profit percentage...")
    sortedOpChain = sorted(optionsChain, key=lambda option: option.expectedPercentChange, reverse=True)
    print("Sorting Successful.\n")
    return sortedOpChain


def plotOptionsChainProfits(optionsChain):
    print("Creating options profits plot...")
    minVol = 0
    callList = []
    putList = []
    for option in optionsChain:
        expDate = option.expirationDate
        strike = option.strikePrice
        cp = option.expectedPercentChange
        vol = option.volume
        # if cp < 0:
        #     print(cp)
        if vol >= minVol:
            optionList = [datetime.datetime.combine(expDate, datetime.time()), strike, cp]
            if option.type == 'CALL':
                callList.append(optionList)
            else:
                putList.append(optionList)

    callax = makePlot(callList)
    putax = makePlot(putList)
    # if len(callax) > len(putax):
    #     cols = len(callax)
    # else:
    #     cols = len(putax)
    # fig, axs = plt.subplots(2, cols)
    # x=1
    # for ax in callax:
    #     fig.add_subplot(1,x,x)
    #
    # # callax.title("Calls")
    plt.show()



def makePlot(optionsList):
    pal = sb.diverging_palette(0, 500, sep=1, n=9)
    max = optionsList[0][2]
    print(max)
    sb.set(font_scale=1)
    df = pd.DataFrame(optionsList, columns=["Expiration Date", "Strike Price", "Percent Change"])
    df = df.sort_values('Expiration Date')
    years = df['Expiration Date'].dt.year.unique()
    print(years)
    dfs = []
    for year in years:
        dfx = df[df['Expiration Date'].dt.year == year]
        dfxpivot = dfx.pivot("Strike Price", "Expiration Date", "Percent Change")[::-1]
        dfxpivot.columns = dfxpivot.columns.strftime('%m-%d')
        dfs.append(dfxpivot)

    fig, axs = plt.subplots(1, len(years), figsize=(16,9), gridspec_kw={'hspace': 0, 'wspace': .25})

    x = 0
    for year in years:
        if x == len(years) - 1:
            cbar = True
        else:
            cbar = False
        sb.set(font_scale=.5)
        if x != 0:
            xSpace = 1
        else:
            xSpace = 2

        # axins1 = inset_axes(axs[x],
        #                     width="100%",  # width = 50% of parent_bbox width
        #                     height="5%",  # height : 5%
        #                     loc='upper center',
        #                     bbox_to_anchor=(0,-1, 1, 1),
        #                     bbox_transform=axs[x].transAxes,
        #                     borderpad=0,
        #                     )
        ax_divider = make_axes_locatable(axs[x])
        cax = ax_divider.append_axes("top", size="7%", pad="2%")
        sb.heatmap(dfs[x],
                   fmt=".0f",
                   center=0,
                   cmap=pal,
                   ax=axs[x],
                   annot=False,
                   annot_kws={"size": 3},
                   cbar=True,
                   cbar_ax=cax,
                   cbar_kws=dict(orientation='horizontal'),
                   xticklabels='auto',
                   yticklabels='auto',
                   robust=True,
                   # vmax=max,
                   # vmin=-90
                   )
        cax.xaxis.set_ticks_position("top")
        axs[x].set_xlabel(str(year))
        axs[x].yaxis.set_tick_params(rotation=0)
        axs[x].xaxis.set_tick_params(rotation=45)
        if x != 0:
            axs[x].set_ylabel('')
        x += 1

    plt.gcf().subplots_adjust(bottom=0.25)
    datacursor(display='single', xytext=(15,-15), bbox=dict(fc='white'))
    return axs


    #
    # fig, (ax, ax1, ax2) = plt.subplots(1, 3)
    #
    # sb.heatmap(pivot1, fmt=".0f", center=0, cmap=pal, ax=ax, robust=True, annot=False, annot_kws={"size": 3}, cbar=False)
    # ax.xlabel(year)
    # ax.yaxis.set_tick_params(rotation=0)
    # ax.xaxis.set_tick_params(rotation=45)
    # sb.heatmap(pivot2, fmt=".0f", center=0, cmap=pal, ax=ax1, robust=True, annot=True, annot_kws={"size": 3}, cbar=False)
    # ax1.yaxis.set_tick_params(rotation=0)
    # ax1.xaxis.set_tick_params(rotation=45)
    # sb.heatmap(pivot3, fmt=".0f", center=0, cmap=pal, ax=ax2, robust=True, annot=True, annot_kws={"size": 3}, cbar=True)
    # ax2.yaxis.set_tick_params(rotation=0)
    # ax2.xaxis.set_tick_params(rotation=45)
    #
    # fig.autofmt_xdate()
    # # ax.yaxis.
    # # ax.fmt_xdata = mdates.DateFormatter('%m-%d-%y')
    # # plt.tight_layout()
    #
    #
    # plt.show()


authenticateAndLoad()
# symbol = input("Enter symbol: ").upper().strip()
# price = float(input("Expected price: ").strip())
# eDate = input("on date? (YYYY-MM-DD): ").strip()
# budget = input("What's your budget?[None]: ").strip()
# try:
#     budget = float(budget)
# except:
#     budget = None
symbol = 'TSLA'
price = 700
eDate = "2020-05-20"
budget = 5000

o = loadOptions(symbol, budget=budget)
p = calculateValues(o, price, datetime.date.fromisoformat(eDate))
s = sortChainByProfit(p)
plotOptionsChainProfits(s)
