import datetime
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sb
import requests
import tdameritrade
from bs4 import BeautifulSoup
from scipy.interpolate import interp1d
from tdameritrade import auth
import matplotlib.colors as mcolors

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
    callList = []
    putList = []
    for option in optionsChain:
        expDate = option.expirationDate
        strike = option.strikePrice
        cp = option.expectedPercentChange
        # if cp < 0:
        #     print(cp)
        optionList = [expDate, strike, cp]
        if option.type == 'CALL':
            callList.append(optionList)
        else:
            putList.append(optionList)
    callDF = pd.DataFrame(callList, columns=["Expiration Date", "Strike Price", "Percent Change"])
    putDF = pd.DataFrame(putList, columns=["Expiration Date", "Strike Price", "Percent Change"])

    callDF = callDF.pivot("Strike Price", "Expiration Date", "Percent Change")[::-1]
    putDF = putDF.pivot("Strike Price", "Expiration Date", "Percent Change")[::-1]

    pal = sb.diverging_palette(0, 500, n=5)

    # plt.pcolormesh(putDF, cmap="coolwarm", norm=mcolors.DivergingNorm(0))
    # # sb.heatmap(callDF, norm=DivergingNorm(0),  cmap=pal)
    # plt.yticks(np.arange(0.5, len(callDF.index), 1), callDF.index)
    # plt.xticks(np.arange(0.5, len(callDF.columns), 1), callDF.columns)
    # plt.show()

    pal = sb.diverging_palette(0, 500, sep=1, n=7)
    sb.set(font_scale=.5)
    fig, ax = plt.subplots(figsize=(25, 50))
    plt.subplot(211)
    sb.heatmap(callDF, center=0, cmap=pal)
    plt.subplot(212)
    sb.heatmap(putDF, center=0, cmap=pal)
    plt.show()
    #
    # d1 = datetime.date(day=10, month=5, year=2020)
    # d2 = datetime.date(day=15, month=6, year=2020)
    # d3 = datetime.date(day=20, month=7, year=2020)
    #
    # s1 = 100
    # s2 = 150
    # s3 = 200
    #
    # o1 = [d1, s1, 100]
    # o2 = [d1, s2, 5]
    # o3 = [d1, s3, 20]
    # o4 = [d2, s1, 50]
    # o5 = [d2, s2, 10]
    # o6 = [d2, s3, -45]
    # o7 = [d3, s1, -7]
    # o8 = [d3, s2, -30]
    # o9 = [d3, s3, -100]
    #
    # chain = [o1, o2, o3, o4, o5, o6, o7, o8, o9]
    #
    # df = pd.DataFrame(chain, columns=['Date', 'Strike', 'Value'])
    # df1 = df.pivot("Strike", "Date", "Value")[::-1]


authenticateAndLoad()
# symbol = input("Enter symbol: ").upper().strip()
# price = float(input("Expected price: ").strip())
# eDate = input("on date? (YYYY-MM-DD): ").strip()
# budget = input("What's your budget?[None]: ").strip()
# try:
#     budget = float(budget)
# except:
#     budget = None
symbol = 'SPY'
price = 300
eDate = "2020-05-20"
budget = None

o = loadOptions(symbol, budget=budget)
p = calculateValues(o, price, datetime.date.fromisoformat(eDate))
s = sortChainByProfit(p)
plotOptionsChainProfits(s)
print(s[0],"\n",s[1])

#
# optionIn = td.optionsDF('SPY', fromDate=d.isoformat()).head(1)
# # print(optionIn.columns)
# # print(optionIn['expirationDate'].values[0])
# expDate = str(optionIn['expirationDate'].values[0])
# sym = optionIn['symbol'].values[0]
# option = Option(symbol=sym[:sym.find('_')],
#                 description=optionIn['description'].values[0],
#                 type=optionIn['putCall'].values[0],
#                 strikePrice=optionIn['strikePrice'].values[0],
#                 expirationDate=datetime.date.fromisoformat(expDate[:expDate.find('T')]),
#                 bid=optionIn['bid'].values[0],
#                 ask=optionIn['ask'].values[0],
#                 mark=optionIn['mark'].values[0],
#                 volatility=optionIn['volatility'].values[0],
#                 delta=optionIn['delta'].values[0],
#                 gamma=optionIn['gamma'].values[0],
#                 theta=optionIn['theta'].values[0],
#                 vega=optionIn['vega'].values[0],
#                 rho=optionIn['rho'].values[0],
#                 openInterest=optionIn['openInterest'].values[0],
#                 volume=optionIn['totalVolume'].values[0])
# print(option)
# #print(expDate[:expDate.find('T')])
# d = datetime.date(day=15, month=5, year=2020)
# print(option.getExpectedValue(240, d))
# print(option.expectedPercentChange)
