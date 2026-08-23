from src.service.client_service import ClientService
from src.repository.client_repository import SqlClientRepository
from src.database.db import session_DP
from src.dto.client_dto import CreateClient
import pytest
from src.exception.exceptions import UnderageClientError
from datetime import date, timedelta
from src.service.age_calculator import get_current_date


def fake_birthday():

    current_date = get_current_date()
    year = current_date.year - 18

    return {
        'tomorrow': date(year=year, month=current_date.month, day=current_date.day) + timedelta(days=1),
        'today':  date(year=year, month=current_date.month, day=current_date.day),
        'yesterday' :  date(year=year, month=current_date.month, day=current_date.day) + timedelta(days=-1)
    }


class TestClientService:

    def test_cliente_faz_18_anos_hoje_deve_ser_criado(self):

        birth_date = fake_birthday()['today'] 
        client_service = ClientService(SqlClientRepository(session_DP))
        client_service.create(CreateClient(name="Eliseu", email='eliseu@example.com', phone_number="999999",
                        birth_date=birth_date))


    def test_clientw_faz_18_anos_amanha_nao_deve_passar(self):

        with pytest.raises(UnderageClientError):
            birth_date = fake_birthday()['tomorrow'] 
            client_service = ClientService(SqlClientRepository(session_DP))
            client_service.create(CreateClient(name="Eliseu", email='eliseu@example.com', phone_number="999999",
                            birth_date=birth_date))

    def cliente_fez_anos_ontem_deve_passar(self):

        birth_date = fake_birthday()['yesterday'] 
        client_service = ClientService(SqlClientRepository(session_DP))
        client_service.create(CreateClient(name="Eliseu", email='eliseu@example.com', phone_number="999999",
                        birth_date=birth_date))


        # TODO: Aprender a criar mocks de dados para escrever testes de integração 
        # CRIAR UMA BASE DE DADOS FAKE PARA NÃO POLUIR A BASE DE DADOS PRINCIPAL.