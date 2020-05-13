class Option:
    symbol = ''
    description = 'description'
    type = 'putCall'
    strikePrice =  'strikePrice'
    expirationDate = ''
    bid =  'bid'
    ask =  'ask'
    mark =  'mark'
    DTE =  'daysToExpiration'
    volatility =  50
    delta =  'delta'
    gamma =  'gamma'
    theta =  'theta'
    vega =  'vega'
    rho =  'rho'
    openInterest =  'openInterest'
    volume =  'totalVolume'
    expectedDTE = ''
    expectedValue = ''
    expectedPercentageChange = ''
    
    def __init__(self, symbol=None, description = None, type = None, strikePrice = None, expirationDate = None, bid = None,
                 ask = None, mark =None, DTE = None, volatility = None, delta = None, gamma = None, theta = None, vega = None,
                 rho = None, openInterest = None, volume = None, expectedDTE = None, expectedValue = None, expectedPercentChange = None):
        self.symbol = symbol
        self.


