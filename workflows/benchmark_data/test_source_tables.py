import io
import tempfile
from pathlib import Path
import unittest
import zipfile
from workflows.benchmark_data.source_tables import tdc_rows,decode_column,curated_pka_rows


class SourceTableTests(unittest.TestCase):
    def test_pka_author_curation_preserves_raw_source_row_identity(self):
        rows=[{'exclude_flag':' EXCLUDE ','rawdataID':'omit'},
              {'exclude_flag':'','rawdataID':'keep','Exp_Macro_pKa_processed':'1.2345678901234567'}]
        result=list(curated_pka_rows(rows))
        self.assertEqual(len(result),1)
        self.assertEqual(result[0][1],1)
        self.assertEqual(result[0][2]['Exp_Macro_pKa_processed'],'1.2345678901234567')

    def test_tdc_archive_is_streamed_with_original_split_and_label_lexemes(self):
        memory=io.BytesIO()
        with zipfile.ZipFile(memory,'w') as archive:
            archive.writestr('admet_group/task/test.csv','Drug_ID,Drug,Y\noriginal,CCO,1.2345678901234567\n')
            archive.writestr('admet_group/task/train_val.csv','Drug_ID,Drug,Y\ntrain,CCC,0\n')
        memory.seek(0)
        rows=list(tdc_rows(memory))
        self.assertEqual([r[3] for r in rows],['test','train_val'])
        self.assertEqual(rows[0][2]['Y'],'1.2345678901234567')
        self.assertEqual(rows[0][1],0)

    def test_official_zarr_codec_chain_preserves_strings_categories_and_f64(self):
        import numpy as np
        from numcodecs import get_codec
        for values,filters,dtype,compressor in [
            (['CCO','CCN'],[{'id':'vlen-utf8'}],'|O',None),
            (['Train','Test'],[{'id':'categorize','astype':'|u1','dtype':'|O','labels':['Train','Test']}],
                '|O',{'id':'blosc','cname':'lz4','clevel':5,'shuffle':1,'blocksize':0}),
            ([1.2345678901234567,float('nan')],None,'<f8',None)]:
            array=np.asarray(values,dtype=dtype)
            value=array
            for spec in filters or []:value=get_codec(spec).encode(value)
            value=get_codec(compressor).encode(value) if compressor else value
            if hasattr(value,'tobytes'):value=value.tobytes()
            actual=decode_column(value,{'shape':[2],'chunks':[2],'dtype':dtype,'order':'C',
                'filters':filters,'compressor':compressor})
            if dtype=='<f8':
                self.assertEqual(actual[0],values[0]);self.assertTrue(np.isnan(actual[1]))
            else:self.assertEqual(actual,values)

if __name__=='__main__':unittest.main()
