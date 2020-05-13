import tdameritrade, json, pandas, os, datetime, selenium, requests
from tdameritrade import auth

client_id = os.getenv('TDAMERITRADE_CLIENT_ID')
account_id = os.getenv('TDAMERITRADE_ACCOUNT_ID')
redirect_uri = os.getenv('REDIRECT_URL')
# access_token = os.getenv('ACCESS_TOKEN')
# refresh_token = os.getenv('TDAMERITRADE_REFRESH_TOKEN')
#print(redirect_uri+client_id)
#tdameritrade.auth.authentication(client_id,redirect_uri,os.getenv('TDAUSER'), os.getenv('TDAPASS'))
#print(os.getenv['ACCESS_TOKEN'])

def getTokens():
    auth = tdameritrade.auth.authentication(client_id, redirect_uri, os.getenv('TDAUSER'), os.getenv('TDAPASS'))
    os.environ['TDAMERITRADE_REFRESH_TOKEN'] = auth['refresh_token']
    os.environ['ACCESS_TOKEN'] = auth['access_token']


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





#print(auth['refresh_token'])


print(td.optionsDF('JCP'))

