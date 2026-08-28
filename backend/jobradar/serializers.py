import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db.models.functions import Substr
from django.utils import timezone
from rest_framework import serializers
from .models import JobLead, JobEvaluation, ApplicationNote, FollowUp, InviteCode, MailboxDraft, MailboxMessage, MailboxRun, MailboxSuggestion, PracticeSession, UserProfile
from .services.skill_matcher import smart_skill_status, display_skill_name
from .services.access import accessible_jobs
from .services.demo_data import is_demo_job_payload, is_demo_user
from .services.prompt_builder import decode_profile_value, encode_profile_value
from .services.cleaning import clean_job_location


def normalize_job_url(value):
    """Accept normal URLs plus common copy/paste mistakes like
    https-www.karriere.at-jobs-7794074 -> https://www.karriere.at/jobs/7794074.
    Also repairs markdown/corrupted values such as https://[https://example.com/job.
    """
    raw=(value or '').strip()
    value=raw.replace('https://[https://','https://').replace('http://[http://','http://').strip('[]()<>.,;')
    embedded=re.findall(r'https?://[^\s\[\])>"}]+', value)
    if embedded:
        value=embedded[-1].strip('[]()<>.,;')
    if not value:
        return ''
    if value.startswith('http://') or value.startswith('https://'):
        parts=urlsplit(value)
        query=urlencode([(key,val) for key,val in parse_qsl(parts.query, keep_blank_values=True) if not key.lower().startswith('utm_') and key.lower() not in {'utm','fbclid','gclid','msclkid'}])
        return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/'), query, ''))
    if value.startswith('https-') or value.startswith('http-'):
        scheme, rest=value.split('-', 1)
        parts=rest.split('-')
        if len(parts) >= 2 and '.' in parts[0]:
            return f'{scheme}://' + parts[0] + '/' + '/'.join(parts[1:])
    if '.' in value and ' ' not in value:
        return 'https://' + value
    return value


def value_is_valid_url(value):
    raw=str(value or '').strip()
    if '](' in raw or (' ' in raw and not raw.startswith(('http://','https://','http-','https-'))):
        return False
    value=normalize_job_url(raw)
    if not value:
        return False
    try:
        serializers.URLField(max_length=1000).run_validation(value)
        return True
    except serializers.ValidationError:
        return False


# TASK-133 AC3/AC7: the owner edits To/Cc by hand before a reply is saved, so those addresses need
# the same "is this even well-formed" floor value_is_valid_url gives a pasted URL above. Django's own
# validate_email (no new dependency, same rung normalize_job_url already reaches for with DRF's
# URLField) -- never a hand-rolled regex for something this security-adjacent.
def invalid_email_addresses(addresses):
    """The subset of `addresses` that are not a well-formed email address, in the order given.
    Blank/whitespace-only entries count as invalid too -- a To/Cc slot has nothing to say empty.
    """
    invalid = []
    for addr in addresses:
        addr = (addr or '').strip()
        if not addr:
            invalid.append(addr or '(empty)')
            continue
        try:
            validate_email(addr)
        except DjangoValidationError:
            invalid.append(addr)
    return invalid


def extract_url_from_text(value):
    text=str(value or '')
    m=re.search(r'https?://[^\s)\]]+', text)
    if not m: return ''
    return normalize_job_url(m.group(0).split('%22')[0].split('"')[0].rstrip('.,;'))


def clean_label_text(value):
    text=str(value or '').strip()
    if not text: return ''
    if '](' in text:
        before=text.split('](',1)[0].lstrip('[').strip()
        suffix=text.split(')',1)[1].strip() if ')' in text else ''
        text=(before + (' ' + suffix if suffix else '')).strip()
    text=re.sub(r'https?://[^\s)\]]+', '', text)
    text=text.replace('[','').replace(']','').replace('%22','').replace('"','')
    return re.sub(r'\s+', ' ', text).strip(' ,;:-')


def clean_job_title(value):
    text=clean_label_text(value)
    text=re.sub(r'\s*[-–—,;:]*\s*\(?\s*[mwfdx](?:\s*/\s*[mwfdx]){1,3}\s*\)?\s*$', '', text, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', text).strip(' ,;:-')


class CandidateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=UserProfile
        # TASK-125 AC1/AC2: mailbox_check_enabled/window_start/window_end sit next to the existing
        # cadence/calendar_aware fields, where the owner already looks for mailbox settings.
        # TASK-141 AC1/AC2: mailbox_lookback_months sits next to the cadence field it shares its
        # validation shape with -- same place on the settings page as every other mailbox control.
        # TASK-145 AC4/AC8: board_sort_keys sits with the other board/mailbox settings this
        # serializer already exposes plainly.
        # TASK-116: mailbox_calendar_ids replaces TASK-115's mailbox_calendar_ics_urls -- a Google
        # Calendar id carries no secret (unlike the ICS URL it replaces), so, unlike every other field
        # that used to need TASK-115's masking treatment, it is exposed here exactly like every other
        # plain field: no masking below, no merge in update().
        # TASK-169: mailbox_identify_window_months sits right next to mailbox_lookback_months -- same
        # family, deliberately a different field (see the model comment on both for why fetch and
        # identify must not share one setting).
        fields=('candidate_profile','candidate_evidence','target_roles','preferred_locations','salary_expectations','language_levels','preferred_stack','red_flags','selling_points','learned_application_preferences','follow_up_digest_enabled','mailbox_check_cadence_minutes','mailbox_check_calendar_aware','mailbox_check_enabled','mailbox_check_window_start','mailbox_check_window_end','mailbox_lookback_months','mailbox_identify_window_months','mailbox_salary_floor_eur','mailbox_do_not_disclose','mailbox_calendar_ids','board_sort_keys','evaluation_prompt_template','combined_prompt_template','enrichment_prompt_template','bulk_links_prompt_template')
    # The profile codec is a text codec: it JSON-wraps values for drifted SQLite schemas and
    # coerces falsy values to ''. Running a boolean through it would store '' in a
    # BooleanField and serialise False as ''. Booleans (and mailbox_check_cadence_minutes, an int
    # that is never 0 per the validator below) pass through untouched.
    def to_representation(self, instance):
        data=super().to_representation(instance)
        # TASK-169: `or v is None` added for mailbox_identify_window_months, the first field in this
        # serializer that is genuinely nullable rather than defaulting to '' -- without it, None (not
        # isinstance of bool/int) would fall into decode_profile_value(None), which returns '' (its
        # "falsy input" branch), silently turning an explicit "not set yet" into the WRONG kind of
        # falsy (the text-field idiom, not this field's own null-means-unset one). No existing field
        # can be None (every other field here has a non-null default), so this changes nothing else.
        data={k: (v if isinstance(v, (bool, int)) or v is None else decode_profile_value(v)) for k,v in data.items()}
        return data
    # No validate_candidate_profile: clearing the field used to store somebody else's bio instead,
    # so a user could never actually empty it. Empty now stays empty and prompt generation refuses.
    def validate_mailbox_check_cadence_minutes(self, v):
        # TASK-109 AC8. Floor of 5: check_mailbox's own cadence gate already makes anything faster
        # pointless (IMAP round-trips alone cost more than that), and 0 would read back as '' through
        # the profile codec above (encode_profile_value treats a falsy value as unset).
        if v < 5 or v > 1440:
            raise serializers.ValidationError('Mailbox check cadence must be between 5 and 1440 minutes.')
        return v
    def validate_mailbox_lookback_months(self, v):
        # TASK-141 AC3: 0 (or blank, already rejected by PositiveIntegerField's own type coercion
        # before this ever runs) must not mean "unlimited" -- that is exactly the bug this field's
        # model comment (models.py, UserProfile.mailbox_lookback_months) warns against copying from
        # mailbox_check_cadence_minutes' "falsy is unset" idiom. Accepted range: 1-60 months (five
        # years) -- same floor/ceiling shape as the cadence validator above, sized so the window stays
        # a window rather than reading as "no limit" spelled as a very large number.
        if v < 1 or v > 60:
            raise serializers.ValidationError('Mailbox lookback must be between 1 and 60 months.')
        return v
    def validate_mailbox_identify_window_months(self, v):
        # TASK-169 AC4/AC7: same range/reasoning as validate_mailbox_lookback_months above -- 0 must
        # never read back as "unlimited". Unlike that field, None IS accepted here and means something
        # different from 0: "the owner has not explicitly chosen a window" (views.py's `unmatched`
        # action reads that as the 3-month default), not "off"/"unbounded" -- see the model field's own
        # comment for why this needed a nullable field rather than mailbox_check_cadence_minutes'
        # 0-means-unset idiom. Sending None is how the owner resets back to the default explicitly.
        if v is None:
            return v
        if v < 1 or v > 60:
            raise serializers.ValidationError('Identification window must be between 1 and 60 months.')
        return v
    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            # TASK-169: see to_representation's own comment -- None must pass through untouched here
            # too, or PATCHing mailbox_identify_window_months back to null would encode_profile_value
            # it into '' and try to store that in an integer column.
            setattr(instance, field, value if isinstance(value, (bool, int)) or value is None else encode_profile_value(field, value))
        instance.save(update_fields=list(validated_data.keys()))
        return instance

class JobEvaluationSerializer(serializers.ModelSerializer):
    skill_statuses=serializers.SerializerMethodField()
    class Meta:
        model=JobEvaluation; fields='__all__'; read_only_fields=('created_at','updated_at')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request=self.context.get('request') if hasattr(self, 'context') else None
        if request and 'job' in self.fields:
            self.fields['job'].queryset=accessible_jobs(request.user)
    def get_skill_statuses(self, obj):
        skills=[]
        for s in (obj.required_skills or []) + (obj.nice_to_have_skills or []) + (obj.missing_skills or []) + (obj.matched_skills or []):
            if s and s not in skills: skills.append(s)
        return {s: {'status': smart_skill_status(s), 'display': display_skill_name(s)} for s in skills}
    def validate_fit_score(self, v):
        if v < 0 or v > 100: raise serializers.ValidationError('fit_score must be 0..100')
        return v

class ApplicationNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model=ApplicationNote; fields='__all__'; read_only_fields=('created_by','created_at')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request=self.context.get('request') if hasattr(self, 'context') else None
        if request and 'job' in self.fields:
            self.fields['job'].queryset=accessible_jobs(request.user)

class FollowUpSerializer(serializers.ModelSerializer):
    company=serializers.CharField(source='job.company', read_only=True)
    title=serializers.CharField(source='job.title', read_only=True)
    class Meta:
        model=FollowUp; fields='__all__'; read_only_fields=('created_at','updated_at')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request=self.context.get('request') if hasattr(self, 'context') else None
        if request and 'job' in self.fields:
            self.fields['job'].queryset=accessible_jobs(request.user)

class JobLeadSerializer(serializers.ModelSerializer):
    latest_evaluation=serializers.SerializerMethodField()
    created_by_username=serializers.SerializerMethodField()
    created_by_email=serializers.SerializerMethodField()
    submitted_for_username=serializers.SerializerMethodField()
    submitted_for_email=serializers.SerializerMethodField()
    url=serializers.CharField(max_length=1000, required=False, allow_blank=True)
    class Meta:
        model=JobLead; fields='__all__'; read_only_fields=('created_by','submitted_for','created_at','updated_at')
        extra_kwargs={'company': {'required': False, 'allow_blank': True}, 'title': {'required': False, 'allow_blank': True}}
    def validate_url(self, value):
        value=normalize_job_url(value)
        if value:
            serializers.URLField(max_length=1000).run_validation(value)
        return value
    def validate(self, attrs):
        embedded=extract_url_from_text(attrs.get('url')) or extract_url_from_text(attrs.get('company')) or extract_url_from_text(attrs.get('title'))
        if embedded and not attrs.get('url'):
            attrs['url']=embedded
        if attrs.get('url'):
            attrs['url']=normalize_job_url(extract_url_from_text(attrs.get('url')) or attrs.get('url'))
        if not attrs.get('url') and value_is_valid_url(attrs.get('company')):
            attrs['url']=normalize_job_url(attrs.get('company'))
            attrs['company']=''
        if 'company' in attrs: attrs['company']=clean_label_text(attrs.get('company'))
        if 'title' in attrs: attrs['title']=clean_job_title(attrs.get('title'))
        if 'location' in attrs: attrs['location']=clean_job_location(attrs.get('location'))
        current=self.instance
        request=self.context.get('request') if hasattr(self, 'context') else None
        if request and not is_demo_user(request.user) and is_demo_job_payload(attrs.get('url'), attrs.get('source')):
            raise serializers.ValidationError('Demo jobs are only available in the demo account.')
        has_content = any([
            attrs.get('url') or (current and current.url),
            attrs.get('raw_description') or (current and current.raw_description),
            attrs.get('company') or (current and current.company),
            attrs.get('title') or (current and current.title),
        ])
        if not has_content:
            raise serializers.ValidationError('Provide at least a URL, description, company, or title')
        return attrs
    def to_representation(self, instance):
        data=super().to_representation(instance)
        data['location']=clean_job_location(data.get('location'))
        return data
    def create(self, attrs):
        attrs['company']=attrs.get('company') or 'Unknown company'
        attrs['title']=attrs.get('title') or 'Untitled role'
        if attrs.get('status') in JobLead.DATED_STATUSES and not attrs.get('status_date'):
            attrs['status_date']=timezone.localdate()
        if attrs.get('status') not in JobLead.DATED_STATUSES:
            attrs['last_update_date']=None
        return super().create(attrs)
    def update(self, instance, attrs):
        new_status=attrs.get('status')
        if new_status in JobLead.DATED_STATUSES and instance.status != new_status and not attrs.get('status_date'):
            attrs['status_date']=timezone.localdate()
        status_for_last_update=new_status or instance.status
        if status_for_last_update not in JobLead.DATED_STATUSES:
            attrs['last_update_date']=None
        elif new_status and instance.status != new_status and not attrs.get('last_update_date'):
            attrs['last_update_date']=timezone.localdate()
        if new_status and new_status not in JobLead.DATED_STATUSES and instance.status != new_status and 'status_date' not in attrs:
            attrs['status_date']=None
            attrs['feedback_due_date']=None
        if new_status and new_status != 'interview':
            attrs['interview_stage']=None
            attrs['interview_total']=None
        return super().update(instance, attrs)
    def get_latest_evaluation(self, obj):
        ev=obj.evaluations.first()
        return JobEvaluationSerializer(ev).data if ev else None
    def get_created_by_username(self, obj): return obj.created_by.username if obj.created_by else ''
    def get_created_by_email(self, obj): return (obj.created_by.email or obj.created_by.username) if obj.created_by else ''
    def get_submitted_for_username(self, obj): return obj.submitted_for.username if obj.submitted_for else ''
    def get_submitted_for_email(self, obj): return (obj.submitted_for.email or obj.submitted_for.username) if obj.submitted_for else ''

class JobEvaluationListSerializer(JobEvaluationSerializer):
    """Nested evaluation for board rows only.

    Keeps exactly what the dashboard renders: the score/priority chips, MatchGapPopup
    (summary, main_match_reasons, main_gaps) and SkillLabels (required/matched/missing
    plus skill_statuses). Drops structured_json_raw -- the whole raw LLM reply, ~3.7KB
    per evaluation in the local snapshot and by far the biggest thing on the wire -- and
    the long-form notes only the detail page shows. recommendation stays because the
    board filters on it; skill_statuses is reduced to the required/matched/missing keys
    that SkillLabels can actually look up. The detail serializer keeps the complete map.
    """
    class Meta(JobEvaluationSerializer.Meta):
        fields=('id','fit_score','priority','recommendation','summary','main_match_reasons','main_gaps','required_skills','matched_skills','missing_skills','skill_statuses')
    def get_skill_statuses(self, obj):
        """The same map, carrying only what the board can actually read out of it.

        Measured on the owner's real 69-row board: skill_statuses was 181.8 KB of a 402.7 KB
        response -- 46% of the whole payload, the single biggest thing on the wire, at 37.4 entries
        per row against 31.6 skills the board ever looks up. Every byte below is dropped because
        App.tsx's SkillLabels provably cannot reach it, not because it looked expendable -- read
        that function alongside this one, they are a pair:

        1. Keys outside required + missing + matched go. SkillLabels builds its skill list from
           exactly those three arrays and looks each name up with `ev.skill_statuses?.[s]`, so a
           nice_to_have-only key has no lookup that can find it. (The parent still computes them:
           the DETAIL endpoint keeps the full map.) Measured: 328 of 2,506 keys.
        2. `display` goes when it equals the key. SkillLabels' `label()` falls back to the raw
           skill name when the entry has no display, and the entry then collapses to the bare
           status string -- a shape that function has always handled (`typeof meta(s)==='string'`).
           Measured: 687 of 2,178 reachable keys.
        3. `status: 'unknown'` goes. `tone()` reads 'match' -> green, 'weak' -> yellow, and
           *everything else* -> red, so an absent status and an 'unknown' one paint the identical
           chip. Measured: 1,385 of 2,178.
        4. An entry that is both (unknown status, display == key) disappears entirely, because
           SkillLabels renders a name with no entry at all exactly the same way. Measured: 294.

        Net 402,728 -> 330,238 B, 5,837 -> 4,786 B per row, with byte-identical chips: same names,
        same tones, same order (the sort is the client's and reads only these values), same hover
        tooltip, and the 360px card layout's limit={999} sees the same full list as the desktop
        table's limit={8}. This is the call JobEvaluationListSerializer's own docstring already made
        once for structured_json_raw, applied one field further down.
        """
        # dict-not-set so the key order stays the board's own (required, then missing, then
        # matched, first mention wins) instead of a hash order that would change between processes.
        rendered={}
        for name in (obj.required_skills or []) + (obj.missing_skills or []) + (obj.matched_skills or []):
            if name: rendered.setdefault(name, None)
        out={}
        for name in rendered:
            status=smart_skill_status(name); display=display_skill_name(name)
            if display == name:
                if status != 'unknown': out[name]=status
            elif status == 'unknown':
                out[name]={'display': display}
            else:
                out[name]={'status': status, 'display': display}
        return out

class JobLeadListSerializer(JobLeadSerializer):
    """/api/jobs/ list rows. The detail endpoint keeps every field.

    raw_description and original_source_text are a full job posting each and nothing on
    the board reads them from the list response -- the job detail page fetches
    /api/jobs/<id>/ for its editor and source-text pane.
    """
    # TASK-126 AC1/AC4: the board's mail indicator used to derive "this job has mail" only from
    # /mailbox-suggestions/ (pending-only), so it vanished the moment a suggestion was decided --
    # see the task's Description for the measured bug. This is the recorded decision from that
    # task's notes: option 1 (a field on the list response), not a second per-row request (option 2,
    # which TASK-91 was filed to avoid) or overloading /mailbox-suggestions/ to return decided rows
    # too (option 3). Read-only: sourced from the Exists() annotation JobLeadViewSet.get_queryset()
    # adds for every row already in this one list query, not a per-row lookup.
    has_mailbox_history=serializers.BooleanField(read_only=True, default=False)
    # TASK-178: the same shape, one field down, for the same reason. The board renders a `notes`
    # button on every row -- measured byte-identical on all 69 visible rows -- while only 12 of the
    # owner's 83 jobs carry a general note, so the affordance told the owner nothing. note_preview
    # is what both halves of the fix read: non-empty IS "this job has a note" (no second boolean to
    # keep in sync with it), and the string itself is the row's hover text. The full note still
    # comes from /jobs/<id>/notes/ when the modal opens, so no long-form prose joins this
    # deliberately trimmed payload. Sourced from the annotation JobLeadViewSet.get_queryset() adds
    # to this one list query, never a per-row request (option 2, which TASK-91 was filed to avoid).
    NOTE_PREVIEW_CHARS = 140
    # Bounded in SQL (the view's Substr annotation), never sliced out of the whole column here:
    # TASK-142 measured that mistake truncating the RESPONSE while the QUERY had already paid for
    # every row's full body. 2x + 1 rather than MailboxMessageListSerializer's exact CHARS + 1
    # because of the whitespace squeeze below -- a note's newlines and markdown-table padding
    # collapse to single spaces, so 141 raw chars can be fewer than 140 displayed ones. The trick
    # is the same either way: a raw value at the full fetch length means there is more note, which
    # is what earns the ellipsis when the squeeze came up short of the cap on its own.
    NOTE_PREVIEW_FETCH_CHARS = 2 * NOTE_PREVIEW_CHARS + 1
    note_preview=serializers.SerializerMethodField()
    class Meta(JobLeadSerializer.Meta):
        fields=None  # DRF forbids fields and exclude together; the parent sets fields='__all__'
        exclude=('raw_description','original_source_text')
    def get_note_preview(self, obj):
        """Server-side twin of appUtils.messagePreviewLine (TASK-177): same 140-char cap and the
        same whitespace squeeze, so a note preview and a mail preview never disagree about length.
        Squeezing first matters more here than there -- JobNotes composes a note as text + blank
        line + markdown tables, so a table-only note's literal first line is empty and a raw slice
        would preview it as nothing at all, which looks exactly like the "no note" case this field
        exists to tell apart. '' for a job with no general note; getattr keeps a stray direct
        instantiation without the annotation (a test, a reused serializer) from raising.
        """
        raw=getattr(obj, 'note_preview_raw', '') or ''
        line=re.sub(r'\s+', ' ', raw).strip()
        if len(line) > self.NOTE_PREVIEW_CHARS:
            return line[:self.NOTE_PREVIEW_CHARS].rstrip() + '…'
        return line + '…' if line and len(raw) >= self.NOTE_PREVIEW_FETCH_CHARS else line
    def get_latest_evaluation(self, obj):
        ev=obj.evaluations.first()
        return JobEvaluationListSerializer(ev).data if ev else None

class PracticeSessionSerializer(serializers.ModelSerializer):
    """A practice attempt. Scores/feedback/rewrite are server-computed, never client-writable."""
    job_company=serializers.CharField(source='job.company', read_only=True, default='')
    job_title=serializers.CharField(source='job.title', read_only=True, default='')
    class Meta:
        model=PracticeSession
        fields=('id','job','job_company','job_title','question','answer_text','language','clarity_score','structure_score','confidence_score','overall_score','feedback','stronger_answer','evaluator','model','fallback_used','created_at')
        read_only_fields=('clarity_score','structure_score','confidence_score','overall_score','feedback','stronger_answer','evaluator','model','fallback_used','created_at')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request=self.context.get('request') if hasattr(self, 'context') else None
        if request and 'job' in self.fields:
            # Scoped like every other job-linking serializer: a session may only point at a job
            # this user can already read (services.access.accessible_jobs), not any job by id.
            self.fields['job'].queryset=accessible_jobs(request.user)

class PracticeEvaluateSerializer(serializers.Serializer):
    """Input for POST /api/practice/evaluate/. Matches the coach's AnalyzeRequest bounds."""
    question=serializers.CharField(max_length=300, required=False, allow_blank=True, default='')
    answer_text=serializers.CharField(min_length=20, max_length=5000)
    language=serializers.ChoiceField(choices=PracticeSession.LANGUAGES)
    job=serializers.PrimaryKeyRelatedField(queryset=JobLead.objects.none(), required=False, allow_null=True)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request=self.context.get('request') if hasattr(self, 'context') else None
        if request:
            self.fields['job'].queryset=accessible_jobs(request.user)

# TASK-121 AC3: gmail_conversation_url is the single Gmail URL builder in the codebase -- it takes
# an RFC822 Message-ID (MailboxMessage.message_id) and returns '' when there is no usable id; both
# serializers below turn that into None rather than an empty string on the wire. Imported lazily
# (inside the function, not at module level) because services.mailbox itself imports
# JobLeadSerializer from this module -- a top-level import here would be circular.
def _gmail_url(message_id):
    # TASK-121 AC3/AC4, measured against the owner's real mailbox 2026-08-18: a bare
    # https://mail.google.com/mail/u/0/#search/... opens whichever Google account signed in FIRST in
    # that browser, not necessarily the mailbox the app reads. The owner had to hand-edit /u/0/ to
    # /u/3/ before the link found the message. Passing the mailbox's own address as authuser makes
    # the link say which account it means instead of relying on tab order.
    # Imported inside the function on purpose: services.mailbox imports JobLeadSerializer from this
    # module, so a module-level import here is a circular import that breaks the whole app.
    from .services.mailbox import _reply_from_address, gmail_conversation_url
    return gmail_conversation_url(message_id, authuser=_reply_from_address() or '') or None

class MailboxDraftSerializer(serializers.ModelSerializer):
    """TASK-110 AC5. Read-only everywhere -- MailboxDraft is append-only, same shape as
    MailboxMessageSerializer below. TASK-121 AC1: gmail_draft_id/gmail_message_id/gmail_thread_id
    are '' on every row written before that task, and on every row from a machine on the IMAP
    transport (no Gmail API ids at all).
    """
    # gmail_conversation_url only accepts an RFC822 Message-ID (see its docstring) --
    # gmail_message_id is a different, Gmail-internal id it does not understand. The draft's own
    # inbound message is the conversation this draft replies to, so that message's message_id is
    # the link target (null when that message has no usable id either -- TASK-121 AC4).
    gmail_url=serializers.SerializerMethodField()
    class Meta:
        model=MailboxDraft
        # TASK-122 AC4/AC5: chat_history is read-only here too -- the only writer is
        # MailboxDraftViewSet.chat (append on a successful turn) and .edit (reset on accept),
        # never a generic field on this serializer.
        fields=('id','status','block_reason','subject','body_text','evaluator','gmail_draft_id','gmail_message_id','gmail_thread_id','gmail_url','chat_history','created_at')
        read_only_fields=fields
    def get_gmail_url(self, obj):
        return _gmail_url(obj.message.message_id)

class MailboxMessageSerializer(serializers.ModelSerializer):
    """TASK-109. Read-only everywhere -- the model itself is the append-only log (AC5), so no
    serializer here ever gets wired to a PATCH/DELETE view.
    """
    matched_job_company=serializers.CharField(source='matched_job.company', read_only=True, default='')
    matched_job_title=serializers.CharField(source='matched_job.title', read_only=True, default='')
    # TASK-110: null when this message's classification never wanted a reply (or wanted one but had
    # no matched job) -- see services.mailbox._DRAFT_WORTHY_CLASSIFICATIONS. A SerializerMethodField
    # rather than a nested serializer because `obj.draft` raises DoesNotExist (caught here, not by
    # DRF) when the OneToOne reverse relation is absent.
    draft=serializers.SerializerMethodField()
    # TASK-121 AC4: null when this message's RFC822 Message-ID is not usable -- see _gmail_url above.
    gmail_url=serializers.SerializerMethodField()
    class Meta:
        model=MailboxMessage
        # TASK-117 AC1/AC2: body_text is the received body (5000-char cap applied at the wire read in
        # services.mailbox), stored now instead of dropped -- see MailboxMessage's docstring for why.
        # TASK-121 AC2: thread_id is the inbound Gmail thread id -- a different id from a draft's own
        # gmail_thread_id above. Exposed for completeness even though gmail_conversation_url does not
        # consume it today (it links by message_id alone -- see that function's docstring).
        # TASK-132/TASK-133 AC2: to_addrs/cc_addrs are the raw header text services.mailbox.
        # derive_reply_recipients() parses into reply/reply-all recipient lists -- exposed here too so
        # the client can render an exchange without a second request. sent_by_owner is the stored
        # (never guessed) flag distinguishing the owner's own sent mail from what they received, so a
        # conversation reads as an exchange rather than a flat list.
        # TASK-135: calendar_summary/calendar_location/calendar_organizer/calendar_start/calendar_end/
        # attachments were added to the model (migration 0042) but never added here -- see
        # MailboxMessage's own docstring for exactly what each holds. Read-only like everything else
        # in this serializer (ModelSerializer default for a field with no explicit writable=True).
        fields=('id','sender','subject','body_text','received_at','classification','matched_job','matched_job_company','matched_job_title','draft','thread_id','gmail_url','to_addrs','cc_addrs','sent_by_owner','created_at','calendar_summary','calendar_location','calendar_organizer','calendar_start','calendar_end','attachments')
    def get_draft(self, obj):
        draft=getattr(obj,'draft',None)
        return MailboxDraftSerializer(draft).data if draft else None
    def get_gmail_url(self, obj):
        return _gmail_url(obj.message_id)

class MailboxSuggestionSerializer(serializers.ModelSerializer):
    """TASK-109 AC3. Read-only: the only writes this model allows are the confirm/dismiss/postpone
    actions on MailboxSuggestionViewSet, never a generic PATCH of `status` or `payload`.

    TASK-175: `postponed_until` is read-only here too -- the postpone action takes its date from the
    request body and validates it itself (see that action), so this serializer stays a pure
    projection.
    """
    message=MailboxMessageSerializer(read_only=True)
    job_company=serializers.CharField(source='job.company', read_only=True)
    job_title=serializers.CharField(source='job.title', read_only=True)
    class Meta:
        model=MailboxSuggestion
        fields=('id','message','job','job_company','job_title','suggestion_type','payload','status','created_at','decided_at','postponed_until')
        read_only_fields=fields

class MailboxMessageListSerializer(MailboxMessageSerializer):
    """TASK-142 AC1: MailboxMessageViewSet.unmatched -- measured at 763 messages carrying 1,796,060
    characters of body_text (2,354 chars/message average) in one response, 10.5s to answer. A list
    row exists to be scanned (sender/subject/classification), not read in full, so body_text here is
    truncated to a preview -- never omitted outright, so the list still gives the owner something to
    recognise the thread by without opening it. `body_truncated` tells the client whether there is
    more to fetch. Nothing is deleted and nothing becomes unreachable (AC7): MailboxMessageViewSet.
    retrieve returns this same message with its FULL body_text, so the one row the owner actually
    opens is still completely readable in a single extra request -- see that method's docstring.

    TASK-142 AC2 (coordinator re-measurement, 2026-08-19): slicing body_text in
    to_representation() -- the previous shape of this serializer -- truncated the RESPONSE but not
    the QUERY: Django (and, in production, the Neon round-trip) had already paid for every row's
    full body_text before this code ever ran, so the endpoint got slower, not faster (12.3s, up from
    10.5s, as the message count grew). The view now `.defer('body_text')`s the real column and
    annotates a bounded `body_preview` (Substr, computed in SQL) instead -- this serializer reads
    THAT, never `instance.body_text` directly. Touching the deferred field here would silently
    trigger one reload query per row (Django's deferred-field descriptor), which is worse than the
    original bug: N extra round-trips instead of one oversized one.

    TASK-163: `suggested_job` reads the same body_preview annotation this serializer already uses,
    never a second body fetch -- see get_suggested_job below and the view's own comment.
    """
    BODY_PREVIEW_CHARS = 300
    body_text = serializers.SerializerMethodField()
    body_truncated = serializers.SerializerMethodField()
    # TASK-163 AC1/AC3: the view (MailboxMessageViewSet.unmatched) sets a transient `suggested_job`
    # attribute per row -- a JobLead or None, never a model field, never persisted -- computed by
    # services.mailbox.suggest_job_for_message. {'id', 'label'} is enough for the owner to recognise
    # the job and for the client to pre-fill/confirm the existing attach <select> with it; null when
    # the row's subject/body names no tracked company or names more than one (AC4: never a guess).
    suggested_job = serializers.SerializerMethodField()
    # TASK-171 AC3/AC4: true only when the view's `?include_dismissed=1` reveal actually included this
    # row (the default queryset excludes dismissed rows entirely) -- lets the client render a
    # "Restore" control instead of the attach picker for a revealed row, without a second request.
    dismissed = serializers.SerializerMethodField()
    # TASK-166 AC1/AC2: {'company', 'title', 'status'} the message itself supports, or null when this
    # message may not become a job lead at all (already attached, the owner's own mail, or a
    # classification that says nothing about an application's state -- see
    # services.mailbox.lead_fields_from_message, which owns every one of those rules). Shipped with
    # the row so the panel can pre-fill and the owner can confirm in one click without a second
    # request, exactly like suggested_job above. Costs no query and no body read: the extraction
    # looks at `subject`, `sender` and `classification` only, never body_text (still .defer()'d by
    # the view -- touching it here would trigger one reload query PER ROW, the regression TASK-142
    # removed). EMPTY company or title is a real, expected answer, not a failure: 25 of the 160
    # measured production rows name no employer anywhere the extraction is allowed to look, and AC2
    # requires those to arrive blank rather than guessed.
    lead_prefill = serializers.SerializerMethodField()
    class Meta(MailboxMessageSerializer.Meta):
        fields = MailboxMessageSerializer.Meta.fields + ('body_truncated', 'suggested_job', 'dismissed', 'lead_prefill')
    def get_dismissed(self, obj):
        return obj.dismissed_at is not None
    def get_lead_prefill(self, obj):
        from .services.mailbox import lead_fields_from_message  # local: see _gmail_url above
        fields = lead_fields_from_message(obj)
        return {k: fields[k] for k in ('company', 'title', 'status')} if fields else None
    def _preview(self, obj):
        # body_preview is the view's Substr(...) annotation -- (BODY_PREVIEW_CHARS + 1) chars, so its
        # own length (not a second query) is what tells truncated apart from whole-body-happened-to-
        # be-short. Falls back to '' for any caller that reuses this serializer without the
        # annotation (e.g. a stray direct instantiation in a test) rather than raising.
        return getattr(obj, 'body_preview', '') or ''
    def get_body_text(self, obj):
        preview = self._preview(obj)
        if len(preview) > self.BODY_PREVIEW_CHARS:
            return preview[:self.BODY_PREVIEW_CHARS].rstrip() + '…'
        return preview
    def get_body_truncated(self, obj):
        return len(self._preview(obj)) > self.BODY_PREVIEW_CHARS
    def get_suggested_job(self, obj):
        job = getattr(obj, 'suggested_job', None)
        return {'id': job.id, 'label': f'{job.company} — {job.title}'} if job else None

class MailboxMessageWithSuggestionsSerializer(MailboxMessageSerializer):
    """TASK-117 AC2/AC6: the per-job mailbox panel (JobLeadViewSet.mailbox) and the manual-attach
    response (MailboxMessageViewSet.attach) both need each message's still-pending suggestions
    alongside its draft. Kept off the base MailboxMessageSerializer above on purpose -- that one is
    nested inside MailboxSuggestionSerializer.message, and a `suggestions` field there would recurse
    into itself (suggestion -> message -> suggestions -> message -> ...).
    """
    suggestions=serializers.SerializerMethodField()
    class Meta(MailboxMessageSerializer.Meta):
        fields=MailboxMessageSerializer.Meta.fields + ('suggestions',)
    def get_suggestions(self, obj):
        return MailboxSuggestionSerializer(obj.suggestions.filter(status='pending'), many=True).data

# TASK-172: shared by both MailboxRunListSerializer.to_representation (the bulk, /api/mailbox-runs/
# list path) and MailboxRunSerializer.get_digest_messages' own single-object fallback below -- the
# exact bounded-preview query TASK-142 already built one endpoint over (MailboxMessageViewSet.
# unmatched), never a second implementation of the same Substr(...)/.defer('body_text') idiom.
# select_related('draft') is TASK-142's own fix for the reverse-one-to-one N+1 it measured (320
# queries for 319 rows); select_related('matched_job') is the ADDITIONAL join `unmatched` never
# needed -- that endpoint's own queryset filters matched_job__isnull=True, so matched_job_id is
# always NULL there and the forward FK never touches the DB either way (see that queryset's own
# comment in views.py) -- but a run's digest is NOT filtered that way: a job-related message here
# routinely HAS a matched_job, and MailboxMessageSerializer.matched_job_company/_title reads
# matched_job.company/.title, which would otherwise be one query per matched row.
def _digest_queryset(qs, preview_len):
    return (qs
        .exclude(classification='not_job_related')
        .select_related('draft', 'matched_job')
        .annotate(body_preview=Substr('body_text', 1, preview_len))
        .defer('body_text'))

class MailboxRunListSerializer(serializers.ListSerializer):
    """TASK-172: MailboxRunSerializer.get_digest_messages queries `obj.messages` once per run --
    calling that once per row in a many=True list is exactly the N+1 the owner measured (35,831ms /
    1,271,114 bytes for /api/mailbox-runs/, 13 runs over ~1,000 stored messages, each shipped with
    the FULL MailboxMessageSerializer -- up to 5,000 chars of body_text apiece). This class runs
    _digest_queryset ONCE, across every run in the list (a single `run_id__in=[...]` query, same
    shape as any other bulk-prefetch fix in this codebase), and groups the rows by run_id in Python
    -- `.order_by('run_id', '-uid')` guarantees each run's rows are contiguous AND already sorted
    -uid within that run, so grouping by first-seen-order reproduces exactly what
    `obj.messages.exclude(...).order_by('-uid')` gave per run before this task, never a second sort.
    Cached on `self` (the list serializer instance, bound as `self.child.parent` by DRF's own
    ListSerializer.__init__) so MailboxRunSerializer.get_digest_messages can read it back per row
    without a second query.
    """
    def to_representation(self, data):
        if hasattr(data, 'prefetch_related'):
            # MailboxRunViewSet.get_queryset() (views.py) still chains
            # .prefetch_related('messages__matched_job','messages__draft') -- built for the OLD,
            # per-run get_digest_messages below, which never actually consumed it: a FILTERED
            # `obj.messages.exclude(...).order_by(...)` call bypasses Django's prefetch cache
            # entirely (that cache only answers an unfiltered `.messages.all()`), so it was already
            # dead weight before this task. Left in place, evaluating `data` below would still run
            # it -- prefetch_related queries fire the moment the base queryset is fetched, whether or
            # not anything reads the attribute afterward -- and pull every stored message's FULL,
            # un-deferred body_text into the app server on every request, exactly the unbounded
            # column AC2 removes. `.prefetch_related(None)` is Django's own documented reset (not a
            # private API): it returns a new queryset with every chained prefetch lookup cleared, so
            # this stays a serializer-side fix rather than requiring a change to the view's queryset.
            data=data.prefetch_related(None)
        data=list(data)  # materialize once -- both the run_id collection below and the per-row
        # pass through the parent implementation need the same rows; a queryset iterated twice would
        # cost a second SELECT against mailboxrun for no reason.
        preview_len=MailboxMessageListSerializer.BODY_PREVIEW_CHARS + 1
        rows=_digest_queryset(MailboxMessage.objects.filter(run_id__in=[obj.id for obj in data]), preview_len).order_by('run_id', '-uid')
        by_run={}
        for row in rows:
            by_run.setdefault(row.run_id, []).append(row)
        self._digest_by_run=by_run
        return super().to_representation(data)

class MailboxRunSerializer(serializers.ModelSerializer):
    """TASK-109 AC4: the per-run digest. digest_messages is every message this run classified as
    job-related or uncertain -- exactly 'not_job_related' is left out, never dropped from the log
    itself (still visible via MailboxMessage, just not surfaced here as something to review).
    """
    digest_messages=serializers.SerializerMethodField()
    class Meta:
        model=MailboxRun
        list_serializer_class=MailboxRunListSerializer
        # drafting_skipped belongs here, not only in check_mailbox's stdout: an unattended Task
        # Scheduler run writes that stdout nowhere, so without this field a first run shows N
        # job-related messages and zero drafts in /mailbox with no explanation -- which reads as a
        # broken drafting path, the exact confusion the field was added to remove.
        fields=('id','started_at','finished_at','skipped','skip_reason','fetched_count','job_related_count','uncertain_count','suggestion_count','draft_written_count','draft_blocked_count','drafting_skipped','error','digest_messages')
    def get_digest_messages(self, obj):
        # TASK-172 AC3/AC6: still every message this run classified as job-related/uncertain, in the
        # same -uid order as before -- only the per-message shape changed, from the full
        # MailboxMessageSerializer (unbounded body_text) to MailboxMessageListSerializer's bounded
        # preview (the same one /api/mailbox-messages/unmatched/ already ships). AC6: a full body, if
        # ever genuinely needed here, is MailboxMessageViewSet.retrieve's job, not this list's --
        # nothing here calls it.
        by_run=getattr(self.parent, '_digest_by_run', None)
        if by_run is not None:
            # The list path: MailboxRunListSerializer.to_representation already ran ONE bulk query
            # for every run being serialized -- reuse it rather than re-querying obj.messages here,
            # which is exactly the per-run query this task exists to remove.
            rows=by_run.get(obj.id, [])
        else:
            # Single-object serialization (MailboxRunViewSet.retrieve, .status_view) -- no sibling
            # runs to batch with, so this queries just the one run's own messages, still through the
            # same bounded/deferred/joined shape as the list path above.
            preview_len=MailboxMessageListSerializer.BODY_PREVIEW_CHARS + 1
            rows=_digest_queryset(obj.messages, preview_len).order_by('-uid')
        return MailboxMessageListSerializer(rows, many=True, context=self.context).data

class InviteCodeSerializer(serializers.ModelSerializer):
    """Owner-facing view of an invite code. `code` is generated server-side, never posted."""
    class Meta:
        model=InviteCode
        fields=('id','code','label','active','expires_at','created_at')
        read_only_fields=('id','code','active','created_at')

class PublicSubmissionSerializer(serializers.Serializer):
    invite_code=serializers.CharField(max_length=80, required=False, allow_blank=True)
    company=serializers.CharField(max_length=200, required=False, allow_blank=True)
    title=serializers.CharField(max_length=250, required=False, allow_blank=True)
    location=serializers.CharField(max_length=200, required=False, allow_blank=True)
    url=serializers.CharField(max_length=1000, required=False, allow_blank=True)
    raw_description=serializers.CharField(required=False, allow_blank=True)
    submitted_by=serializers.CharField(max_length=120, required=False, allow_blank=True)
    submitter_reason=serializers.CharField(required=False, allow_blank=True)
    salary_info=serializers.CharField(max_length=250, required=False, allow_blank=True)
    language_requirements=serializers.CharField(max_length=250, required=False, allow_blank=True)
    work_mode=serializers.ChoiceField(choices=JobLead.WORK_MODES, required=False)
    website=serializers.CharField(required=False, allow_blank=True)  # honeypot
    def validate_url(self, value):
        value=normalize_job_url(value)
        if value:
            serializers.URLField(max_length=1000).run_validation(value)
        return value
    def validate(self, attrs):
        if attrs.get('website'): raise serializers.ValidationError('Spam rejected')
        embedded=extract_url_from_text(attrs.get('url')) or extract_url_from_text(attrs.get('company')) or extract_url_from_text(attrs.get('title'))
        if embedded and not attrs.get('url'):
            attrs['url']=embedded
        if attrs.get('url'):
            attrs['url']=normalize_job_url(extract_url_from_text(attrs.get('url')) or attrs.get('url'))
        if not attrs.get('url') and value_is_valid_url(attrs.get('company')):
            attrs['url']=normalize_job_url(attrs.get('company'))
            attrs['company']=''
        if 'company' in attrs: attrs['company']=clean_label_text(attrs.get('company'))
        if 'title' in attrs: attrs['title']=clean_job_title(attrs.get('title'))
        if 'location' in attrs: attrs['location']=clean_job_location(attrs.get('location'))
        if is_demo_job_payload(attrs.get('url')):
            raise serializers.ValidationError('Demo jobs are only available in the demo account.')
        if not (attrs.get('url') or attrs.get('raw_description') or attrs.get('company') or attrs.get('title')):
            raise serializers.ValidationError('Provide at least a job URL, description, company, or title')
        return attrs
    def create(self, data):
        # An anonymous submission belongs to whoever minted the code, otherwise the row is
        # ownerless and only staff can see it. public_submit overwrites submitted_for for
        # authenticated submitters, so this only takes effect on the anonymous path.
        recipient=InviteCode.recipient_for(data.pop('invite_code', None)); data.pop('website', None)
        data['company']=data.get('company') or 'Unknown company'
        data['title']=data.get('title') or 'Untitled role'
        return JobLead.objects.create(source='friend', submitted_for=recipient, **data)
