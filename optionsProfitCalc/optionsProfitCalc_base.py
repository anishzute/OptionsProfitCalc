import datetime
import os
import pandas
import tdameritrade
from tdameritrade import auth

# from optionsProfitCalc.option.option_object import Option
from optionsProfitCalc.option.option_object import Option

client_id = os.getenv('TDAMERITRADE_CLIENT_ID')
account_id = os.getenv('TDAMERITRADE_ACCOUNT_ID')
redirect_uri = os.getenv('REDIRECT_URL')


def getTokens():
    if os.getenv('TDAUSER') is None or os.getenv('TDAPASS') is None:
        auth = tdameritrade.auth.authentication(client_id, redirect_uri)
    else:
        auth = tdameritrade.auth.authentication(client_id, redirect_uri, os.getenv('TDAUSER'), os.getenv('TDAPASS'))
    os.environ['TDAMERITRADE_REFRESH_TOKEN'] = auth['refresh_token']
    os.environ['ACCESS_TOKEN'] = auth['access_token']


def authenticateAndLoad():
    try:
        td = tdameritrade.TDClient()
        td.quote('SPY')
    except tdameritrade.exceptions.InvalidAuthToken:
        print("Token Expire: Getting new token.")
        getTokens()
        td = tdameritrade.TDClient()
    except KeyError:
        print('Keyerror passed')
        getTokens()
        td = tdameritrade.TDClient()
    return td


def loadOptions(symbol, fromDate=None, opType='ALL', expectedUnderlying=None, expectedDate=None):
    optionsChain = []
    td = authenticateAndLoad()
    optionsDF = td.optionsDF(symbol, fromDate=fromDate.isoformat(), contractType=opType)
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
                        volume=optionIn['totalVolume'])
        optionsChain.append(option)
        #print(option)

    return optionsChain


def calculateValues(optionsChain, underlyingPrice, expectedDate):
    profitChain = []
    # for option in optionsChain:
    #     option.getExpectedValue(underlyingPrice, expectedDate)
    #     profitChain.append(option)
    #     print(option)
    option = optionsChain[30]
    print(option)
    option.getExpectedValue(underlyingPrice, expectedDate)
    return profitChain


o = loadOptions('SPY', datetime.date(day=20, month=5, year=2020))
p = calculateValues(o, 250, datetime.date(day=15, month=5, year=2020))

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
