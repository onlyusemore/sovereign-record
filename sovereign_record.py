"""Signed, append-only record ledger: inference-time binding, chain
immutability, monotonic sequencing."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Literal, Optional


class LedgerError(Exception): pass
class VerificationError(LedgerError): pass
class SequenceError(LedgerError): pass
class PersistenceError(LedgerError): pass


def canonical_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def chain_hash(prev_chain: bytes, record_bytes: bytes) -> bytes:
    h = hashlib.sha256()
    h.update(prev_chain)
    h.update(record_bytes)
    return h.digest()


GENESIS_CHAIN = b"\x00" * 32
ReasoningState = Literal["PRESENT", "ABSENT"]


@dataclass(frozen=True)
class Step:
    source: str
    content: str


@dataclass(frozen=True)
class Record:
    seq: int
    token: str
    output: str
    reasoning_state: ReasoningState
    reasoning: tuple
    monotonic_ns: int
    wall_time_s: float
    prev_chain: str
    signature: str = ""

    def payload_for_signing(self) -> dict:
        return {
            "seq": self.seq, "token": self.token, "output": self.output,
            "reasoning_state": self.reasoning_state,
            "reasoning": [asdict(s) for s in self.reasoning],
            "monotonic_ns": self.monotonic_ns,
            "wall_time_s": self.wall_time_s,
            "prev_chain": self.prev_chain,
        }

    def __post_init__(self) -> None:
        if self.reasoning_state == "ABSENT" and self.reasoning:
            raise ValueError("ABSENT record must have empty reasoning")
        if self.reasoning_state == "PRESENT" and not self.reasoning:
            raise ValueError("PRESENT record must contain at least one Step")
        for item in self.reasoning:
            if not isinstance(item, Step):
                raise TypeError(f"reasoning entries must be Step; got {type(item).__name__}")


class Ledger:
    def __init__(
        self, key: bytes, *, storage_path: Optional[Path] = None,
        time_fn: Callable[[], int] = time.monotonic_ns,
        wall_fn: Callable[[], float] = time.time,
    ) -> None:
        if len(key) < 32:
            raise ValueError("HMAC key must be at least 32 bytes")
        self._key = key
        self._time_fn = time_fn
        self._wall_fn = wall_fn
        self._storage = Path(storage_path) if storage_path else None
        self._records = []
        self._last_chain = GENESIS_CHAIN
        self._next_seq = 0
        if self._storage is not None:
            self._load_or_init()

    def append(self, token: str, output: str, reasoning: Optional[list] = None) -> Record:
        steps = tuple(reasoning) if reasoning else ()
        state = "PRESENT" if steps else "ABSENT"
        unsigned = Record(
            seq=self._next_seq, token=token, output=output,
            reasoning_state=state, reasoning=steps,
            monotonic_ns=int(self._time_fn()),
            wall_time_s=float(self._wall_fn()),
            prev_chain=self._last_chain.hex(), signature="",
        )
        signed = self._replace_signature(unsigned, self._sign(unsigned))
        if self._storage is not None:
            self._persist(signed)
        self._records.append(signed)
        self._last_chain = chain_hash(
            self._last_chain, canonical_bytes(signed.payload_for_signing())
        )
        self._next_seq += 1
        return signed

    def verify(self) -> None:
        prev = GENESIS_CHAIN
        for i, rec in enumerate(self._records):
            if rec.seq != i:
                raise SequenceError(f"expected seq {i}, got {rec.seq}")
            if rec.prev_chain != prev.hex():
                raise VerificationError(f"chain break at seq {i}")
            if not hmac.compare_digest(self._sign(rec), rec.signature):
                raise VerificationError(f"signature mismatch at seq {i}")
            prev = chain_hash(prev, canonical_bytes(rec.payload_for_signing()))
        if self._storage is not None:
            self._verify_anchor(len(self._records), prev)

    def _sign(self, rec: Record) -> str:
        msg = canonical_bytes(rec.payload_for_signing())
        return hmac.new(self._key, msg, hashlib.sha256).hexdigest()

    @staticmethod
    def _replace_signature(rec: Record, sig: str) -> Record:
        return Record(
            seq=rec.seq, token=rec.token, output=rec.output,
            reasoning_state=rec.reasoning_state, reasoning=rec.reasoning,
            monotonic_ns=rec.monotonic_ns, wall_time_s=rec.wall_time_s,
            prev_chain=rec.prev_chain, signature=sig,
        )

    def _load_or_init(self) -> None:
        assert self._storage is not None
        self._storage.mkdir(parents=True, exist_ok=True)
        records_file = self._storage / "records.jsonl"
        anchor_file = self._storage / "anchor.json"
        if not records_file.exists():
            if anchor_file.exists():
                raise PersistenceError("anchor exists but records file does not")
            return
        loaded = []
        with records_file.open("rb") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    raise PersistenceError(f"malformed line in records.jsonl: {e}") from e
                reasoning = tuple(Step(**s) for s in obj.get("reasoning", []))
                loaded.append(Record(
                    seq=obj["seq"], token=obj["token"], output=obj["output"],
                    reasoning_state=obj["reasoning_state"], reasoning=reasoning,
                    monotonic_ns=obj["monotonic_ns"], wall_time_s=obj["wall_time_s"],
                    prev_chain=obj["prev_chain"], signature=obj["signature"],
                ))
        prev = GENESIS_CHAIN
        for i, rec in enumerate(loaded):
            if rec.seq != i:
                raise SequenceError(f"on-disk seq {rec.seq} at position {i}")
            if rec.prev_chain != prev.hex():
                raise VerificationError(f"on-disk chain break at seq {i}")
            if not hmac.compare_digest(self._sign(rec), rec.signature):
                raise VerificationError(f"on-disk signature mismatch at seq {i}")
            prev = chain_hash(prev, canonical_bytes(rec.payload_for_signing()))
        self._verify_anchor(len(loaded), prev)
        self._records = loaded
        self._last_chain = prev
        self._next_seq = len(loaded)

    def _persist(self, rec: Record) -> None:
        assert self._storage is not None
        records_file = self._storage / "records.jsonl"
        anchor_file = self._storage / "anchor.json"
        line = json.dumps({
            "seq": rec.seq, "token": rec.token, "output": rec.output,
            "reasoning_state": rec.reasoning_state,
            "reasoning": [asdict(s) for s in rec.reasoning],
            "monotonic_ns": rec.monotonic_ns, "wall_time_s": rec.wall_time_s,
            "prev_chain": rec.prev_chain, "signature": rec.signature,
        }, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n"

        with records_file.open("ab") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())

        new_chain = chain_hash(
            bytes.fromhex(rec.prev_chain),
            canonical_bytes(rec.payload_for_signing()),
        )
        tmp = anchor_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(
            {"count": rec.seq + 1, "chain": new_chain.hex()}, sort_keys=True
        ))
        os.replace(tmp, anchor_file)

        dir_fd = os.open(self._storage, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def _verify_anchor(self, count: int, chain: bytes) -> None:
        assert self._storage is not None
        anchor_file = self._storage / "anchor.json"
        if not anchor_file.exists():
            if count == 0:
                return
            raise PersistenceError("anchor missing for non-empty ledger")
        anchor = json.loads(anchor_file.read_text())
        if anchor["count"] != count:
            raise SequenceError(
                f"anchor count {anchor['count']} != loaded length {count}"
            )
        if anchor["chain"] != chain.hex():
            raise VerificationError("anchor chain head does not match ledger")
