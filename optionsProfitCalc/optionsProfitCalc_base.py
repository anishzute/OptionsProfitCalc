import datetime
import os
import pandas
import requests
import tdameritrade
from bs4 import BeautifulSoup
from scipy.interpolate import interp1d
from tdameritrade import auth

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
            if((option.mark*100) <= budget):
                optionsChain.append(option)
        else:
            optionsChain.append(option)


        # print(option)
    print("Loading Successful.\n")

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
    print(f"Calculating expected options values for {optionsChain[1].symbol} at {underlyingPrice:.2f} ({cp:+.2f}%) on {expectedDate.isoformat()}...")
    interestRate = getRiskFree()
    profitChain = []
    numOptions = len(optionsChain)
    x = 1
    for option in optionsChain:
        if option.expirationDate > expectedDate or option.expirationDate == expectedDate:
            #print(f'Calculating: {x}/{numOptions}')
            option.getExpectedValue(underlyingPrice, expectedDate, interestRate)
            profitChain.append(option)
        # else:
        #     print(f'Skipped OOB: {x}/{numOptions}')
        x += 1
    print("Calculation Successful.\n")
    return profitChain


def sortChainByProfit(optionsChain):
    print("Sorting options chain by expected profit percentage...")
    sortedOpChain = sorted(optionsChain, key=lambda option: option.expectedPercentChange, reverse=True)
    print("Sorting Successful.\n")
    return sortedOpChain

authenticateAndLoad()
symbol = input("Enter symbol: ").upper().strip()
price = float(input("Expected price: ").strip())
eDate = input("on date? (YYYY-MM-DD): ").strip()
budget = input("What's your budget?[None]: ").strip()
try:
    budget = float(budget)
except:
    budget = None
o = loadOptions(symbol, budget=budget)
p = calculateValues(o, price, datetime.date.fromisoformat(eDate))
s = sortChainByProfit(p)
for i in s:
    print(i)




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
