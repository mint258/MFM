"""One exact SQL fixture against an independent JSON/list oracle."""
import json
import unittest
from .query import census,summarize


class Source(unittest.TestCase):
    def test_exact_tuple_membership_and_canonical_domain_with_empty_vector(self):
        import duckdb
        values=['[]','[[6,1]]','[[8,2]]','[[16,1]]','[[6,2],[8,1],[16,3]]',
                '[[14,1],[34,1]]','[[26,1]]','[[6,3],[7,3],[8,6],[26,1]]',
                '[[6,0]]','[[1,2]]','[[6,1],[6,2]]','[[8,1],[6,1]]',
                '[[6,1.2]]','[[6,"1"]]','[[6,1],null]','[[6]]',None,'n.a.']
        expected=[]
        for text in values:
            try:
                v=json.loads(text)
                good=isinstance(v,list) and json.dumps(v,separators=(',',':'))==text and all(
                    isinstance(p,list) and len(p)==2 and type(p[0]) is int and 2<=p[0]<=118
                    and type(p[1]) is int and p[1]>0 for p in v)
                good=good and [p[0] for p in v]==sorted(set(p[0] for p in v))
            except (TypeError,ValueError):good=False
            expected.append((good,{p[0] for p in v} if good else set()))
        with duckdb.connect() as db:
            db.execute('CREATE TABLE fixture(non_h_composition VARCHAR)')
            db.executemany('INSERT INTO fixture VALUES(?)',[(v,) for v in values])
            result=summarize(census(db,'fixture'))
        self.assertEqual(result['total_rows'],len(values))
        self.assertEqual(result['invalid_or_noncanonical_composition_rows'],sum(not v for v,z in expected))
        self.assertEqual(result['contains_any_C_O_S'],sum(v and bool(z & {6,8,16}) for v,z in expected))
        self.assertEqual(result['contains_none_C_O_S'],sum(v and not bool(z & {6,8,16}) for v,z in expected))
        self.assertEqual(result['empty_non_H_vector_rows'],1)
        self.assertEqual(result['Fe_containing_rows'],2)
        self.assertEqual(result['outside_original_X_element_rows'],2)
        self.assertEqual(len(result['eight_C_O_S_combinations']),8)
        self.assertTrue(result['all_rows_accounted'])


if __name__=='__main__':unittest.main()
