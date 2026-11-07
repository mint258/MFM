"""One synthetic cache/binding control fixture; no science/source execution."""
import contextlib,copy,io,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
from . import prepare_runtime as P,uff_d3 as U


class CacheOnlyCheck(unittest.TestCase):
    def test_cache_only_never_writes_plan_or_binding_and_default_still_binds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);runtime=root/'runtime';path=root/'plan.json';marker=runtime/'bound_plan.json'
            common=root/'common.json';projection=root/'projection.json';old=str(root/'base_UFF/manifest.json')
            common.write_text(json.dumps({'status':'COMMON_POPULATION_V1_FROZEN','registered_extra_geometry_map_tables':[{'path':'toy:n1'}],
                                          'diagnostic_addressable_geometry_tables':[{'path':'toy:diagnostic'}]}))
            projection.write_text(json.dumps({'source_geometry_pointer_tables':[{'path':'toy:physical_records'}]}))
            plan={'runtime_metadata_root':str(runtime),'common':str(common),'pprime_cache':str(projection),'uff_d3_cache':old,
                  'source_working_root':str(root/'identities'),'additional_uff_d3_cache_root':str(root/'new_D3')}
            path.write_text(json.dumps(plan));original=path.read_bytes();source={'files':[{'path':'toy:addresses','records':15305}],'records':15305}
            save=P.I.save;produced=[]
            def addresses(inputs,cache):
                self.assertEqual(inputs,plan);self.assertEqual(cache['source_geometry_pointer_tables'],[{'path':'toy:physical_records'}])
                runtime.mkdir(exist_ok=True);save(runtime/'pprime_source_addresses.json',source);return copy.deepcopy(source)
            def produce(inputs):
                produced.append(copy.deepcopy(inputs));target=pathlib.Path(inputs['uff_d3_cache_root']);target.mkdir(exist_ok=True)
                self.assertEqual(inputs['reuse_uff_d3_caches'],[old])
                self.assertEqual(inputs['source_working_root'],str(root/'identities')+'_with_Pprime_sources')
                save(target/'manifest.json',{'toy_cache_closed':True});return {'toy_cache_closed':True}
            with patch.object(P,'source_pprime_addresses',side_effect=addresses) as address_call,patch.object(U,'produce',side_effect=produce),patch.object(P.I,'save',wraps=save) as writes:
                cached=P.prepare(path,bind_plan=False)
                self.assertEqual(path.read_bytes(),original);self.assertFalse(marker.exists())
                self.assertTrue((runtime/'pprime_source_addresses.json').is_file());self.assertTrue((root/'new_D3/manifest.json').is_file())
                self.assertEqual(cached['extra_geometry_tables'],[{'path':'toy:n1'},{'path':'toy:diagnostic'},source['files'][0]])
                self.assertEqual(cached['uff_d3_cache'],str(root/'new_D3/manifest.json'))
                self.assertEqual(writes.call_count,0);self.assertEqual(address_call.call_count,1)
                bound=P.prepare(path)
                self.assertEqual(bound,cached);self.assertEqual(address_call.call_count,2)
                self.assertEqual(produced[0],produced[1]);self.assertTrue(marker.is_file())
                self.assertEqual([pathlib.Path(call.args[0]) for call in writes.call_args_list],[path,marker])
            bound_bytes=marker.read_bytes();plan_bytes=path.read_bytes()
            with patch.object(P.I,'save',wraps=save) as writes,patch.object(P,'source_pprime_addresses',side_effect=AssertionError('bound cache replayed')),patch.object(U,'produce',side_effect=AssertionError('bound cache replayed')):
                self.assertEqual(P.prepare(path,bind_plan=False),bound);writes.assert_not_called()
                self.assertEqual(path.read_bytes(),plan_bytes);self.assertEqual(marker.read_bytes(),bound_bytes)
            wrong=json.loads(marker.read_text());wrong['plan_path']=str(root/'different_plan.json');save(marker,wrong)
            with patch.object(P.I,'save',wraps=save) as writes:
                for bind in (False,True):
                    with self.assertRaisesRegex(ValueError,'FROZEN_RUNTIME_PLAN_PATH_CHANGED'):P.prepare(path,bind_plan=bind)
                writes.assert_not_called()
            # CLI forwarding only; its cache work and actual target admission are
            # separately mocked, so no production plan/data can be touched.
            with patch.object(P,'prepare',return_value={}) as prepare,patch.object(P,'from_plan'),patch.object(sys,'argv',['prepare_runtime','--plan',str(path),'--cache-only']),contextlib.redirect_stdout(io.StringIO()):
                P.main();prepare.assert_called_once_with(str(path),bind_plan=False)


if __name__=='__main__':unittest.main()
