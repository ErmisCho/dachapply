"""TASK-370: private fixture export and isolated, real-service experiments."""
import base64
import hashlib
import inspect
import json
import os
import platform
import shutil
import tempfile
import time
import uuid
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from threading import Event, Thread, local
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.db.models import Q
from django.test.utils import override_settings

from jobradar.models import CvAsset, JobEvaluation, JobLead, UserProfile
from jobradar.services import application_prep as prep, cv_generator as gen, cv_tasks, cv_workspace, job_evaluator
from jobradar.services.prompt_builder import PROFILE_FIELD_NAMES


def outside_repo(value):  # TASK-370: resolve symlinks and worktree/common repository ancestors.
    path = Path(value).resolve()
    here = Path(__file__).resolve()
    root = next(p for p in here.parents if (p / '.git').exists())
    roots = [root]
    marker = root / '.git'
    if marker.is_file():
        gitdir = Path(marker.read_text(encoding='utf-8').strip().removeprefix('gitdir: ').strip())
        if not gitdir.is_absolute():
            gitdir = root / gitdir
        common = gitdir / 'commondir'
        if common.is_file():
            roots.append((gitdir / common.read_text(encoding='utf-8').strip()).resolve().parent)
    if any(path == root or root in path.parents for root in roots):
        raise CommandError('Output must be outside the git repository.')
    return path


def write_json(path, value):
    path.write_text(json.dumps(value, cls=DjangoJSONEncoder, indent=2), encoding='utf-8')


def fields(model):
    return [f.attname for f in model._meta.concrete_fields if not f.is_relation and not f.primary_key and not getattr(f, 'auto_now', False) and not getattr(f, 'auto_now_add', False)]


def export_fixture(email, selection, output):  # TASK-370: no model instances, save hooks or lazy profile creation.
    output = outside_repo(output)
    if output.exists():
        raise CommandError('Output already exists; choose a fresh directory.')
    profile_fields = list(dict.fromkeys(PROFILE_FIELD_NAMES + ['candidate_evidence', 'learned_application_preferences', 'evaluation_prompt_template',
        'combined_prompt_template', 'enrichment_prompt_template', 'use_cloud_models_only', 'can_generate_cv', 'analysis_concurrency',
        'analysis_time_limit_minutes', 'daily_analyse_limit', 'daily_prepare_limit', 'auto_pipeline_daily_limit']))

    def read_only(execute, sql, params, many, context):
        if not sql.lstrip().upper().startswith('SELECT'):
            raise CommandError('Benchmark export permits SELECT only.')
        return execute(sql, params, many, context)

    with transaction.atomic():
        with connection.execute_wrapper(read_only):
            user = get_user_model().objects.values('id', 'email', 'first_name', 'last_name').get(email__iexact=email)
            profile = UserProfile.whole.filter(user_id=user['id']).values(*profile_fields).get()
            jobs = JobLead.objects.filter(Q(submitted_for_id=user['id']) | Q(created_by_id=user['id'], submitted_for__isnull=True))
            if ',' in selection or selection.startswith('ids:'):
                ids = [int(v) for v in selection.removeprefix('ids:').split(',')]
                rows = list(jobs.filter(pk__in=ids).order_by('id').values('id', *fields(JobLead)))
                if {r['id'] for r in rows} != set(ids):
                    raise CommandError('Some selected jobs are missing or not owned by this account.')
            else:
                count = int(selection)
                if count < 1:
                    raise CommandError('Job count must be positive.')
                rows = list(jobs.filter(status__in=('new', 'to_apply')).exclude(original_source_text='', raw_description='').order_by('-created_at').values('id', *fields(JobLead))[:count])
            for row in rows:
                row['evaluations'] = list(JobEvaluation.objects.filter(job_id=row['id']).order_by('created_at').values(*fields(JobEvaluation)))
            assets = list(CvAsset.objects.filter(user_id=user['id']).values(*fields(CvAsset)))
        transaction.set_rollback(True)
    if not rows:
        raise CommandError('No matching jobs with postings.')
    source = Path(settings.CODEX_CV_WORKSPACE)
    # TASK-370: exact generator inputs, never generated documents, sidecars or cache.
    if not assets:
        if email.lower() != (settings.CODEX_CV_OWNER_EMAIL or '').lower():
            raise CommandError('Account has no stored assets and is not the workspace owner.')
    output.mkdir(parents=True)
    workspace = output / 'workspace'
    workspace.mkdir()
    if not assets:
        relatives = [cv_workspace.PHOTO_PATH]
        for layout in cv_workspace.WORKSPACE_LAYOUT.values():
            relatives += [str(cv_workspace.latest_versioned(source, layout['cv'][0]).relative_to(source))]
            relatives += [relative for relative, label in layout['letters'].values()]
        for relative in relatives:
            path = source / relative
            if path.is_file():
                dest = workspace / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)
    for asset in assets:
        asset['image'] = base64.b64encode(bytes(asset['image'])).decode()
        asset['source_path'] = ''
    for setting, name in [('CODEX_CANDIDATE_EVIDENCE_PATH', 'candidate-evidence.md'), ('CODEX_APPLICATION_RULES_PATH', 'application-rules.md')]:
        if setting == 'CODEX_CANDIDATE_EVIDENCE_PATH' and profile['candidate_evidence'].strip():
            continue
        path = Path(getattr(settings, setting))
        if path.is_file():
            shutil.copyfile(path, workspace / name)
    write_json(output / 'jobs.json', rows)
    write_json(output / 'profile.json', {'user': user, 'profile': profile, 'assets': assets,
        'conditions': {'document_limit': settings.PREP_QUEUE_CONCURRENCY, 'model': list(gen.CV_DEFAULT_MODEL),
                       'effort': gen.CV_DEFAULT_EFFORT, 'speed': 'normal',
                       'learned_preferences_budget': settings.CODEX_LEARNED_PREFERENCES_BUDGET}})
    return len(rows)


def error_class(exc):
    return 'cancellation' if isinstance(exc, gen.GenerationCancelled) else 'provider-limit' if getattr(exc, 'usage_limit', False) else 'failure'


class Recorder:  # TASK-370: wrappers retain the real service boundary, including model repairs.
    def __init__(self, workspace):
        self.workspace, self.requests, self.artifacts, self.resources = Path(workspace), [], [], []
        self.context = local()

    def model(self, original):
        signature = inspect.signature(original)
        def call(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            row = {k: bound.arguments[k] for k in ('provider', 'model', 'effort', 'speed')}
            row.update(getattr(self.context, 'identity', {}), start=time.time(), status='success', error_class=None,
                       repair='AUTOMATIC REPAIR ATTEMPT' in str(bound.arguments.get('prompt', '')))
            try:
                return original(*args, **kwargs)
            except BaseException as exc:
                row.update(status='error', error_class=error_class(exc), exception=type(exc).__name__)
                raise
            finally:
                row['end'] = time.time()
                self.requests.append(row)
        return call

    def generate(self, original):
        signature = inspect.signature(original)
        def call(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            job = bound.arguments['job']
            identity = {'job_id': job.pk, 'user_id': bound.arguments.get('user_id')}
            self.context.identity = identity
            try:
                result = original(*args, **kwargs)
                for kind, value in result[2].items():
                    if kind.endswith(('_tex', '_pdf')):
                        path = Path(value).resolve()
                        pages = None
                        if path.suffix == '.pdf' and shutil.which('pdfinfo'):
                            try:
                                pages = gen._pdf_pages(path)
                            except RuntimeError:
                                pass
                        self.artifacts.append({**identity, 'kind': kind, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'pages': pages})
                return result
            finally:
                self.context.identity = {}
        return call

    def sample(self, stop):
        try:
            import psutil
        except ImportError:
            self.resources.append({'status': 'unavailable'})
            return
        process = psutil.Process()
        while True:
            processes = [process, *process.children(recursive=True)]
            cpu, ram = 0, 0
            for child in processes:
                try:
                    times = child.cpu_times()
                    cpu += times.user + times.system
                    ram += child.memory_info().rss
                except psutil.Error:
                    pass
            self.resources.append({'time': time.time(), 'cpu_seconds': cpu, 'rss_bytes': ram})
            if stop.wait(2):
                return

    def overwrite_check(self, owners):
        seen, errors = set(), []
        for row in self.artifacts:
            path = Path(row['path'])
            if row['path'] in seen:
                errors.append({'path': str(path), 'reason': 'duplicate artifact path'})
            seen.add(row['path'])
            if owners.get(row['job_id']) != row['user_id'] or self.workspace.resolve() not in path.parents:
                errors.append({'path': str(path), 'reason': 'job/account/workspace mismatch'})
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                errors.append({'path': str(path), 'reason': 'artifact changed or missing'})
        return {'ok': not errors, 'errors': errors}


def metrics(states, started, ended):
    useful, ready, errors = [], 0, []
    for state in states:
        variants = list(state.get('variants', {}).values())
        for cv in [v for v in variants if v['document'] == 'cv']:
            wanted = [cv, *[v for v in variants if (v.get('recommended') or v['document'] == 'message') and v.get('language') == cv.get('language')]]
            if all(v['status'] == 'ready' for v in wanted):
                useful.append(max(datetime.fromisoformat(v['finished_at']).timestamp() for v in wanted) - started)
        ready += sum(v['status'] == 'ready' for v in variants)
        errors += [{'status': v['status'], 'error_class': 'cancellation' if v['status'] == 'cancelled' else 'provider-limit' if v.get('retry_at') else 'failure'} for v in variants if v['status'] in ('failed', 'cancelled')]
        if state.get('reason') and not variants:
            errors.append({'status': 'blocked', 'error_class': 'failure'})
    elapsed = ended - started
    return {'time_to_first_useful_package_seconds': min(useful) if useful else None, 'total_seconds': elapsed,
            'ready_documents': ready, 'documents_per_minute': ready * 60 / elapsed if elapsed else 0, 'errors': errors}


def concurrency(jobs, user, workers, variant):  # TASK-370: all variants, original queue gates and retries unchanged.
    if variant:
        raise CommandError('concurrency has no variants; compare --workers 1 and 2.')
    try:
        for job in jobs:
            prep.prepare(job.pk, user, inline=True)
        while True:
            with prep._lock:
                if not prep._queue and not prep._running and not prep._analysing:
                    return [prep._state(job, user) for job in jobs]
            time.sleep(.05)
    except BaseException:
        # TASK-370: drain workers before restoring the workspace/settings on interruption.
        for job in jobs:
            for key, item in prep._state(job, user).get('variants', {}).items():
                if item['status'] in ('queued', 'running'):
                    try:
                        prep.queue_action(user, job.pk, key, 'cancel')
                    except ValueError:
                        pass  # finished between snapshot and cancellation
        while prep._running or prep._analysing:
            time.sleep(.05)
        raise


EXPERIMENTS = {'concurrency': concurrency}  # TASK-370: 368/369 add name -> (jobs, user, workers, variant) functions.


def run_fixture(fixture, experiment, variant, workers, output):
    if connection.vendor != 'sqlite':
        raise CommandError('Benchmark runs require a scratch sqlite database.')
    if workers < 1 or experiment not in EXPERIMENTS:
        raise CommandError('Choose a registered experiment and a positive worker count.')
    output = outside_repo(output)
    if output.exists():
        raise CommandError('Output already exists; choose a fresh directory.')
    # TASK-370: refuse populated scratch databases to avoid unrelated jobs/accounts and queue work.
    if get_user_model().objects.exists() or JobLead.objects.exists():
        raise CommandError('Use a freshly migrated empty scratch database for each run.')
    if prep._queue or prep._running or prep._analysing:
        raise CommandError('Benchmark requires an idle document queue.')
    fixture = Path(fixture).resolve()
    data = json.loads((fixture / 'profile.json').read_text(encoding='utf-8'))
    rows = json.loads((fixture / 'jobs.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True)
    # Kept for artifact review; each run gets a fresh system-temp workspace.
    workspace = Path(tempfile.mkdtemp(prefix='dachapply-benchmark-'))
    shutil.copytree(fixture / 'workspace', workspace, dirs_exist_ok=True)
    recorder = Recorder(workspace)
    stop = Event()
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {'DACHAPPLY_CONTROL_DB': ''}))
        stack.enter_context(override_settings(CODEX_CV_WORKSPACE=str(workspace), CODEX_CV_ENABLED=True,
            CODEX_CV_OWNER_EMAIL=data['user']['email'], PREP_QUEUE_CONCURRENCY=workers,
            CODEX_CANDIDATE_EVIDENCE_PATH=str(workspace / 'candidate-evidence.md'),
            CODEX_APPLICATION_RULES_PATH=str(workspace / 'application-rules.md'),
            CODEX_LEARNED_PREFERENCES_BUDGET=data['conditions']['learned_preferences_budget']))
        choice = gen.cv_default_choice
        def matched_choice(options):
            option, effort = choice(options)
            if not option or [option['provider'], option['key']] != data['conditions']['model'] or effort != data['conditions']['effort']:
                raise CommandError('Exported document model/effort unavailable; refusing an unmatched workload.')
            return option, effort
        stack.enter_context(patch.object(prep, 'cv_default_choice', matched_choice))
        for module in (gen, prep, job_evaluator):
            stack.enter_context(patch.object(module, 'run_structured_model', recorder.model(module.run_structured_model)))
        stack.enter_context(patch.object(cv_tasks, 'generate_cv_package', recorder.generate(cv_tasks.generate_cv_package)))
        user = get_user_model().objects.create(username='benchmark-' + uuid.uuid4().hex, **{k: data['user'][k] for k in ('email', 'first_name', 'last_name')})
        UserProfile.whole.update_or_create(user=user, defaults=data['profile'])
        for asset in data['assets']:
            asset['image'] = base64.b64decode(asset['image'])
            CvAsset.objects.create(user=user, **asset)
        jobs, mapping = [], {}
        for row in rows:
            values = dict(row)
            original = values.pop('id')
            evaluations = values.pop('evaluations')
            job = JobLead.objects.create(created_by=user, **values)
            jobs.append(job)
            mapping[original] = job.pk
            for evaluation in evaluations:
                JobEvaluation.objects.create(job=job, **evaluation)
        started = time.time()
        sampler = Thread(target=recorder.sample, args=(stop,), daemon=True)
        sampler.start()
        try:
            states = EXPERIMENTS[experiment](jobs, user, workers, variant)
        finally:
            stop.set()
            sampler.join()
        ended = time.time()
    result = {'experiment': experiment, 'variant': variant, 'workers': workers, 'fixture': str(fixture), 'workspace': str(workspace),
        'conditions': data['conditions'], 'platform': platform.platform(), 'job_mapping': mapping, 'started': started, 'ended': ended,
        'requests': recorder.requests, 'artifacts': recorder.artifacts, 'resources': recorder.resources, 'states': states,
        'metrics': metrics(states, started, ended), 'overwrite_check': recorder.overwrite_check({j.pk: user.pk for j in jobs})}
    # TASK-370: verify the durable queue associates every recorded file with its originating job.
    claims = {(job.pk, user.pk, str(Path(path).resolve())) for job, state in zip(jobs, states)
              for v in state.get('variants', {}).values() for path in v.get('files', {}).values()}
    for artifact in recorder.artifacts:
        if (artifact['job_id'], artifact['user_id'], artifact['path']) not in claims:
            result['overwrite_check']['errors'].append({'path': artifact['path'], 'reason': 'artifact absent from owning job preparation'})
    result['overwrite_check']['ok'] = not result['overwrite_check']['errors']
    write_json(output / 'results.json', result)
    summary = result['metrics']
    (output / 'summary.md').write_text(f"# Document benchmark: {experiment}\n\nWorkers: {workers}; exported document limit: {data['conditions']['document_limit']}. Jobs: {len(jobs)}.\n\n"
        f"First useful package: {summary['time_to_first_useful_package_seconds']} seconds. Total: {summary['total_seconds']:.2f} seconds. "
        f"Throughput: {summary['documents_per_minute']:.2f} documents/minute. Errors: {len(summary['errors'])}. "
        f"Repairs: {sum(r['repair'] for r in recorder.requests)}. Overwrite check: {result['overwrite_check']['ok']}.\n\n"
        f"Workspace: {workspace}\n\nPrivate data. CPU/RAM samples, request errors and artifact hashes/pages are in results.json. "
        "Review document quality manually. No production default changed; retain one worker pending matched measurements and quality review. "
        "Reject higher concurrency if provider limits, failures or resource pressure increase.\n", encoding='utf-8')
    return result
