from abc import ABC, abstractmethod
from supabase import Client
from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool
import io
from src.supabase.server import supabase_url
from uuid import uuid4
from src.exception.exceptions import FileUploadError


class FileStorage(ABC):

    @abstractmethod
    def upload(self, file):
        raise NotImplementedError

    @abstractmethod
    def delete(self, file_path):
        raise NotImplementedError


class SupabaseFileStorage(FileStorage):

    # Omitido no construtor, cai neste bucket — mantém o comportamento de sempre para quem já
    # construía isto sem indicar bucket (ex: documentos de KYC, ver get_document_service).
    BUCKET_NAME = 'product_images'

    def __init__(self, supabase_client : Client, bucket_name : str | None = None):
        self.supabase_client = supabase_client
        self.bucket_name = bucket_name or self.BUCKET_NAME

    def _build_absolut_path(self, file_path : str):
        return f'{supabase_url}/storage/v1/object/{file_path}'

    def _extract_relative_path(self, absolute_path : str) -> str:
        prefix = f'{supabase_url}/storage/v1/object/{self.bucket_name}/'
        return absolute_path.removeprefix(prefix)

    async def upload(self, file : UploadFile, client_id):

        content = await file.read()
        input_file = io.BytesIO(content)
        extension = file.filename.split('.')[-1]
        path = f'{client_id}/{uuid4()}.{extension}'

        try:
            response = await run_in_threadpool(
                self.supabase_client.storage.from_(self.bucket_name).upload,
                path,
                input_file.getvalue(),
            )
            return self._build_absolut_path(response.full_path)

        except Exception as e:
            print("houve um erro ao submeter o ficheiro: ", str(e))
            raise FileUploadError("Não foi possível submeter o ficheiro. Tenta novamente.") from e

    def delete(self, file_path : str):
       
        try:
            relative_path = self._extract_relative_path(file_path)
            self.supabase_client.storage.from_(self.bucket_name).remove([relative_path])

        except Exception as e:
            print("houve um erro ao apagar o ficheiro antigo: ", str(e))

    def get_signed_url(self, file_path : str, expires_in : int = 300) -> str:
        # Documentos de KYC (BI/passaporte/comprovativo) não podem depender do bucket estar
        # público — geramos sempre um link assinado e de curta duração, usando o cliente admin
        # (service role) que este storage já recebe, para funcionar independentemente da
        # política do bucket.
        relative_path = self._extract_relative_path(file_path)

        try:
            response = self.supabase_client.storage.from_(self.bucket_name).create_signed_url(
                relative_path, expires_in,
            )
            return response['signedUrl']

        except Exception as e:
            print("houve um erro ao gerar o link do ficheiro: ", str(e))
            raise FileUploadError("Não foi possível gerar o link do ficheiro. Tenta novamente.") from e
