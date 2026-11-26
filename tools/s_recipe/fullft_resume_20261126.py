"""Resume only an actually closed partial fit with identical scientific inputs."""


def require_resume(previous,closure,old,new):
    if (not previous.get('resource_closed') or previous.get('status')!='PAUSED_SAFE_CONTINUATION'
            or previous.get('run')!=new.get('run') or closure.get('status')!='CONTINUATION_REQUIRED'
            or closure.get('exit_code')!=75 or not closure.get('ended_at')
            or not closure.get('owned_descendants_exited') or not closure.get('observer_joined')):
        raise ValueError('Previous partial fit and its exact owned resources must close first')
    for key in ('run','output','task','seed','pretraining_seed','internal_split_seed','bootstrap_seed',
            'source_binding','store','providers_sha256','authority','invoking_authority','kind','mode'):
        if key not in old or key not in new or old[key]!=new[key]:
            raise ValueError('FullFT continuation changed scientific identity: '+key)
