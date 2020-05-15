import datetime
from datetime import timedelta

import py_lets_be_rational
import requests
from bs4 import BeautifulSoup
from scipy.interpolate import interp1d
from scipy.stats import norm
from scipy.optimize import fsolve
import tdameritrade
import mibian
import py_vollib
from py_vollib import black
from py_vollib.black_scholes import implied_volatility
from py_vollib.black import implied_volatility

TREASURY_URL = "http://www.treasury.gov/resource-center/data-chart-center/interest-rates/Pages/TextView.aspx?data=yield"
OVERNIGHT_RATE = 0
FALLBACK_RISK_FREE_RATE = 0.02
FALLBACK_VOLATILITY = 0.01


class Option:

    def __init__(self, symbol=None, description=None, type=None, strikePrice=None, expirationDate=None, bid=None,
                 ask=None, mark=None, DTE=None, volatility=None, delta=None, gamma=None, theta=None, vega=None,
                 rho=None, openInterest=None, volume=None, expectedDTE=None, expectedValue=None,
                 expectedVolatility=None, underlyingMark=None, underlyingExpected=None, underlyingCP=None):
        self.symbol = symbol
        self.description = description
        self.type = type
        self.strikePrice = strikePrice
        self.expirationDate = expirationDate
        self.bid = bid
        self.ask = ask
        self.mark = mark
        self.DTE = DTE
        self.volatility = volatility/100
        self.delta = delta
        self.gamma = gamma
        self.theta = theta
        self.vega = vega
        self.rho = rho
        self.openInterest = openInterest
        self.volume = volume
        self.expectedDTE = expectedDTE
        self.expectedValue = expectedValue
        self.expectedPercentChange = None
        if self.expectedValue is not None and self.expectedDTE is not None:
            self.expectedPercentChange = self.calculateCP(self.mark, self.expectedValue)
        self.expectedVolatility = expectedVolatility
        self.underlyingMark = underlyingMark
        self.underlyingExpected = underlyingExpected
        self.underlyingCP = underlyingCP
        self.volPerm = volatility

    def calculateDTE(self, date):
        dte = self.expirationDate - date
        return dte.days

    def setExpectedValue(self, expectedValue=None, expectedVolatility=None):
        if expectedValue is not None:
            self.expectedValue = expectedValue
        if expectedVolatility is not None:
            self.expectedVolatility = expectedVolatility
        self.expectedPercentChange = (self.expectedValue - self.mark) / self.mark * 100

    def calculateCP(self, start, end):
        return (end - start) / start * 100

    def getExpectedValue(self, underlyingPrice, expectedDate, riskFreeLamda):
        # tdc = tdameritrade.TDClient()
        # toDate = self.expirationDate + timedelta(days=1)
        self.underlyingExpected = underlyingPrice
        self.underlyingCP = self.calculateCP(self.underlyingMark, self.underlyingExpected)
        self.expectedDTE = self.calculateDTE(expectedDate)
        interestRate = riskFreeLamda(self.expectedDTE / 30.5 / 12) / 100
        # print(interestRate)
        # option = tdc.optionsDF(strategy='ANALYTICAL',
        #                        symbol=self.symbol,
        #                        contractType=self.type,
        #                        strike=self.strikePrice,
        #                        fromDate=self.expirationDate.isoformat(),
        #                        toDate=toDate.isoformat(),
        #                        volatility=self.volatility,
        #                        underlyingPrice=underlyingPrice,
        #                        # interestRate=interestRate(dteMonth),
        #                        daysToExpiration=int(self.expectedDTE)
        #                        )
        # # print(option)
        # self.setExpectedValue(option['theoreticalOptionValue'].values[0], option['theoreticalVolatility'].values[0])
        # print("TD Value: " + str(self.expectedValue))
        #
        # self.expectedDTE = self.calculateDTE(expectedDate)
        # calculated = mibian.BS(
        #     [underlyingPrice, self.strikePrice, self.getRiskFree()(self.expectedDTE / 12), self.expectedDTE],
        #     volatility=self.volatility)
        # if self.type == 'CALL':
        #     self.setExpectedValue(expectedValue=calculated.callPrice, expectedVolatility=calculated.impliedVolatility)
        # elif self.type == 'PUT':
        #     self.setExpectedValue(calculated.putPrice, expectedVolatility=calculated.impliedVolatility)
        # else:
        #     print("Option type not recognized")
        #
        # print("Mibian Value: " + str(self.expectedValue))
        eVal = 0.0
        if self.type == 'CALL':
            flag = 'c'
        elif self.type == 'PUT':
            flag = 'p'
        else:
            print("Option type not recognized")
        eVal = py_vollib.black_scholes.black_scholes(flag=flag, S=underlyingPrice, K=self.strikePrice,
                                                     t=self.expectedDTE / 365, r=interestRate, sigma=self.volatility)
        self.setExpectedValue(expectedValue=eVal)
        # print("Vollib Value: " + str(self.expectedValue))

        return self.expectedValue

    def getRiskFree(self):
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
            return interp1d(years, rates, fill_value="extrapolate")
        # If scraping treasury data fails use the constant fallback risk free rate
        except Exception:
            print('Exception getting current risk free rate: using default.')
            return lambda x: FALLBACK_RISK_FREE_RATE

    def getIV(self, interest):
        if self.type == 'CALL':
            flag = 'c'
        elif self.type == 'PUT':
            flag = 'p'
        else:
            print("type error.")
        try:
            iv = py_vollib.black_scholes.implied_volatility.implied_volatility(price=self.mark, K=self.strikePrice,
                                                                               t=self.expectedDTE / 365, r=interest,
                                                                               flag=flag, S=self.underlyingMark)
            # print(f"Successful IV Calc!: {iv}")
        except:
            iv = FALLBACK_VOLATILITY
        return iv

    def __str__(self):
        # return "Option: " + self.description + " Value: " + str(self.mark) + " Expected Value: " \
        #        + str(self.expectedValue) + " Option Percent Change: " + str(self.expectedPercentChange) \
        #        + " Eq Percent Change: " + str(self.underlyingCP)

        return f'Option: {self.description:40} Value: {self.mark:6.2f} Expected Value: {self.expectedValue:6.2f} ' \
               f'Percent Change: {self.expectedPercentChange:8.2f}       Volume: {self.volume} Volatility: ' \
               f'{self.volatility}'
