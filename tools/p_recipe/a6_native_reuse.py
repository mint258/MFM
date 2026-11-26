"""Copy closed native frames without decoding or recasting their FP64 coordinates."""
import hashlib
import json
import os
from pathlib import Path
import struct


def read_bound_frame(path, row):
    before=Path(path).stat()
    with Path(path).open("rb") as stream:
        if stream.read(8)!=b"P1DS1\0\0\0":
            raise ValueError("Closed native magic changed")
        stream.seek(row["offset"]);raw=stream.read(row["bytes"])
    after=Path(path).stat()
    if ((before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns)
            or len(raw)!=row["bytes"] or hashlib.sha256(raw).hexdigest()!=row["sha256"]):
        raise ValueError("Closed native frame binding changed")
    expected=(row["native_n_atoms"],row["target_rows"],len(row["tasks"]),int(row["geometry_ready"]))
    if struct.unpack_from("<4I",raw)!=expected:
        raise ValueError("Closed native shape changed")
    return raw


class ClosedNativeReuse:
    def __init__(self, sidecar):
        sidecar=Path(sidecar);self.document=json.loads(sidecar.read_text())
        d=self.document
        if not d["source_complete"] or d["targets_in_metadata"] or not d["native_record_hashes_preserved"]:
            raise ValueError("Only a closed TRAIN-native store may be reused")
        self.rows={(r["dataset_id"],r["member_index"]):r for r in d["records"]}
        self.groups={(r["dataset_id"],r["member_index"]):r for r in d["molecule_groups"]}
        from phychem_mfm.phase1.v3_dev_store import bound_json
        ref=d["selected_store_manifest"]
        if ref["sha256"]!=d["source_store_manifest_sha256"]:
            raise ValueError("Closed source manifest identity differs")
        manifest=bound_json(ref["path"],ref["sha256"])
        ref=manifest["source_proofs"]
        proofs=bound_json(ref["path"],ref["sha256"])["records"]
        self.proofs={(r["dataset_id"],r["member_index"]):r for r in proofs}
        self.path=Path(d["records_file"]["path"])

    def get(self,dataset,source):
        key=(dataset,source["member_index"])
        if key not in self.rows:return None
        row=self.rows[key];proof=self.proofs[key];group=self.groups[key]
        if (row["member_uid"]!=source["member_uid"]
                or group["full_inchikey"]!=source["full_inchikey"]
                or proof["selected_role"]!=source["selected_role"]
                or proof["original_member_row_sha256"]!=source["original_member_row_sha256"]):
            raise ValueError("Closed source/role/molecule binding changed")
        return dict(annotation_state="REUSED_CLOSED_NATIVE",reused_metadata=row,
                    reused_frame=read_bound_frame(self.path,row),source_proof=proof["source_proof"])


def materialization_one(job,reuse,decode):
    dataset,source=job
    actual=reuse.get(dataset,source)
    if actual is None:
        actual=decode(dataset,source["member_index"],role=source["selected_role"])
    return dataset,source,actual
