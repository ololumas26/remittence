from src.supabase.server import client
from src.external.repo.file_storage_repo import SupabaseFileStorage
from fastapi import UploadFile
import io


class FileStorageService:

    ALLOWED_FILE_EXTENSION = ['png', 'jpg', 'jpeg', 'pdf']

    def __init__(self, supabase_file_storage : SupabaseFileStorage):
        self.supabase_file_storage = supabase_file_storage

    def _ensure_has_allowed_extension(self, filename : str):

        if filename.split('.')[-1].lower() not in self.ALLOWED_FILE_EXTENSION:
            raise FileNotFoundError(f"Formato do ficheiro incorreto, formatos permitidos, {self.ALLOWED_FILE_EXTENSION}")


    async def execute(self, file : UploadFile, client_id):

        self._ensure_has_allowed_extension(filename=file.filename)
        response = await self.supabase_file_storage.upload(file, client_id)
        return response