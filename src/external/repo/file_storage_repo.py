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

    BUCKET_NAME = 'product_images'

    def __init__(self, supabase_client : Client):
        self.supabase_client = supabase_client

    def _build_absolut_path(self, file_path : str):
        return f'{supabase_url}/storage/v1/object/{file_path}'

    def _extract_relative_path(self, absolute_path : str) -> str:
        prefix = f'{supabase_url}/storage/v1/object/{self.BUCKET_NAME}/'
        return absolute_path.removeprefix(prefix)

    async def upload(self, file : UploadFile, client_id):

        content = await file.read()
        input_file = io.BytesIO(content)
        extension = file.filename.split('.')[-1]
        path = f'{client_id}/{uuid4()}.{extension}'

        try:
            response = await run_in_threadpool(
                self.supabase_client.storage.from_(self.BUCKET_NAME).upload,
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
            self.supabase_client.storage.from_(self.BUCKET_NAME).remove([relative_path])

        except Exception as e:
            print("houve um erro ao apagar o ficheiro antigo: ", str(e))
