import sqlite3

def get_connection():
    connection = sqlite3.connect("remittance.db")
    return connection