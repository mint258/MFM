"""Bounded, source-bound TRAIN log statistics. No targets, SDK or model execution."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import math
from pathlib import Path
import statistics

from .v3_decision_evidence import (RunEvidence, bound_bytes, bound_json, canonical,
    digest, require, _json, _number)
from .v3_decision_rules import RulePolicy, Stability


def integer(x, minimum=0):
    require(type(x) is int and x >= minimum, 'Explicit integer cursor/count required')
    return x


def terminal_capture(reference, job_id, *, pointer=()):
    """Consume a bound Root raw sacct observation; a child COMPLETE is not C0."""
    raw = bound_json(reference)
    for key in pointer:
        raw = raw[key]
    require(raw['returncode'] == 0 and type(raw['returncode']) is int
            and raw['argv'][0] == 'sacct' and '-X' in raw['argv']
            and '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList' in raw['argv'],
            'Root actual parent sacct capture required')
    rows = [line.split('|') for line in raw['stdout'].splitlines() if line.strip()]
    rows = [r for r in rows if r[0] == str(job_id)]
    require(len(rows) == 1 and len(rows[0]) == 7, 'Unique actual parent accounting row required')
    r = rows[0]
    require(r[1] == 'zixiao' and r[2] in ('COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY')
            and int(r[4]) >= 0 and int(r[5]) >= 16, 'Actual terminal UID/allocation/state differs')
    require(r[3].count(':') == 1 and all(x.isdigit() for x in r[3].split(':')), 'Actual exit code required')
    return {'job_id':str(job_id), 'state':r[2], 'exit_code':r[3],
            'C0':r[2] == 'COMPLETED' and r[3] == '0:0', 'raw_capture':reference}




def _job_binding(reference,segment):
    b=bound_json(reference)
    require(b['schema'] == 'model_v3_proxy_segment_launch_v1' and b['job_id'] == str(segment['job_id'])
        and bound_json(b['request'])['configuration'] == segment['configuration'],
        'Actual producer RUN_BINDING job/config differs')
    return b


def anchored_cursors(anchor,segment,*,terminal,initial):
    """Independent producer/checkpoint JSON anchors; never hashes/loads payload.pt."""
    require(type(anchor) is dict,'Actual committed cursor anchor required')
    kind=anchor['kind']
    if initial:
        launch=_job_binding(anchor['run_binding'],segment)
        if kind == 'origin':
            require(launch.get('resume_complete') is None,'A resumed run cannot claim a fresh zero origin')
            value=launch.get('initial_cursors')
            require(value == {'optimizer_updates':0,'samples_consumed':0,'log_cursor':0},
                'Actual producer zero-draw origin missing')
            for x in value.values():integer(x)
            return value
        require(kind == 'checkpoint' and launch.get('resume_complete') == anchor['reference'],
            'Initial cursor must bind the actual resumed checkpoint')
    if kind == 'checkpoint':
        record=bound_json(anchor['reference'])
        require(record['schema'] == 'model_v3_sample_experiment_checkpoint_v1','Actual wrapper checkpoint record required')
        state=bound_json(record['state']);marker=bound_json(record['trainer_marker']);intent=bound_json(record['intent'])
        require(intent['schema'] == 'model_v3_sample_checkpoint_intent_v1'
            and intent['state'] == {k:v for k,v in state.items() if k != 'event'}
            and marker['schema'] == 'model_v3_training_checkpoint_v1'
            and marker['bindings'] == state['contract']['trainer_bindings']
            and state['contract']['model_configuration'] == segment['configuration']
            and marker['bindings']['configuration_sha256'] == segment['configuration']['sha256'],
            'Actual checkpoint metadata/config/intent chain differs')
        payload=record['trainer_payload'];digest(payload['sha256']);integer(payload['bytes'],1)
        for key in ('samples_consumed','optimizer_updates','payload_bytes'):integer(marker[key])
        require(Path(record['trainer_marker']['path']) == Path(payload['path']).parent/'COMPLETE.json'
            and marker['payload_sha256'] == payload['sha256'] and marker['payload_bytes'] == payload['bytes']
            and marker['samples_consumed'] == state['samples_consumed']
            and marker['optimizer_updates'] == state['optimizer_updates'] and state['pending_log'] is False,
            'Checkpoint completion/committed clocks/pending log differ')
        event=state['event']
        from .v3_sample_budget_events import canonical as event_digest
        require(event['checkpoint'] == payload and event['training_completion'] == record['trainer_marker']
            and event['event_id'] == event_digest({k:v for k,v in event.items() if k != 'event_id'}),
            'Checkpoint/controller event does not bind actual immutable marker')
        value={k:state[k] for k in ('optimizer_updates','samples_consumed','log_cursor')}
    else:
        require(not initial and kind == 'failed_child' and not terminal['C0'],
            'Successful full-update statistics require a committed checkpoint anchor')
        child=bound_json(anchor['reference']);_job_binding(anchor['run_binding'],segment)
        require(child['schema'] == 'model_v3_proxy_child_receipt_v1' and child['status'] == 'CHILD_FAILED'
            and child['job_id'] == str(segment['job_id']) and child['committed_cursors']['pending_log'] is False,
            'Actual failed producer committed-clock receipt required')
        value={k:child['committed_cursors'][k] for k in ('optimizer_updates','samples_consumed','log_cursor')}
    for x in value.values():integer(x)
    return value

def closed_series(manifest, policy, *, run=None, maximum_bytes=256 << 20, maximum_rows=200000):
    """Every resumed committed update appears once. Gaps/overlap fail, never dedup.

    Closure is a model-owned Root projection of committed checkpoint/log cursors,
    raw history and actual terminal capture. It is not a data-line schema. The
    Root projection and accounting authenticity still require external review.
    """
    require(isinstance(policy, RulePolicy) and type(manifest) is dict
            and manifest.get('schema') == 'model_v3_recipe_log_inputs_v1', 'Registered policy and log manifest required')
    segments = manifest.get('segments')
    require(type(segments) is list and 1 <= len(segments) <= 512, 'Explicit finite closed segments required')
    if run is not None:
        require(isinstance(run, RunEvidence) and manifest['training_run_id'] == run.training_run_id
                and manifest['scientific_identity_sha256'] == run.scientific_identity_sha256
                and manifest['seed'] == run.seed, 'Log series differs from inspected training run')
    digest(manifest['scientific_identity_sha256']); integer(manifest['seed'])
    rows, refs, terminals, total, previous = [], [], [], 0, None
    updates = samples = cursor = None
    configuration_ref = None
    for ref in segments:
        s = bound_json(ref)
        require(s.get('schema') == 'model_v3_recipe_closed_log_segment_v1'
                and s['training_run_id'] == manifest['training_run_id']
                and s['scientific_identity_sha256'] == manifest['scientific_identity_sha256']
                and type(s['seed']) is int and s['seed'] == manifest['seed'], 'Closed segment identity differs')
        require(policy.commit_epoch < _number(s['training_start_epoch']), 'Numeric policy must precede actual training')
        # Configuration itself is bound; source inventories remain in that config.
        config = bound_json(s['configuration'])
        if run is not None:
            expected=bound_json(run.sources['request'])['model_configuration']
            require(s['configuration'] == expected and s['training_start_epoch'] == run.training_start_epoch, 'Log config/start differs from inspected checkpoint')
        require(config.get('engineering_only') is False and config.get('experiment_scope') != 'ENGINEERING_SYNTHETIC_ONLY'
                and type(config['seed']) is int and config['seed'] == s['seed'], 'Engineering logs cannot become scientific evidence')
        if configuration_ref is None: configuration_ref=s['configuration']
        require(configuration_ref == s['configuration'],'Configuration changed across resumed log segments')
        start, end = s['initial'], s['final']
        for state in (start,end):
            require(set(state) == {'optimizer_updates','samples_consumed','log_cursor'}, 'Complete committed cursors required')
            for v in state.values(): integer(v)
        require(end['samples_consumed'] <= config['proxy_contract']['sample_budget']
            and end['optimizer_updates'] <= end['samples_consumed'] and end['log_cursor'] >= end['optimizer_updates'],'Impossible committed checkpoint cursors/budget')
        if previous is None:
            require(start == {'optimizer_updates':0,'samples_consumed':0,'log_cursor':0},'All-update statistics require the complete run from zero')
        if previous is not None:
            require(start == previous, 'Resume has overlapping/replayed updates or missing committed cursors')
        updates, samples, cursor = start['optimizer_updates'], start['samples_consumed'], start['log_cursor']
        term = terminal_capture(s['terminal'], s['job_id'], pointer=tuple(s.get('terminal_pointer',())))
        terminals.append(term)
        require(start == anchored_cursors(s.get('initial_anchor'),s,terminal=term,initial=True)
            and end == anchored_cursors(s.get('final_anchor'),s,terminal=term,initial=False),
            'History projection differs from actual committed checkpoint/producer cursors')
        data = bound_bytes(s['history'], maximum=min(maximum_bytes,128 << 20)); total += len(data)
        require(total <= maximum_bytes and (not data or data.endswith(b'\n')), 'Log envelope exhausted or truncated tail')
        for line in data.splitlines():
            require(len(rows) < maximum_rows and 0 < len(line) <= 2 << 20, 'Bounded complete history records required')
            item = _json(line)
            require(type(item) is dict and set(item) == {'step','commit','row'}
                    and type(item['commit']) is bool and item['commit'] is True
                    and type(item['step']) is int and item['step'] == cursor, 'Explicit contiguous committed history step required')
            row = item['row']; require(type(row) is dict and row.get('log_cursor') == cursor
                    and type(row.get('log_cursor')) is int, 'Saved row/SDK step cursor differs')
            if row.get('event') == 'TRAIN_STEP':
                require(type(row['optimizer_updated']) is bool, 'Actual update flag required')
                counts=[v for k,v in row.items() if k.startswith('valid_count/')]
                require(counts and all(type(v) is int and v >= 0 for v in counts)
                    and any(v > 0 for v in counts) is row['optimizer_updated'],'Effective update flag differs from actual label coverage')
                samples_new = integer(row['samples_consumed'])
                require(samples_new > samples, 'Consumed TRAIN draw cursor must advance')
                updates += int(row['optimizer_updated']); samples = samples_new
                require(type(row['optimizer_updates']) is int and row['optimizer_updates'] == updates,
                        'Effective update counter missing, duplicated or replayed')
                norm = row.get('gradient_norm_before_clip')
                require((norm is None) == (not row['optimizer_updated']), 'Preclip norm belongs only to actual effective updates')
                if norm is not None: require(_number(norm) >= 0, 'Nonfinite or negative preclip norm')
                _number(row['loss/total'])
            else:
                require(type(row.get('samples_consumed')) is int and type(row.get('optimizer_updates')) is int
                        and row.get('event') == 'VALIDATION' and row.get('role') in ('VAL','TRAIN_UNSEEN_CONFORMATION') and row['samples_consumed'] == samples
                        and row['optimizer_updates'] == updates, 'Unknown event or validation cursor drift')
            rows.append(row); cursor += 1
        require(end == {'optimizer_updates':updates,'samples_consumed':samples,'log_cursor':cursor},
                'History does not reach the exact Root committed checkpoint cursors')
        require(bound_bytes(s['history'], maximum=128 << 20) == data, 'History changed during read')
        bound_json(ref); bound_json(s['configuration']); bound_json(s['terminal'])
        refs.append(ref); previous = end
    if run is not None:
        require(samples == run.checkpoint_samples, 'Final log draws differ from inspected checkpoint')
    return rows, {'segments':refs, 'terminals':terminals, 'history_rows':len(rows),
        'final':previous, 'training_run_id':manifest['training_run_id'],
        'scientific_identity_sha256':manifest['scientific_identity_sha256'],
        'seed':manifest['seed'], 'policy_sha256':policy.sha256,
        'inspected_run_evidence_sha256':None if run is None else run.evidence_sha256,
        'manifest_sha256':canonical(manifest), 'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def gradient_p99(manifest, policy, *, run=None):
    p = policy.rules.get('gradient_p99')
    require(p == {'population':'all_effective_TRAIN_updates','quantile':.99,'method':'linear'},
            'Explicit preregistered exact TRAIN p99 population/quantile method required')
    rows, proof = closed_series(manifest,policy,run=run)
    require(all(t['C0'] for t in proof['terminals']), 'Clip p99 requires successful closed committed training segments')
    values = sorted(_number(r['gradient_norm_before_clip']) for r in rows
                    if r['event'] == 'TRAIN_STEP' and r['optimizer_updated'])
    require(bool(values), 'No effective TRAIN gradient samples')
    x = .99*(len(values)-1); i = math.floor(x)
    value = values[i] if i == len(values)-1 else values[i]+(values[i+1]-values[i])*(x-i)
    require(value > 0, 'Zero p99 cannot supply a positive clipping threshold')
    return {'schema':'model_v3_TRAIN_preclip_p99_proposal_v1','status':'PROPOSED_NOT_FROZEN',
        'p99':value,'sample_count':len(values),'minimum':values[0],'maximum':values[-1],
        'population':p,'proof':proof,'frozen':False}


def classify_stability(manifest, policy, *, run=None):
    p = policy.rules.get('stability')
    require(type(p) is dict and set(p) == {'window','warmup_updates','minimum_updates','ratio',
            'absolute_increase','baseline_floor','minimum_spikes','numeric_failure_literals',
            'numeric_exception_types','numeric_failure_phases'},
            'Explicit preregistered quantitative stability policy required')
    window=integer(p['window'],1); integer(p['warmup_updates']); integer(p['minimum_updates'],window+1)
    require(_number(p['ratio']) > 1 and _number(p['absolute_increase']) > 0
            and _number(p['baseline_floor']) > 0, 'Numeric spike thresholds required')
    integer(p['minimum_spikes'],1)
    require(type(p['numeric_failure_literals']) is list and p['numeric_failure_literals']
            and all(type(x) is str and 1 <= len(x) <= 200 for x in p['numeric_failure_literals']), 'Bound numeric failure patterns required')
    rows, proof = closed_series(manifest,policy,run=run)
    failed = any(not t['C0'] for t in proof['terminals'])
    divergence = False
    if failed:
        failures = manifest.get('failure_observations',[])
        require(failures, 'Failed training needs raw numeric failure evidence; infrastructure exit is not divergence')
        allowed_messages={'Nonfinite gradient before optimizer update','Nonfinite training/validation loss','Nonfinite shared-gradient probe'}
        require(set(p['numeric_failure_literals']) <= allowed_messages
            and type(p['numeric_exception_types']) is list and p['numeric_exception_types']
            and set(p['numeric_exception_types']) <= {'ValueError','FloatingPointError'}
            and type(p['numeric_failure_phases']) is list and p['numeric_failure_phases']
            and set(p['numeric_failure_phases']) <= {'TRAIN_STEP','VALIDATION'},
            'Only source-known numeric exceptions/phases/messages may classify LR failure')
        failed_jobs={t['job_id'] for t in proof['terminals'] if not t['C0']}
        observed=set()
        segments={str(bound_json(ref)['job_id']):bound_json(ref) for ref in manifest['segments']}
        for observation in failures:
            require(type(observation) is dict and set(observation) == {'child_receipt','run_binding'}, 'Typed producer failure references required; legacy free text is UNKNOWN')
            child=bound_json(observation['child_receipt']);job=child.get('job_id')
            require(job in failed_jobs and job not in observed,'Typed primary failure must bind one actual failed parent')
            segment=segments[job];_job_binding(observation['run_binding'],segment)
            require(segment['final_anchor']['kind'] == 'failed_child'
                and segment['final_anchor']['reference'] == observation['child_receipt']
                and Path(observation['child_receipt']['path']).parent == Path(observation['run_binding']['path']).parent
                == Path(segment['history']['path']).parent,'Failure receipt is not this producer/output root')
            primary=child.get('primary_failure')
            require(child.get('schema') == 'model_v3_proxy_child_receipt_v1' and child.get('status') == 'CHILD_FAILED'
                and type(primary) is dict and primary.get('schema') == 'model_v3_recipe_primary_failure_v1'
                and primary.get('job_id') == job and child.get('first_failure') == {'type':primary.get('type'),'message':primary.get('message')},
                'Source producer primary exception/phase is unknown; free text cannot exclude an LR')
            require(primary['type'] in p['numeric_exception_types'] and primary['phase'] in p['numeric_failure_phases']
                and type(primary['message']) is str and any(primary['message'].startswith(x) for x in p['numeric_failure_literals']),
                'Non-numeric primary exception/phase cannot classify LR divergence')
            observed.add(job)
        require(observed == failed_jobs,'Every failed segment needs its actual typed primary failure')
        divergence=True
    losses = [_number(r['loss/total']) for r in rows if r['event'] == 'TRAIN_STEP' and r['optimizer_updated']]
    require(divergence or len(losses) >= p['minimum_updates'], 'Incomplete numeric stability population')
    spikes=[]
    for i in range(max(window,p['warmup_updates']),len(losses)):
        baseline=statistics.median(losses[i-window:i])
        if losses[i]-baseline >= p['absolute_increase'] and losses[i] >= p['ratio']*max(abs(baseline),p['baseline_floor']):
            spikes.append(i+1)
    verdict = Stability(divergence,len(spikes) >= p['minimum_spikes'],canonical(proof),canonical(p),
                        (manifest['training_run_id'],))
    return {'schema':'model_v3_numeric_stability_proposal_v1','status':'PROPOSED_NOT_FROZEN',
        'stability':asdict(verdict),'spike_update_ordinals':spikes,'proof':proof,
        'failure_observations':manifest.get('failure_observations',[]),'frozen':False}


def confirm_sdp(manifest, policy, *, run=None):
    p = policy.rules.get('SDP_confirmation')
    require(type(p) is dict and set(p) == {'groups','minimum_observed_updates','minimum_nonzero_probes',
            'minimum_relative_loss_improvement','validation_seed','validation_epoch'}, 'Explicit SDP learning policy required')
    require(set(p['groups']) == {'S','D','P'}, 'SDP requires every registered group')
    integer(p['minimum_observed_updates'],1); integer(p['minimum_nonzero_probes'],1)
    integer(p['validation_seed']); integer(p['validation_epoch'])
    require(_number(p['minimum_relative_loss_improvement']) >= 0, 'Explicit nonnegative learning threshold required')
    rows, proof = closed_series(manifest,policy,run=run)
    require(all(t['C0'] for t in proof['terminals']), 'SDP confirmation needs actual successful closed training')
    config = bound_json(bound_json(manifest['segments'][0])['configuration'])
    require(config['proxy_contract']['groups'] == ['S','D','P'], 'SDP confirmation cannot consume an S-only/P-only run')
    stability=classify_stability(manifest,policy,run=run)
    training=[r for r in rows if r['event'] == 'TRAIN_STEP' and r['optimizer_updated']]
    checks={}
    for group,fields in p['groups'].items():
        require(type(fields) is list and fields and len(set(fields)) == len(fields), 'Fixed registry field list per group required')
        observed=sum(all(type(r.get('valid_count/'+f)) is int and r['valid_count/'+f] > 0 for f in fields) for r in training)
        probes=sum(_number(r['shared_gradient_norm/'+group]) > 0 for r in training if 'shared_gradient_norm/'+group in r)
        roles={}
        for role in ('VAL','TRAIN_UNSEEN_CONFORMATION'):
            v=[r for r in rows if r['event'] == 'VALIDATION' and r.get('role') == role]
            require(len(v) >= 2, 'Initial and final full fixed-cohort validation required')
            a,b=v[0],v[-1]
            for item in (a,b):
                integer(item['validation_seed']);integer(item['validation_epoch'])
            context=config['proxy_contract']['validation']
            require(a['samples_consumed'] == 0 and b['samples_consumed'] == proof['final']['samples_consumed']
                and a['population_binding_sha256'] == context['population_bindings'][role]
                and context['seed'] == p['validation_seed'] and context['epoch'] == p['validation_epoch']
                and a['samples_consumed'] < b['samples_consumed']
                and a['validation_seed'] == b['validation_seed'] == p['validation_seed']
                and a['validation_epoch'] == b['validation_epoch'] == p['validation_epoch']
                and a['population_binding_sha256'] == b['population_binding_sha256']
                and a['input_population_sha256'] == b['input_population_sha256'], 'Fixed validation cohort/context changed')
            for key in ('population_binding_sha256','input_population_sha256'): digest(a[key])
            av,bv=[],[]
            for f in fields:
                aa,bb=a['fields'][f],b['fields'][f]
                require(type(aa['valid_labels']) is int and aa['valid_labels'] > 0 and aa['valid_labels'] == bb['valid_labels'], 'Group validation coverage changed or missing')
                av.append(_number(aa['loss'])); bv.append(_number(bb['loss']))
            before,after=statistics.mean(av),statistics.mean(bv)
            require(before > 0, 'Relative learning requires positive initial group loss')
            gain=(before-after)/before
            roles[role]={'initial_equal_field_loss':before,'final_equal_field_loss':after,'relative_improvement':gain,
                         'learning':gain >= p['minimum_relative_loss_improvement']}
        checks[group]={'observed_updates':observed,'nonzero_group_probes':probes,'roles':roles,
            'passed':observed >= p['minimum_observed_updates'] and probes >= p['minimum_nonzero_probes'] and all(x['learning'] for x in roles.values())}
    stable=not stability['stability']['diverged'] and not stability['stability']['loss_spike']
    return {'schema':'model_v3_SDP_recipe_confirmation_proposal_v1','status':'PROPOSED_CONFIRMATION' if stable and all(c['passed'] for c in checks.values()) else 'REPORT_REQUIRED',
            'groups':checks,'stability':stability,'proof':proof,'frozen':False,'scientific_acceptance':False}


def verify_failure_exclusions(failures,measurements,policy):
    """Conservatively exclude actual numeric failures without fabricating a score.

    Every failed condition needs a raw C-nonzero Root capture, a pinned numeric
    failure observation and the exact preregistered configuration identity.
    Successful conditions still supply inspected panels. No missing attempt is
    silently counted as a failed or repeated seed.
    """
    from .v3_proxy_run import identity
    from .v3_decision_rules import LR_GRID
    require(type(failures) is dict and set(failures) <= {'S','P'},'Explicit failed condition registry required')
    excluded=set()
    for condition,names in failures.items():
        require(type(names) is dict and set(names) <= set(LR_GRID),'Unknown failed LR candidate')
        for lr,reference in names.items():
            m=bound_json(reference); result=classify_stability(m,policy)
            require(result['stability']['diverged'] and any(not t['C0'] for t in result['proof']['terminals']),
                'Failure exclusion needs actual nonzero numeric failure, not a bool')
            require(not measurements[condition][lr],'A condition cannot claim both failed and successful panel')
            initial=policy.rules['learning_rate']['pretraining_seed_roles']['initial']
            require(type(m['seed']) is int and m['seed'] == initial,'Failed actual initial seed differs')
            expected=policy.rules.get('failed_training_configurations',{}).get(condition,{}).get(lr)
            require(type(expected) is str,'Preregistered exact failed-candidate configuration required')
            for segment in m['segments']:
                cfg=bound_json(bound_json(segment)['configuration'])
                c=cfg['proxy_contract']
                require(c['groups'] == [condition] and c['optimizer']['lr'] == float(lr)
                    and c['sample_budget'] == policy.rules['recipe']['sample_budget'],'Failed config does not implement the attempted condition/LR/budget')
                require(identity(cfg) == expected,'Failed actual configuration differs from preregistration')
            excluded.add(lr)
    for condition in ('S','P'):
        require(set(measurements[condition]) == set(LR_GRID),'All five attempted rates must be explicit')
        for lr,rows in measurements[condition].items():
            require(rows or lr in failures.get(condition,{}),'Missing panel is not failure evidence')
    return excluded
