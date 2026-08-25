import sqlite3


connect = sqlite3.connect("remittance.db")



try:

    response = connect.execute("""
                    UPDATE document
                    set status = 'APPROVED'
                    where client_id = ?

            """, ('befbb3f69e52460e8006cba7ea513def',))
    connect.commit()

    print("Documento atualizado com sucesso: ", response.lastrowid)
    
except Exception as e:
    print("Algo correu mal ao obter os daos: ", str(e))


finally:
    connect.close()