from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, ConnectionError, ReadTimeoutError


@dataclass
class FileToSync:
    local_path: Path
    s3_key: str


@dataclass
class EngineConfig:
    profile: str
    bucket_name: str
    local_path: Path
    storage_class: str = "STANDARD"
    verify_upload: bool = True
    hash_algorithm: str = "sha256"
    max_retries: int = 3
    retry_delay_base: float = 1.0
    retry_delay_max: float = 60.0
    chunk_size_mb: int = 100
    include_patterns: List[str] = None
    exclude_patterns: List[str] = None
    max_concurrent_uploads: int = 20
    max_concurrent_checks: int = 20


@dataclass
class EngineStats:
    files_uploaded: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    bytes_uploaded: int = 0
    retries_attempted: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    verifications_total: int = 0
    verifications_passed: int = 0


class SyncEngine:
    """Pure sync engine with no UI concerns.

    Emits progress via callbacks so any UI can render consistently.
    """

    def __init__(self, config: EngineConfig, logger: logging.Logger | None = None):
        self.config = config
        self._logger = logger or logging.getLogger("sync-engine")
        self.stats = EngineStats()
        self._stats_lock = threading.Lock()

        self._session = None
        self.s3_client = None
        self.s3_resource = None
        self._setup_aws_clients()

    # ---------- Public high-level API ----------
    def discover_all_files(self) -> List[FileToSync]:
        files: List[FileToSync] = []
        if not self.config.local_path.exists():
            return files
        for p in self.config.local_path.rglob("*"):
            if p.is_file() and self._should_include_file(p):
                key = self._calculate_s3_key(p)
                files.append(FileToSync(local_path=p, s3_key=key))
        return files

    def check_files_to_sync(
        self,
        candidates: List[FileToSync],
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> List[FileToSync]:
        """Return subset of candidates that need upload. Calls on_progress(done, total)."""
        if not candidates:
            return []
        total = len(candidates)
        done = 0

        result: List[FileToSync] = []
        def worker(item: FileToSync):
            nonlocal done
            try:
                if self._should_upload_file(item.local_path, item.s3_key):
                    out = item
                else:
                    out = None
            finally:
                done += 1
                if on_progress:
                    on_progress(done, total)
            return out

        with ThreadPoolExecutor(max_workers=self.config.max_concurrent_checks) as ex:
            for fut in as_completed([ex.submit(worker, it) for it in candidates]):
                r = fut.result()
                if r:
                    result.append(r)
        return result

    def upload_files(
        self,
        files: List[FileToSync],
        on_file_done: Optional[Callable[[FileToSync, bool, int], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        total = len(files)
        completed = 0

        def worker(item: FileToSync):
            nonlocal completed
            local_file = item.local_path
            s3_key = item.s3_key
            try:
                if local_file.stat().st_size <= 100 * 1024 * 1024:
                    ok = self._upload_file_simple(local_file, s3_key)
                else:
                    ok = self._upload_file_multipart(local_file, s3_key)
                if ok and self.config.verify_upload:
                    self.stats.verifications_total += 1
                    if self._verify_upload(local_file, s3_key):
                        self.stats.verifications_passed += 1
                    else:
                        ok = False
                if ok:
                    with self._stats_lock:
                        size = local_file.stat().st_size
                        self.stats.files_uploaded += 1
                        self.stats.bytes_uploaded += size
                else:
                    with self._stats_lock:
                        self.stats.files_failed += 1
                return ok
            finally:
                completed += 1
                if on_file_done:
                    size = 0
                    try:
                        size = local_file.stat().st_size
                    except Exception:
                        size = 0
                    on_file_done(item, ok, size)
                if on_progress:
                    on_progress(completed, total)

        with ThreadPoolExecutor(max_workers=self.config.max_concurrent_uploads) as ex:
            list(as_completed([ex.submit(worker, it) for it in files]))

    # ---------- AWS setup ----------
    def _setup_aws_clients(self):
        try:
            self._session = boto3.Session(profile_name=self.config.profile)
            cfg = Config(connect_timeout=30, read_timeout=60, retries={"max_attempts": 3, "mode": "adaptive"})
            self.s3_client = self._session.client("s3", config=cfg)
            self.s3_resource = self._session.resource("s3")
            self.s3_client.list_buckets()
        except NoCredentialsError as e:
            raise e
        except ClientError as e:
            raise e

    # ---------- Helpers (pure, no UI) ----------
    def _should_include_file(self, file_path: Path) -> bool:
        include = self.config.include_patterns or ["*"]
        exclude = self.config.exclude_patterns or []
        included = any(file_path.match(p) for p in include)
        if not included:
            return False
        if any(file_path.match(p) for p in exclude):
            return False
        return True

    def _calculate_s3_key(self, file_path: Path) -> str:
        try:
            relative = file_path.relative_to(self.config.local_path)
            key = str(relative).replace("\\", "/").lstrip("/")
            return key
        except ValueError:
            abs_file_path = file_path.resolve()
            parts = abs_file_path.parts
            if len(parts) >= 3:
                key = "/".join(parts[-3:])
            else:
                key = file_path.name
            return key.replace("\\", "/").lstrip("/")

    def _get_s3_object_metadata(self, key: str):
        try:
            r = self.s3_client.head_object(Bucket=self.config.bucket_name, Key=key)
            return {"etag": r["ETag"].strip('"'), "size": r["ContentLength"], "last_modified": r["LastModified"]}
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "404":
                return None
            return None

    def _should_upload_file(self, local_file: Path, s3_key: str) -> bool:
        if not local_file.exists():
            return False
        meta = self._get_s3_object_metadata(s3_key)
        if not meta:
            return True
        if local_file.stat().st_size != meta["size"]:
            return True
        etag = meta["etag"]
        if "-" in etag:
            return False
        local_md5 = self._calculate_file_hash(local_file, "md5")
        return bool(local_md5 and local_md5 != etag)

    def _calculate_file_hash(self, file_path: Path, algorithm: str) -> Optional[str]:
        if algorithm == "md5":
            h = hashlib.md5()
        elif algorithm == "sha256":
            h = hashlib.sha256()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.hexdigest()

    def _retry_with_backoff(self, func, *args, **kwargs):
        last = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (ClientError, ConnectionError, ReadTimeoutError) as e:
                last = e
                if attempt == self.config.max_retries:
                    raise last
                delay = min(self.config.retry_delay_base * (2 ** attempt), self.config.retry_delay_max)
                jitter = random.uniform(0, 0.1 * delay)
                time.sleep(delay + jitter)
        raise last

    def _upload_file_simple(self, local_file: Path, s3_key: str) -> bool:
        def op():
            extra = {
                "StorageClass": self.config.storage_class,
                "Metadata": {
                    "original-filename": local_file.name,
                    "upload-timestamp": datetime.now().isoformat(),
                    "hash-algorithm": self.config.hash_algorithm,
                },
            }
            self.s3_client.upload_file(str(local_file), self.config.bucket_name, s3_key, ExtraArgs=extra)
            return True
        return self._retry_with_backoff(op)

    def _upload_file_multipart(self, local_file: Path, s3_key: str) -> bool:
        file_size = local_file.stat().st_size
        chunk_size = self.config.chunk_size_mb * 1024 * 1024

        def create():
            return self.s3_client.create_multipart_upload(
                Bucket=self.config.bucket_name,
                Key=s3_key,
                StorageClass=self.config.storage_class,
                Metadata={
                    "original-filename": local_file.name,
                    "upload-timestamp": datetime.now().isoformat(),
                    "hash-algorithm": self.config.hash_algorithm,
                },
            )

        mpu = self._retry_with_backoff(create)
        parts = []
        part_number = 1
        try:
            with open(local_file, "rb") as f:
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    def upload_part():
                        return self.s3_client.upload_part(
                            Bucket=self.config.bucket_name,
                            Key=s3_key,
                            PartNumber=part_number,
                            UploadId=mpu["UploadId"],
                            Body=data,
                        )
                    r = self._retry_with_backoff(upload_part)
                    parts.append({"ETag": r["ETag"], "PartNumber": part_number})
                    part_number += 1

            def complete():
                return self.s3_client.complete_multipart_upload(
                    Bucket=self.config.bucket_name,
                    Key=s3_key,
                    UploadId=mpu["UploadId"],
                    MultipartUpload={"Parts": parts},
                )
            self._retry_with_backoff(complete)
            return True
        except Exception:
            try:
                self.s3_client.abort_multipart_upload(Bucket=self.config.bucket_name, Key=s3_key, UploadId=mpu["UploadId"])
            except Exception:
                pass
            return False

    def _verify_upload(self, local_file: Path, s3_key: str) -> bool:
        meta = self._get_s3_object_metadata(s3_key)
        if not meta:
            return False
        if local_file.stat().st_size != meta["size"]:
            return False
        if self.config.hash_algorithm == "md5":
            local = self._calculate_file_hash(local_file, "md5")
            if local and local != meta["etag"]:
                return False
        return True


