from src.supabase.server import client
from src.external.repo.file_storage_repo import SupabaseFileStorage
from src.exception.exceptions import InvalidFileError
from fastapi import UploadFile
import io


class FileStorageService:

    ALLOWED_FILE_EXTENSION = ['png', 'jpg', 'jpeg', 'pdf']

    # 10 MB — suficiente para uma foto/scan de documento de identificação ou um PDF de poucas
    # páginas, sem deixar margem para um upload desproporcionado (abuso de armazenamento/banda
    # no Supabase Storage, ou o pedido a ficar preso demasiado tempo no threadpool).
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

    # Assinaturas (magic bytes) dos formatos permitidos. A extensão do nome do ficheiro é
    # controlada inteiramente pelo cliente e não prova nada sobre o conteúdo real — isto valida
    # os primeiros bytes do próprio ficheiro, para um .jpg não poder ser, por exemplo, um
    # executável ou HTML disfarçado.
    _SIGNATURES_BY_EXTENSION = {
        'png': (b'\x89PNG\r\n\x1a\n',),
        'jpg': (b'\xff\xd8\xff',),
        'jpeg': (b'\xff\xd8\xff',),
        'pdf': (b'%PDF-',),
    }

    def __init__(self, supabase_file_storage : SupabaseFileStorage):
        self.supabase_file_storage = supabase_file_storage

    def _ensure_has_allowed_extension(self, filename : str) -> str:
        extension = filename.split('.')[-1].lower()

        if extension not in self.ALLOWED_FILE_EXTENSION:
            raise InvalidFileError(
                f"Formato do ficheiro incorreto, formatos permitidos: {self.ALLOWED_FILE_EXTENSION}"
            )

        return extension

    def _ensure_within_size_limit(self, content : bytes):
        if len(content) > self.MAX_FILE_SIZE_BYTES:
            max_mb = self.MAX_FILE_SIZE_BYTES // (1024 * 1024)
            raise InvalidFileError(f"O ficheiro excede o tamanho máximo permitido de {max_mb}MB.")

    def _ensure_matches_signature(self, content : bytes, extension : str):
        signatures = self._SIGNATURES_BY_EXTENSION[extension]

        if not any(content.startswith(signature) for signature in signatures):
            raise InvalidFileError(
                "O conteúdo do ficheiro não corresponde ao formato indicado pela extensão."
            )

    async def execute(self, file : UploadFile, client_id):

        extension = self._ensure_has_allowed_extension(filename=file.filename)

        content = await file.read()
        self._ensure_within_size_limit(content)
        self._ensure_matches_signature(content, extension)

        # O conteúdo já foi consumido para validação — repõe o cursor no início para quem lê o
        # ficheiro a seguir (SupabaseFileStorage.upload) receber o ficheiro completo, não vazio.
        await file.seek(0)

        response = await self.supabase_file_storage.upload(file, client_id)
        return response

    def delete_previous(self, file_path : str):
        self.supabase_file_storage.delete(file_path)