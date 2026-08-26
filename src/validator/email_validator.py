import re


_EMAIL_FORMAT = re.compile('/^[A-Za-z\d._]+@([A-Za-z\d-]+\.)+[A-Za-z]{2,}$/gm')

def is_valid_email(email : str):
    """Verifica se o email tem o formato correto e se segue o padrão da regex"""
    return re.match(_EMAIL_FORMAT, email)
   