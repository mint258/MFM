"""Native original-function SQL semantics and pending-scope rejection boundaries."""
import sqlite3
import unittest
from .headers import scope_authority


class Science(unittest.TestCase):
    def test_original_SQL_exact_composition_WP5_and_positive_bound_have_distinct_meaning(self):
        from workflows.expansion.coconut735_recovery_v1 import consumer as C
        with sqlite3.connect(':memory:') as db:
            C.install_tables(db)
            graph=dict(source_id='synthetic:graph',role='all',inchikeys=['AAAAAAAAAAAAAA-BBBBBBBBBB-N'])
            composition=dict(source_id='synthetic:composition',role='all',inchikeys=[],non_h_composition=[[6,2],[8,1]])
            for row,dataset in ((graph,'v1_all_roles_and_embargo'),(composition,'coconut')):
                db.executemany('INSERT INTO excluded VALUES(?,?,?)',[(kind,key,dataset) for kind,key in C.identity_keys(row)])
            binding={'synthetic_fixture_only':True}
            rule=dict(kind='NON_H_ATOM_COUNT_LOWER_BOUND',dataset='moleculenet',rule_id='synthetic:N1',binding=binding,bound=[[7,1]])
            C.insert_constraint(db,rule,expected_dataset='moleculenet',accepted_physical_bindings=[binding])
            def candidate(text,elements,key='DDDDDDDDDDDDDD-EEEEEEEEEE-N'):
                return dict(full_key=key,non_h_composition=text,elements=elements)
            self.assertEqual(C.contamination(candidate('[[6,2],[8,1]]',[6,8]),db),[('composition','coconut')])
            self.assertEqual(C.contamination(candidate('[[6,3],[8,1]]',[6,8]),db),[])
            self.assertEqual(C.contamination(candidate('[[6,3],[7,1],[8,1]]',[6,7,8]),db),[('composition_lower_bound:synthetic:N1','moleculenet')])
            self.assertEqual(C.contamination(candidate('[[6,1]]',[6],'AAAAAAAAAAAAAA-CCCCCCCCCC-N'),db),[('wp5','v1_all_roles_and_embargo')])
            with self.assertRaises(ValueError):C.insert_constraint(db,dict(rule,rule_id='synthetic:empty',bound=[]),expected_dataset='moleculenet',accepted_physical_bindings=[binding])

    def test_pending_scope_proposal_is_not_an_actual_user_approval(self):
        class Pending:
            def json(self,ref):return dict(schema='COCONUT_FINITE_SOURCE_SCOPE_PROPOSAL_V1',status='PENDING_USER_REPLY')
        with self.assertRaises(ValueError):scope_authority(Pending(),{}, {'entries:synthetic:1:1'}, {})


if __name__=='__main__':unittest.main()
