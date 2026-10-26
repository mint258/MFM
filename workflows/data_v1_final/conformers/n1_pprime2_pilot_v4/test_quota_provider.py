"""Synthetic resource boundaries only; no subprocess, remote data or science."""
from __future__ import annotations
import copy,unittest
from . import quota_provider as Q


class AccountQuotaProviderBoundaries(unittest.TestCase):
    def fixtures(self):
        reference={'path':'/synthetic/review.json','bytes':1,'sha256':'1'*64}
        identity_reference={'path':'/synthetic/provider/identity.json','bytes':1,'sha256':'2'*64}
        marker={'path':'/synthetic/marker.json','bytes':213,'sha256':'3'*64}
        mount=Q.LOGIN_MOUNT.copy()
        sources=[{'path':'/synthetic/source.py','bytes':1,'sha256':'4'*64}]
        review={'login_node':'sonmi','login_quota_device':'/dev/sda1','login_mount':mount,'marker_reference':marker,
            'provider_source_references':sources,'maximum_runtime_seconds':3600,'publisher_output_dir':'/synthetic/provider'}
        identity={'schema':Q.IDENTITY_SCHEMA,'endpoint':Q.ENDPOINT,'uid':Q.UID,'node':'sonmi','review_reference':reference,
            'provider_source_references':sources,'started_unix_seconds':1000,'expires_unix_seconds':4600,
            'publisher_output_dir':'/synthetic/provider','pid':100,'start_ticks':200,
            'boot_id':'11111111-2222-3333-4444-555555555555','not_a_Slurm_science_job':True,
            'refresh_seconds':Q.REFRESH,'whole_output_cap_bytes':Q.CAP,
            'execution_argv':[Q.PY,'-B',str(Q.HERE/'quota_provider.py'),'--review',reference['path'],
                '--output','/synthetic/provider','--max-seconds','3600']}
        query={'argv':Q.QUOTA_ARGV.copy(),'returncode':0,'stderr':'','raw_output_complete':True,
            'stdout':'Disk quotas for user zixiao (uid 1278): \n Filesystem blocks quota limit grace files quota limit grace\n /dev/sda1 100 0 1000000000 0 10 0 0\n'}
        findmnt={'argv':Q.FINDMNT_ARGV.copy(),'returncode':0,'stderr':'','raw_output_complete':True,
            'stdout':'/share /dev/sda1 xfs /\n'}
        df={'argv':Q.DF_ARGV.copy(),'returncode':0,'stderr':'','raw_output_complete':True,
            'stdout':'Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/sda1 31251898368 24509828288 6742070080 79% /share\n'}
        value={'schema':Q.SNAPSHOT_SCHEMA,'identity_reference':identity_reference,'review_reference':reference,
            'endpoint':Q.ENDPOINT,'uid':Q.UID,'node':'sonmi','sequence':1,'status':'RUNNING','observed_unix_seconds':1100,
            'storage':{'mount':mount,'uid':Q.UID,'node':'sonmi','findmnt':findmnt,'df':df,'mount_selection':Q.parse_mount(findmnt,df)},
            'marker':{'reference':marker,'uid':Q.UID,'bytes_checked':213,'stat':{'device':2049,**Q.MARKER_IDENTITY}},'quota_query':query,
            'parsed_quota':Q.parse_quota(query,'/dev/sda1')}
        return reference,identity_reference,review,identity,value

    def test_01_finite_account_quota_uses_kib_and_minimum_positive_limit(self):
        *_,value=self.fixtures();row=value['quota_query']
        self.assertEqual(Q.parse_quota(row,'/dev/sda1')['free_bytes'],(1000000000-100)*1024)
        row['stdout']=row['stdout'].replace('100 0 1000000000','100 500000000 1000000000')
        self.assertEqual(Q.parse_quota(row,'/dev/sda1')['limit_kib'],500000000)

    def test_02_empty_or_failed_quota_cannot_be_replaced_by_declared_free(self):
        *_,value=self.fixtures()
        for code,text in ((1,''),(1,value['quota_query']['stdout']),(0,'')):
            row={**value['quota_query'],'returncode':code,'stdout':text}
            with self.assertRaises(ValueError):Q.parse_quota(row,'/dev/sda1')
        with self.assertRaises(ValueError):Q.parse_quota({**value['quota_query'],'raw_output_complete':False},'/dev/sda1')

    def test_03_wrong_uid_device_duplicate_or_infinite_limit_rejected(self):
        *_,value=self.fixtures();original=value['quota_query'];text=original['stdout']
        for bad in (text.replace('uid 1278','uid 1264'),text.replace('/dev/sda1','/dev/other'),
                text+' /dev/sda1 100 0 1000000000 0 10 0 0\n',text.replace('100 0 1000000000','100 0 0')):
            with self.assertRaises(ValueError):Q.parse_quota({**original,'stdout':bad},'/dev/sda1')

    def test_04_freshness_inclusive120_but_future_expired_and_terminal_fail(self):
        ref,iref,review,identity,value=self.fixtures()
        self.assertGreater(Q.validate_observation(value,identity,iref,review,ref,1220)['free_bytes'],0)
        for now,status in ((1220.0001,'RUNNING'),(1099,'RUNNING'),(4600,'RUNNING'),(1110,'STOPPED'),(1110,'ERROR'),(1110,'EXPIRED')):
            bad={**value,'status':status}
            with self.assertRaises(ValueError):Q.validate_observation(bad,identity,iref,review,ref,now)

    def test_05_mount_marker_source_identity_and_raw_recomputation_binding(self):
        ref,iref,review,identity,value=self.fixtures()
        for change in ('mount','marker','uid','source','parsed','pid','argv','boot'):
            bad=copy.deepcopy(value);other=copy.deepcopy(identity)
            if change=='mount':bad['storage']['mount']['source']='/dev/local'
            if change=='marker':bad['marker']['reference']['sha256']='f'*64
            if change=='uid':other['uid']=1264
            if change=='source':other['provider_source_references'][0]['sha256']='f'*64
            if change=='parsed':bad['parsed_quota']['free_bytes']+=1
            if change=='pid':other['pid']=0
            if change=='argv':other['execution_argv'][2]='/synthetic/other_producer.py'
            if change=='boot':other['boot_id']='not-boot-id'
            with self.assertRaises(ValueError):Q.validate_observation(bad,other,iref,review,ref,1110)

    def test_06_actual_autofs_nfs_overlay_requires_unique_active_and_same_df(self):
        findmnt={'argv':Q.FINDMNT_ARGV.copy(),'returncode':0,'stderr':'','raw_output_complete':True,
            'stdout':'/share/home systemd-1       autofs /\n/share/home nfs:/share/home nfs4   /\n'}
        df={'argv':Q.DF_ARGV.copy(),'returncode':0,'stderr':'','raw_output_complete':True,
            'stdout':'Filesystem 1024-blocks Used Available Capacity Mounted on\nnfs:/share/home 31251898368 24509828096 6742070272 79% /share/home\n'}
        parsed=Q.parse_mount(findmnt,df)
        self.assertEqual(parsed['active_mount'],Q.COMPUTE_MOUNTS['compute-0-13'])
        self.assertEqual(len(parsed['all_findmnt_rows']),2);self.assertEqual(len(parsed['autofs_overlay_rows']),1)
        self.assertEqual(parsed['df_active_row']['total_kib'],31251898368)
        for bad_findmnt,bad_df in (
                ({**findmnt,'stdout':findmnt['stdout']+'/other /dev/second xfs /\n'},df),
                ({**findmnt,'stdout':'/share/home systemd-1 autofs /\n'},df),
                (findmnt,{**df,'stdout':df['stdout'].replace('nfs:/share/home','/dev/local')}),
                (findmnt,{**df,'stdout':df['stdout'].replace('79% /share/home','79% /wrong')}),
                (findmnt,{**df,'returncode':1}),
                (findmnt,{**df,'raw_output_complete':False})):
            with self.assertRaises(ValueError):Q.parse_mount(bad_findmnt,bad_df)


if __name__=='__main__':unittest.main()
