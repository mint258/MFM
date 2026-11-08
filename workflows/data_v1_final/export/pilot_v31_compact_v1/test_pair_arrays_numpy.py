"""One tiny integer-pair equivalence fixture; no production arrays or timings."""
import copy,unittest
from unittest.mock import patch
import numpy as np
from . import assemble as A
from .codec import encode
from ..v31_stream_v1.projected_source import assemble_entries
from ..v31_stream_v1.run import channel_codes
from ..v31_stream_v1.test_stream import records,schema


def scalar_pair_arrays(pair_values,ordered_pairs,ncolumns):
    all_pairs={tuple(map(int,row))for pairs,_,_ in pair_values for row in pairs}
    if ordered_pairs is not None:all_pairs.update(tuple(map(int,row))for row in ordered_pairs)
    union=sorted(all_pairs);lookup={pair:i for i,pair in enumerate(union)}
    result26=np.asarray(union,dtype='<i2').reshape(-1,2);result27=np.full((len(union),ncolumns),np.nan,dtype='<f4')
    assigned=set()
    for pairs,values,column in pair_values:
        for pair,value in zip(pairs,values):
            row=lookup[tuple(map(int,pair))];cell=(row,column)
            A._need(cell not in assigned,'ordinary pair target repeats a pair; fixed scalar cell would lose multiplicity')
            assigned.add(cell);result27[row,column]=value
    result31=np.empty(0,dtype='<u4') if ordered_pairs is None else np.asarray([lookup[tuple(map(int,row))]for row in ordered_pairs],dtype='<u4')
    return result26,result27,result31


class NumpyPairArraysCheck(unittest.TestCase):
    def test_exact_pair_union_values_duplicates_and_real_assembler(self):
        # Both endpoints and F32 values are deliberately noncontiguous views.
        backing=np.zeros((4,4),dtype=np.int64);backing[:,::2]=[[32767,32767],[1,0],[0,1],[0,0]];pairs=backing[:,::2]
        bits=np.asarray([0x7fc01234,0,0x80000000,0,0x3f800000,0,0xffc12345,0],dtype='<u4');values=bits.view('<f4')[::2]
        self.assertFalse(pairs.flags.c_contiguous);self.assertFalse(values.flags.c_contiguous)
        empty=np.empty((0,2),dtype=np.int64);empty_values=np.empty(0,dtype='<f4')
        blocks=[(pairs,values,0),(np.asarray([[1,0],[2,2]],dtype=np.int64),np.asarray([0x80000000,0x7fc0abcd],dtype='<u4').view('<f4'),1),
                (np.asarray([[2,1]],dtype=np.int64),np.asarray([3.],dtype='<f4'),0),(empty,empty_values,0)]
        ordered=np.asarray([[0,1],[1,0],[0,1],[32767,32767],[0,0],[1,0],[0,32767],[32767,0]],dtype='<i2')
        cases=[(blocks,ordered,3),([],None,0),([],None,2),([(empty,empty_values,0)],None,0),
               ([],empty,0),([],ordered,0),([(pairs,values,0)],None,1),(blocks,empty,3)]
        for ordinary,raw,ncolumns in cases:
            snapshots=[(p.tobytes(),v.tobytes())for p,v,_ in ordinary];raw_before=None if raw is None else raw.tobytes()
            old=scalar_pair_arrays(ordinary,raw,ncolumns);new=A._pair_arrays(ordinary,raw,ncolumns)
            for expected,actual in zip(old,new):
                self.assertEqual(expected.dtype,actual.dtype);self.assertEqual(expected.shape,actual.shape);self.assertEqual(expected.tobytes(),actual.tobytes())
            k=0 if raw is None else len(raw);onsite=(np.arange(k)%3).astype('u1')
            masked=np.resize(np.asarray([0x7fc12345,0x80000000,0x3f800000],dtype='<u4').view('<f4'),k)
            old_record={26:old[0],27:old[1],31:old[2],33:onsite,34:masked}
            new_record={26:new[0],27:new[1],31:new[2],33:onsite,34:masked}
            self.assertEqual(encode(old_record),encode(new_record));self.assertIs(new_record[33],onsite);self.assertIs(new_record[34],masked)
            self.assertEqual([(p.tobytes(),v.tobytes())for p,v,_ in ordinary],snapshots)
            self.assertEqual(None if raw is None else raw.tobytes(),raw_before)
        duplicate=np.asarray([[1,0],[1,0]],dtype=np.int64);nan_values=np.asarray([0x7fc12345,0xffc01234],dtype='<u4').view('<f4')
        errors=[[(duplicate,nan_values,0)],[(duplicate[:1],nan_values[:1],0),(duplicate[1:],nan_values[1:],0)]]
        for ordinary in errors:
            with self.assertRaises(A.ScientificLayoutError) as old:scalar_pair_arrays(ordinary,ordered,2)
            with self.assertRaises(A.ScientificLayoutError) as new:A._pair_arrays(ordinary,ordered,2)
            self.assertIs(type(new.exception),type(old.exception));self.assertEqual(str(new.exception),str(old.exception))
        # Tiny real PM7/UFF assembly: only the pair-index helper changes between
        # oracle/new calls. No original source reader/native program is invoked.
        entries=records();layout=schema();layout['columns']['pair_labels']=[{},{}]
        layout['target_layout'].update(pair_a={'array_name':'pair_labels','column_indices':[0]},pair_b={'array_name':'pair_labels','column_indices':[1]},raw={'array_name':'r73_ordered','column_indices':[]})
        pgeo=entries[0];label={'descriptor':dict(pgeo['descriptor'],kind='labels',path='toy/pairs'),'gid':pgeo['gid'],'metadata':dict(pgeo['metadata']),
            'arrays':{'pairs/pair_a':np.asarray([[1,0],[0,0]],dtype=np.int64),'values/pair_a':np.asarray([-0.,.25],dtype='<f4'),'valid/pair_a':np.ones(2,dtype='u1'),
                      'pairs/pair_b':np.asarray([[1,0]],dtype=np.int64),'values/pair_b':np.asarray([3.5],dtype='<f4'),'valid/pair_b':np.ones(1,dtype='u1'),
                      'transport/raw/values':np.asarray([0.],dtype='<f4')}}
        entries.append(label)
        raw_parts={'pairs':np.asarray([[1,0],[0,1],[1,0],[0,0]],dtype=np.int64),
                   'onsite':np.asarray([0,1,2,0],dtype='u1'),'masked':np.asarray([0x7fc12345,0x80000000,0x3e000000,0x3f800000],dtype='<u4').view('<f4'),
                   'channels':[('s','p',None),('p','s','sigma'),('s','p',None),('s','s','sigma')]}
        before=copy.deepcopy(entries)
        with patch.object(A,'_r73',return_value=raw_parts),patch.object(A,'_pair_arrays',side_effect=scalar_pair_arrays):old=assemble_entries('m',entries,layout)
        with patch.object(A,'_r73',return_value=raw_parts):new=assemble_entries('m',entries,layout)
        self.assertEqual(encode(old['m_arrays']),encode(new['m_arrays']))
        for key in old.keys()-{'m_arrays','p_records','u_records'}:self.assertEqual(old[key],new[key])
        for domain in ('p_records','u_records'):
            self.assertEqual(len(old[domain]),len(new[domain]))
            old_book=['__ABSENT__'];new_book=['__ABSENT__'];old_codes={};new_codes={}
            for expected,actual in zip(old[domain],new[domain]):
                for key in expected.keys()-{'arrays'}:self.assertEqual(expected[key],actual[key])
                channel_codes(expected,old_book,old_codes);channel_codes(actual,new_book,new_codes)
                self.assertEqual(encode(expected['arrays']),encode(actual['arrays']))
            self.assertEqual(old_book,new_book)
        self.assertIs(new['p_records'][0]['arrays'][33],raw_parts['onsite']);self.assertIs(new['p_records'][0]['arrays'][34],raw_parts['masked'])
        self.assertIs(new['p_records'][0]['r73_channels'],raw_parts['channels'])
        for expected,actual in zip(before,entries):
            self.assertEqual(expected['metadata'],actual['metadata'])
            for key in expected['arrays']:self.assertEqual(expected['arrays'][key].tobytes(),actual['arrays'][key].tobytes())


if __name__=='__main__':unittest.main()
