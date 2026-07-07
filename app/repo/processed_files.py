import logging
from typing import Optional, List, Type

from app.models.database_conn import MyDb
from app.models.kvuno import ProcessedFiles
from app.utils.logging import SharedLogger

shared_logger = SharedLogger(level=logging.DEBUG)


class ProcessedFilesRepo:
    def __init__(self):
        self.logger = shared_logger.get_logger()

    def _get_session(self):
        # Ensure that `MyDb` has been initialized with a Flask app
        self.db = MyDb.get_db()
        return self.db.session

    def get_processed_files(self) -> list[Type[ProcessedFiles]]:
        session = self._get_session()
        try:
            processed_files = session.query(ProcessedFiles).all()
            self.logger.info("Retrieved all processed files")
            return processed_files
        except Exception as e:
            self.logger.error(f"Failed to retrieve processed files: {e}")
            raise

    def add_processed_file(self, processed_file: ProcessedFiles) -> None:
        session = self._get_session()
        try:
            session.add(processed_file)
            session.commit()
            self.logger.info(f"Added processed file with ID: {processed_file.id}")
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to add processed file: {e}")
            raise

    def get_processed_file_by_id(self, record_id: int) -> Optional[ProcessedFiles]:
        session = self._get_session()
        try:
            processed_file = session.query(ProcessedFiles).filter_by(id=record_id).first()
            self.logger.info(f"Retrieved processed file with ID: {record_id}")
            return processed_file
        except Exception as e:
            self.logger.error(f"Failed to retrieve processed file with ID {record_id}: {e}")
            raise

    def get_processed_file_by_checksum(self, checksum: str) -> Optional[ProcessedFiles]:
        session = self._get_session()
        try:
            processed_file = (session.query(ProcessedFiles)
                              .filter_by(check_sum=checksum).first())
            self.logger.info(f"Retrieved processed file with checksum: {checksum}")
            return processed_file
        except Exception as e:
            self.logger.error(f"Failed to retrieve processed file with checksum {checksum}: {e}")
            raise

    def get_processed_file_by_name(self, file_name: str) -> Optional[ProcessedFiles]:
        session = self._get_session()
        try:
            processed_file = session.query(ProcessedFiles).filter_by(file_name=file_name).first()
            self.logger.info(f"Retrieved processed file with name: {file_name}")
            return processed_file
        except Exception as e:
            self.logger.error(f"Failed to retrieve processed file with name {file_name}: {e}")
            raise

    def delete_processed_file(self, processed_file: ProcessedFiles) -> None:
        session = self._get_session()
        try:
            session.delete(processed_file)
            session.commit()
            self.logger.info(f"Deleted processed file with ID: {processed_file.id}")
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to delete processed file with ID {processed_file.id}: {e}")
            raise

    def upsert_offset(self, checksum: str, file_name: str, offset: int) -> None:
        """Create or update the offset for a given checksum using its own transaction."""
        session = self._get_session()
        try:
            existing = session.query(ProcessedFiles).filter_by(check_sum=checksum).first()
            if existing:
                existing.offset = offset
            else:
                session.add(ProcessedFiles(
                    check_sum=checksum,
                    file_name=file_name,
                    offset=offset,
                ))
            session.commit()
            self.logger.info(f"Upserted offset {offset} for checksum {checksum}")
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to upsert offset for checksum {checksum}: {e}")
            raise

    def insert_processed_files(self, processed_files: List[ProcessedFiles]) -> None:
        session = self._get_session()
        try:
            session.add_all(processed_files)
            session.commit()
            self.logger.info(f"Batch inserted {len(processed_files)} processed files")
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to batch insert processed files: {e}")
            raise
