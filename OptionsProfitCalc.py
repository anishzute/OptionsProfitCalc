import tdameritrade, json, pandas, os, datetime, selenium, requests
from tdameritrade import auth

client_id = os.getenv('TDAMERITRADE_CLIENT_ID')
account_id = os.getenv('TDAMERITRADE_ACCOUNT_ID')
#refresh_token = os.getenv('TDAMERITRADE_REFRESH_TOKEN')
redirect_uri = os.getenv('REDIRECT_URL')
#print(redirect_uri+client_id)
#tdameritrade.auth.authentication(client_id,redirect_uri,os.getenv('TDAUSER'), os.getenv('TDAPASS'))
auth = tdameritrade.auth.authentication(client_id,redirect_uri,os.getenv('TDAUSER'), os.getenv('TDAPASS'))

os.environ['TDAMERITRADE_REFRESH_TOKEN'] = auth['refresh_token']
os.environ['ACCESS_TOKEN'] = auth['access_token']
td = tdameritrade.TDClient()

print(td.quote('SPY'))
