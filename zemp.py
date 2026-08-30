import sqlite3
from base64 import standard_b64encode, urlsafe_b64encode, urlsafe_b64decode
import hmac
import hashlib

connect = sqlite3.connect("remittance.db")



try:

    response = connect.execute("""
                    UPDATE document
                    set status = 'APPROVED'
                    where client_id = ?

            """, ('436e85c40a4e43978bae06c8c90bdfec',))
    connect.commit()

    print("Documento atualizado com sucesso: ", response.lastrowid)
    
except Exception as e:
    print("Algo correu mal ao obter os daos: ", str(e))


finally:
    connect.close()


import json


# Passos para criação de um jwt token
# 1 : Converter um dicionário em json
# 2 : Converter o json para bytes
# 3 : Converter os bytes em base46Url
# 4 : Voltar a transformar em string


def to_json(data : dict):
    return json.dumps(data)

def to_bytes(data : str):
    return data.encode(encoding='UTF-8')

def to_base64_encode_url(data : bytes):
    return urlsafe_b64encode(data).decode().replace("=", '')

def access_token(message : str, signature : str ):
    return message + '.' + signature

def _hmac(secret : str, message : str):
    signature = to_base64_encode_url(hmac.new(to_bytes(secret), to_bytes(message), digestmod=hashlib.sha256).digest())
    return signature

def decode_to_dict(data : str):
    decoded = urlsafe_b64decode(data).decode()
    return json.loads(decoded)

def rebuild_padding(data : str):
    remaining = len(data) % 4
    match(remaining):
        case 0:
            return data
        case 2:
            return data + '=='
        case 3:
            return data + '='
        case _:
            raise ValueError("Dado inválido ou mal formado.")


def decode_token(token : str, secret : str):

    header, payload, signature = token.split('.')
   
    message = header + '.' + payload
    signature_from_token = signature
    signature = _hmac(secret=secret, message=message)

    result = hmac.compare_digest(to_bytes(signature), to_bytes(signature_from_token))

    if not result:
        return 'Not Authorized' # depois um erro mais adequado.


    return decode_to_dict(rebuild_padding(payload))

    
secret = "24ccfc30-9fb7-44a5-b91f-96a70221da11"
encoded_header = to_base64_encode_url(to_bytes(to_json({'alg': 'HS256', 'typ': 'jwt'})))
encoded_payload = to_base64_encode_url(to_bytes(to_json({'user_id': 10, 'role': 'user'})))
message = encoded_header + "." + encoded_payload
signature = _hmac(secret, message)







# secret = "olamundoesseeomeuprimeitotextede"


# secret_encoded = secret.encode()
# cleaned = urlsafe_b64encode(secret_encoded).decode().replace("=", '')
# print(urlsafe_b64encode(cleaned.encode()))





# sign_and_get_token(header, payload, secret)









# partial_token = f'{header}.{payload}'
# print("Partial: ", partial_token)

# texto = [b for b in "Olá".encode(encoding='UTF-8')]
# aux = ''
# for b in texto:
#     aux+= hex(b)

# print("Em hexadecimal: ", aux)
# print('Olá'.encode().hex())
# print('hello'.encode().hex())

# algo = hex(texto)


# print("Bytes do payload: ",urlsafe_b64encode((payload.encode('UTF-8'))))