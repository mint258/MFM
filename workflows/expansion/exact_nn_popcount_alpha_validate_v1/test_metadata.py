"""Pure query-history boundary fixtures; no native binary or scientific datasets."""
import copy
import hashlib
import json
import unittest
from .inputs import historical_queries


class QueryBindings(unittest.TestCase):
    def fixture(self):
        rows=[(i,dict(cid=i+1,full_key='fixture-key-'+str(i)),bytes([i])*256)for i in range(64)]
        digest=hashlib.sha256();expected=[]
        for i,row,raw in rows:
            expected.append(dict(query_ordinal=i,fingerprint_sha256=hashlib.sha256(raw).hexdigest()))
            digest.update(json.dumps([i,row['cid'],row['full_key'],raw.hex()],separators=(',',':')).encode()+b'\n')
        return rows,dict(results=expected),dict(query_identity_sha256=digest.hexdigest())

    def test_same64_ordered_raw_fingerprint_and_identity_history(self):
        rows,data,receipt=self.fixture()
        self.assertEqual(historical_queries(rows,data,receipt),receipt['query_identity_sha256'])

    def test_missing_duplicate_order_changed_fingerprint_or_identity_refused(self):
        rows,data,receipt=self.fixture()
        variants=[rows[:-1],list(reversed(rows)),[rows[0],*rows[0:63]],
            [(0,rows[0][1],b'x'*256),*rows[1:]],[(0,dict(cid=999,full_key=rows[0][1]['full_key']),rows[0][2]),*rows[1:]]]
        for value in variants:
            with self.subTest(rows=len(value)):
                with self.assertRaises(ValueError):historical_queries(value,data,receipt)
        wrong=copy.deepcopy(data);wrong['results'].pop()
        with self.assertRaises(ValueError):historical_queries(rows,wrong,receipt)


if __name__=='__main__':unittest.main()
