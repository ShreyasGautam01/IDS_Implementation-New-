from __future__ import annotations

from pathlib import Path
import hashlib
from typing import Iterator
import pandas as pd


class DataIOError(RuntimeError):
    pass


def _normalize_column_names(frame: pd.DataFrame, source: Path) -> pd.DataFrame:
    original = [str(column) for column in frame.columns]
    normalized = [column.strip() for column in original]
    if len(normalized) != len(set(normalized)):
        duplicates = sorted({name for name in normalized if normalized.count(name) > 1})
        raise DataIOError(
            f"Column names in {source} collide after trimming whitespace: {duplicates}"
        )
    frame.columns = normalized
    return frame


def load_table(path: str | Path) -> pd.DataFrame:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise DataIOError(f"Dataset file does not exist: {source}")
    suffix = source.suffix.casefold()
    try:
        if suffix in {".parquet", ".pq"}:
            frame = pd.read_parquet(source)
        elif suffix == ".csv" or source.name.casefold().endswith(".csv.gz"):
            frame = pd.read_csv(source, low_memory=False)
        else:
            raise DataIOError(f"Unsupported dataset extension: {source.suffix}")
    except ImportError as exc:
        raise DataIOError(
            "Parquet support requires pyarrow or fastparquet; install project requirements"
        ) from exc
    except DataIOError:
        raise
    except Exception as exc:
        raise DataIOError(f"Could not read {source}: {exc}") from exc
    return _normalize_column_names(frame, source)


def sha256_file(path: str | Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def iter_table_chunks(path: str | Path, batch_rows: int = 250_000) -> Iterator[pd.DataFrame]:
    """Yield normalized CSV/Parquet chunks without materializing the full table.

    CSV is streamed with pandas chunks. Parquet is streamed with PyArrow record
    batches. This helper is used by the transfer sampler; the full temporal
    pipeline intentionally still loads its selected source dataset in memory.
    """
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise DataIOError(f"Dataset file does not exist: {source}")
    if batch_rows <= 0:
        raise DataIOError("batch_rows must be positive")
    suffix = source.suffix.casefold()
    try:
        if suffix == ".csv" or source.name.casefold().endswith(".csv.gz"):
            for chunk in pd.read_csv(source, chunksize=batch_rows, low_memory=False):
                yield _normalize_column_names(chunk, source)
        elif suffix in {".parquet", ".pq"}:
            try:
                import pyarrow.parquet as pq
            except ImportError as exc:
                raise DataIOError("Parquet chunk iteration requires pyarrow") from exc
            parquet = pq.ParquetFile(source)
            for batch in parquet.iter_batches(batch_size=batch_rows, use_threads=True):
                yield _normalize_column_names(batch.to_pandas(), source)
        else:
            raise DataIOError(f"Unsupported dataset extension: {source.suffix}")
    except DataIOError:
        raise
    except Exception as exc:
        raise DataIOError(f"Could not stream {source}: {exc}") from exc
