"""Read shared B0 S-prime/D records in place, with short SQLite read transactions."""
import argparse
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote
import zlib


class SharedB0Reader:
    def __init__(self,path):
        self.path=Path(path).absolute()
        if not self.path.is_file():raise FileNotFoundError(self.path)
        self.db=sqlite3.connect('file:'+quote(str(self.path),safe='/')+'?mode=ro',
            uri=True,timeout=10,isolation_level=None)
        self.db.execute('PRAGMA query_only=ON')

    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

    def get(self,dataset,record_id):
        row=self.db.execute('''SELECT m.mid,m.model_atom_to_source,t.state,t.error,t.result
            FROM membership m JOIN tasks t ON t.mid=m.mid
            WHERE m.dataset=? AND m.record_id=?''',(dataset,record_id)).fetchone()
        if row is None:raise KeyError((dataset,record_id))
        # fetchone completes the statement before decoding/consumer computation.
        # There is no live SQL iterator holding a shared read lock on the writer.
        self.db.commit()
        mid,mapping,state,error,payload=row
        value=json.loads(zlib.decompress(payload)) if payload is not None else None
        return {'dataset':dataset,'record_id':record_id,'shared_molecule_id':mid,
            'model_atom_to_source':json.loads(mapping),'state':state,'error':error,
            'result':value,'P_ready':False,'Pprime_ready':False,
            'source_database':str(self.path),'local_database_copy_created':False}

    def iter_membership(self,dataset,batch_size=256):
        """Only immutable source membership; readiness is obtained by get()."""
        if not 1<=batch_size<=4096:raise ValueError('Batch size must be within 1..4096')
        after=''
        while True:
            page=self.db.execute('''SELECT record_id FROM membership
                WHERE dataset=? AND record_id>? ORDER BY record_id LIMIT ?''',
                (dataset,after,batch_size)).fetchall()
            self.db.commit()
            if not page:return
            after=page[-1][0]
            for (record_id,) in page:yield record_id


def main():
    p=argparse.ArgumentParser();p.add_argument('--queue',type=Path,required=True)
    p.add_argument('--dataset',required=True);p.add_argument('--record-id')
    a=p.parse_args()
    with SharedB0Reader(a.queue) as reader:
        rid=a.record_id or next(reader.iter_membership(a.dataset))
        value=reader.get(a.dataset,rid)
        result=value['result']
        if result is not None:
            # A small format example; the API returns the complete record.
            value['result']={'D20':result.get('D20'),'atomic_numbers':result.get('atomic_numbers'),
                'model_smiles':result.get('model_smiles'),'conformers_actual':len(result.get('conformers',[])),
                'conformer_fields':list(result['conformers'][0]) if result.get('conformers') else []}
        print(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))

if __name__=='__main__':main()
