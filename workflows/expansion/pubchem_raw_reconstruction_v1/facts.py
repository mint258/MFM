"""Original Alpha source-row facts, without Alpha deployment/resource imports."""
import hashlib
from types import SimpleNamespace
from .support import need
Q = SimpleNamespace(need=need)
C = SimpleNamespace(MAX_LINE=3786)  # Observed complete original snapshot bound.

def cid_summary(token):
    canonical=token.lstrip(b'0');Q.need(token.isascii() and token.isdigit() and canonical,'POSITIVE_ORIGINAL_DECIMAL_CID_REQUIRED')
    return {'decimal_digits':len(canonical),'decimal_prefix':canonical[:32].decode('ascii'),
        'complete_decimal':canonical.decode('ascii') if len(canonical)<=32 else None,'decimal_sha256':hashlib.sha256(canonical).hexdigest()}


def row_fact(raw,ordinal,part_index,offset):
    Q.need(0<len(raw)<=C.MAX_LINE and raw.count(b'\t')==1,'ORIGINAL_SNAPSHOT_ROW_FRAMING_OR_MAXLINE_DIFFERS')
    raw.decode('utf-8','strict');cid,payload=raw.split(b'\t');cid_summary(cid)
    terminator=2 if payload.endswith(b'\r\n') else (1 if payload.endswith(b'\n') else 0)
    smiles=payload[:-terminator] if terminator else payload
    return {'ordinal':ordinal,'part_index':part_index,'offset_bytes':offset,'source_row_bytes':len(raw),
        'smiles_bytes':len(smiles),'source_row_sha256':hashlib.sha256(raw).hexdigest()}


def record(raw,fact,reference):
    actual=row_fact(raw,fact['ordinal'],fact['part_index'],fact['offset_bytes'])
    Q.need(actual=={k:fact[k] for k in actual},'EXACT_PHYSICAL_ROW_LOCATOR_OR_SHA_DIFFERS')
    cid,payload=raw.split(b'\t');end=2 if payload.endswith(b'\r\n') else (1 if payload.endswith(b'\n') else 0)
    smiles=payload[:-end] if end else payload
    return {**actual,'cid_source_ascii':cid.decode('ascii'),'source_smiles':smiles.decode('utf-8','strict'),
        'source_smiles_sha256':hashlib.sha256(smiles).hexdigest(),'source_terminator_hex':raw[-end:].hex() if end else '',
        'source_part':reference}
