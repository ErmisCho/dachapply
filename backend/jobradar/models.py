from django.conf import settings
from django.db import models
from django.utils import timezone


class SiteVisitor(models.Model):
    visitor_id=models.CharField(max_length=64, unique=True, db_index=True)
    user=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='site_visitors', on_delete=models.SET_NULL)
    first_seen_at=models.DateTimeField(auto_now_add=True)
    last_seen_at=models.DateTimeField(null=True, blank=True)
    request_count=models.PositiveIntegerField(default=0)
    had_anonymous=models.BooleanField(default=False)
    had_authenticated=models.BooleanField(default=False)
    demo_click_count=models.PositiveIntegerField(default=0)
    demo_last_clicked_at=models.DateTimeField(null=True, blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['-last_seen_at','-created_at']
    def __str__(self): return self.user.get_username() if self.user_id else self.visitor_id

class UserProfile(models.Model):
    # candidate_profile and candidate_evidence default to '' on purpose. Until migration 0025 the
    # default was one specific person's real bio, so every account that skipped onboarding had its
    # jobs evaluated against that stranger's persona. An empty profile now refuses prompt generation
    # (services/prompt_builder.CandidateProfileRequired) instead of scoring the job against nobody.
    user=models.OneToOneField(settings.AUTH_USER_MODEL, related_name='jobradar_profile', on_delete=models.CASCADE)
    submit_for=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='friend_submitters', on_delete=models.SET_NULL)
    requested_submit_for=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='friend_submit_requests', on_delete=models.SET_NULL)
    # TASK-93. Default True, not False, and deliberately: migration 0028 adds the column to every
    # existing row as verified (AC3 grandfathering), and UserProfile rows are also get_or_create()d
    # for legacy and demo accounts by prompt_builder.user_profile_settings and services.demo_data --
    # defaulting to unverified would lock those accounts out of features they already had, the
    # owner's included. register_view is the only writer of False, because registration is the only
    # door an unproven address comes through.
    email_verified=models.BooleanField(default=True)
    # The friend named at registration, kept as raw text until the address is verified. Resolving it
    # during registration is what made that endpoint an enumeration oracle (TASK-93 AC2): any answer
    # that depends on whether the lookup hit -- a 400, or the friend's username echoed back -- tells
    # an anonymous caller whether an address has an account here. Nothing is looked up until
    # services.email_verification.mark_verified().
    pending_friend_lookup=models.CharField(max_length=254, blank=True, default='')
    candidate_profile=models.TextField(blank=True, default='')
    candidate_evidence=models.TextField(blank=True, default='')
    target_roles=models.TextField(blank=True, default='')
    preferred_locations=models.TextField(blank=True, default='')
    salary_expectations=models.TextField(blank=True, default='')
    language_levels=models.TextField(blank=True, default='')
    preferred_stack=models.TextField(blank=True, default='')
    red_flags=models.TextField(blank=True, default='')
    selling_points=models.TextField(blank=True, default='')
    learned_application_preferences=models.TextField(blank=True, default='')
    follow_up_digest_enabled=models.BooleanField(default=True)
    # TASK-109 AC8: check_mailbox reads these on every tick, so a change made here on the website
    # takes effect on the machine's next tick without touching its .env. Minimum 5 (see
    # serializers.CandidateProfileSerializer.validate_mailbox_check_cadence_minutes) because 0 would
    # collide with prompt_builder's generic profile codec, which treats a falsy value as "unset".
    mailbox_check_cadence_minutes=models.PositiveIntegerField(default=60)
    mailbox_check_calendar_aware=models.BooleanField(default=True)
    # TASK-110 AC2. Guardrails, not prompt text -- neither field is in prompt_builder.PROFILE_FIELDS,
    # so it never reaches an LLM prompt; services.mailbox.check_guardrails reads it only to check the
    # *generated* draft text in code. 0 / '' both mean "not configured" (no floor, no blocklist), same
    # falsy-is-unset idiom as mailbox_check_cadence_minutes. An env var (MAILBOX_SALARY_FLOOR_EUR /
    # MAILBOX_DO_NOT_DISCLOSE) on the machine running check_mailbox overrides this profile value, so a
    # web-only compromise can never raise the floor or shrink the blocklist below the machine's own.
    mailbox_salary_floor_eur=models.PositiveIntegerField(default=0)
    mailbox_do_not_disclose=models.TextField(blank=True, default='')
    # TASK-83: the capability that gates the nine CV endpoints. Off by default -- generation shells
    # out to a model CLI and LaTeX on the server, so it is granted per account in the admin, never
    # by signing up. services.cv_generator.is_cv_owner still honours CODEX_CV_OWNER_EMAIL as a
    # fallback so the owner's access cannot be lost by a flag that was never set.
    can_generate_cv=models.BooleanField(default=False)
    evaluation_prompt_template=models.TextField(blank=True, default='')
    combined_prompt_template=models.TextField(blank=True, default='')
    enrichment_prompt_template=models.TextField(blank=True, default='')
    bulk_links_prompt_template=models.TextField(blank=True, default='')
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.user} -> {self.submit_for or self.requested_submit_for or "self"}'

class JobLead(models.Model):
    WORK_MODES=[('onsite','Onsite'),('hybrid','Hybrid'),('remote','Remote'),('unknown','Unknown')]
    STATUSES=[('new','New'),('reviewed','Reviewed'),('to_apply','To apply'),('applied','Applied'),('interview','Interview'),('offer','Offer'),('accepted','Accepted'),('rejected','Rejected'),('withdrawn','Withdrawn'),('skipped','Skipped'),('archived','Archived')]
    DATED_STATUSES=['applied','interview','offer']  # active statuses that carry a status_date and can go stale
    UNAPPLIED_STATUSES=['new','reviewed','to_apply']  # lead is still ours to act on; ages out from created_at
    # The only home for the board's urgency thresholds. views.stale_rank orders by them and
    # /api/auth/me/ ships them to the frontend badge, so the numbers are never written twice.
    STALE_APPLIED_DAYS=21  # applied/interview/offer with no movement since status_date
    STALE_UNAPPLIED_DAYS=30  # new/reviewed/to_apply never acted on since created_at (postings expire in weeks)
    DEADLINE_SOON_DAYS=7  # apply_by this close (or past) counts as urgent
    FUNNEL_RECENT_DAYS=90  # the "recent window" the stats funnel reports alongside all-time
    company=models.CharField(max_length=200, blank=True, default='Unknown company')
    title=models.CharField(max_length=250, blank=True, default='Untitled role')
    location=models.CharField(max_length=200, blank=True)
    url=models.URLField(max_length=1000, blank=True)
    source=models.CharField(max_length=120, blank=True)
    raw_description=models.TextField(blank=True)
    original_source_text=models.TextField(blank=True)
    submitted_by=models.CharField(max_length=120, blank=True)
    submitter_reason=models.TextField(blank=True)
    salary_info=models.CharField(max_length=250, blank=True)
    language_requirements=models.CharField(max_length=250, blank=True)
    work_mode=models.CharField(max_length=20, choices=WORK_MODES, default='unknown')
    status=models.CharField(max_length=20, choices=STATUSES, default='new')
    status_date=models.DateField(null=True, blank=True)
    applied_at=models.DateField(null=True, blank=True)
    interview_stage=models.PositiveSmallIntegerField(null=True, blank=True)
    interview_total=models.PositiveSmallIntegerField(null=True, blank=True)
    interview_at=models.DateTimeField(null=True, blank=True)
    interview_note=models.CharField(max_length=250, blank=True)
    apply_by=models.DateField(null=True, blank=True)
    last_update_date=models.DateField(null=True, blank=True)
    feedback_due_date=models.DateField(null=True, blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    submitted_for=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='submitted_job_leads', on_delete=models.SET_NULL)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['-created_at']
    @staticmethod
    def is_meaningful_source(text):
        lines=[line.strip() for line in (text or '').splitlines() if line.strip()]
        return bool(lines) and any(not line.lower().startswith(('http://','https://','http-','https-')) for line in lines)
    def save(self, *args, **kwargs):
        existing=type(self).objects.filter(pk=self.pk).values_list('original_source_text', flat=True).first() if self.pk else ''
        if self.is_meaningful_source(existing):
            self.original_source_text=existing
        elif not self.is_meaningful_source(self.original_source_text) and self.is_meaningful_source(self.raw_description):
            self.original_source_text=self.raw_description
        if self.status=='applied' and not self.applied_at:
            self.applied_at=self.status_date or timezone.localdate()
        super().save(*args, **kwargs)
    @property
    def source_text(self): return self.original_source_text or self.raw_description
    def __str__(self): return f'{self.company} - {self.title}'

class JobEvaluation(models.Model):
    PRIORITIES=[('high','High'),('medium','Medium'),('low','Low')]
    RECOMMENDATIONS=[('apply','Apply'),('maybe','Maybe'),('skip','Skip')]
    job=models.ForeignKey(JobLead, related_name='evaluations', on_delete=models.CASCADE)
    fit_score=models.IntegerField()
    priority=models.CharField(max_length=10, choices=PRIORITIES)
    recommendation=models.CharField(max_length=10, choices=RECOMMENDATIONS)
    summary=models.TextField(blank=True)
    main_match_reasons=models.JSONField(default=list)
    main_gaps=models.JSONField(default=list)
    required_skills=models.JSONField(default=list)
    nice_to_have_skills=models.JSONField(default=list)
    matched_skills=models.JSONField(default=list)
    missing_skills=models.JSONField(default=list)
    cv_adjustment_notes=models.TextField(blank=True)
    interview_prep_notes=models.TextField(blank=True)
    risk_notes=models.TextField(blank=True)
    next_action=models.TextField(blank=True)
    structured_json_raw=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['-created_at']
    def __str__(self): return f'{self.job} ({self.fit_score})'

class ApplicationNote(models.Model):
    TYPES=[('general','General'),('cv_change','CV change'),('recruiter_message','Recruiter message'),('interview_prep','Interview prep'),('rejection_feedback','Rejection feedback'),('follow_up','Follow up')]
    job=models.ForeignKey(JobLead, related_name='notes', on_delete=models.CASCADE)
    note=models.TextField()
    note_type=models.CharField(max_length=30, choices=TYPES, default='general')
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']

class FollowUp(models.Model):
    job=models.ForeignKey(JobLead, related_name='followups', on_delete=models.CASCADE)
    follow_up_date=models.DateField()
    reason=models.CharField(max_length=250)
    completed=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['completed','follow_up_date']

class UserDailyUsage(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL, related_name='daily_usage', on_delete=models.CASCADE)
    date=models.DateField(db_index=True)
    request_count=models.PositiveIntegerField(default=0)
    last_seen_at=models.DateTimeField(null=True, blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        unique_together=(('user','date'),)
        ordering=['-date']
    def __str__(self): return f'{self.user} - {self.date}: {self.request_count}'

class SiteDailyUsage(models.Model):
    date=models.DateField(unique=True, db_index=True)
    request_count=models.PositiveIntegerField(default=0)
    authenticated_count=models.PositiveIntegerField(default=0)
    anonymous_count=models.PositiveIntegerField(default=0)
    unique_visitor_count=models.PositiveIntegerField(default=0)
    demo_click_count=models.PositiveIntegerField(default=0)
    demo_unique_visitor_count=models.PositiveIntegerField(default=0)
    last_seen_at=models.DateTimeField(null=True, blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['-date']
    def __str__(self): return f'{self.date}: {self.request_count} requests'

class VisitorDailyUsage(models.Model):
    visitor=models.ForeignKey(SiteVisitor, related_name='daily_usage', on_delete=models.CASCADE)
    date=models.DateField(db_index=True)
    request_count=models.PositiveIntegerField(default=0)
    had_anonymous=models.BooleanField(default=False)
    had_authenticated=models.BooleanField(default=False)
    demo_click_count=models.PositiveIntegerField(default=0)
    last_seen_at=models.DateTimeField(null=True, blank=True)
    demo_last_clicked_at=models.DateTimeField(null=True, blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        unique_together=(('visitor','date'),)
        ordering=['-date']
    def __str__(self): return f'{self.visitor} - {self.date}: {self.request_count}'

class InviteCode(models.Model):
    code=models.CharField(max_length=80, unique=True)
    # Nullable so the 0026 backfill cannot fail on a database with no users, and so legacy
    # ownerless codes keep working exactly as before (submission lands unowned, staff-only).
    owner=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='invite_codes', on_delete=models.CASCADE)
    label=models.CharField(max_length=120, blank=True)
    active=models.BooleanField(default=True)
    expires_at=models.DateTimeField(null=True, blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']
    def is_valid(self): return self.active and (self.expires_at is None or self.expires_at > timezone.now())
    def __str__(self): return self.label or self.code
    @classmethod
    def recipient_for(cls, code):
        """Owner an anonymous submission through `code` belongs to, or None.

        Revocation is a soft flip of `active`: is_valid() stops new submissions while the
        JobLeads already carrying submitted_for=owner keep their owner untouched.
        """
        code=(code or '').strip()
        invite=cls.objects.filter(code=code).first() if code else None
        return invite.owner if invite and invite.is_valid() else None

class PracticeSession(models.Model):
    # TASK-104: absorbed from the standalone interview-coach MVP. Belongs to its own user only --
    # deliberately not the created_by|submitted_for handoff pattern JobLead uses, per TASK-103's
    # ownership lesson. job is optional and SET_NULL on delete: losing the job link should never
    # delete the practice history that was scored against it.
    LANGUAGES=[('de','German'),('en','English')]
    user=models.ForeignKey(settings.AUTH_USER_MODEL, related_name='practice_sessions', on_delete=models.CASCADE)
    job=models.ForeignKey(JobLead, null=True, blank=True, related_name='practice_sessions', on_delete=models.SET_NULL)
    question=models.CharField(max_length=300, blank=True, default='')
    answer_text=models.TextField()
    language=models.CharField(max_length=2, choices=LANGUAGES, default='en')
    clarity_score=models.PositiveSmallIntegerField()
    structure_score=models.PositiveSmallIntegerField()
    confidence_score=models.PositiveSmallIntegerField()
    overall_score=models.PositiveSmallIntegerField()
    feedback=models.JSONField(default=list)
    stronger_answer=models.TextField(blank=True, default='')
    evaluator=models.CharField(max_length=30, default='heuristic')
    model=models.CharField(max_length=120, blank=True, default='')
    fallback_used=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']
    def __str__(self): return f'{self.user}: {self.question or "practice"} ({self.overall_score})'

class ScheduledTaskRun(models.Model):
    name=models.CharField(max_length=120, unique=True)
    last_run_at=models.DateTimeField(null=True, blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    def __str__(self): return f'{self.name}: {self.last_run_at or "never"}'

class MailboxRun(models.Model):
    """TASK-109 AC4: one row per check_mailbox tick that actually ran or was deliberately skipped.

    Never created at all when GMAIL_IMAP_USER/APP_PASSWORD are unset or the cadence isn't due yet --
    only a real attempt (whether it goes on to skip for calendar-quiet-hours or fetches mail) is
    worth a row, so this table doubles as the run digest AC4 asks for without extra bookkeeping.
    """
    SKIP_REASONS=[('', 'Not skipped'), ('quiet_hours', 'Calendar busy')]
    started_at=models.DateTimeField(auto_now_add=True)
    finished_at=models.DateTimeField(null=True, blank=True)
    skipped=models.BooleanField(default=False)
    skip_reason=models.CharField(max_length=20, choices=SKIP_REASONS, blank=True, default='')
    fetched_count=models.PositiveIntegerField(default=0)
    job_related_count=models.PositiveIntegerField(default=0)
    uncertain_count=models.PositiveIntegerField(default=0)
    suggestion_count=models.PositiveIntegerField(default=0)
    # TASK-110 AC1/AC5: how many reply drafts this run produced, split by guardrail outcome. Mirrors
    # suggestion_count's shape -- a cheap run-level summary on top of the per-message MailboxDraft log.
    draft_written_count=models.PositiveIntegerField(default=0)
    draft_blocked_count=models.PositiveIntegerField(default=0)
    # True when this run found no prior resume marker and therefore suppressed reply drafting. The
    # first run against an existing mailbox reads the whole history: on 2026-08-17 that meant 641
    # messages fetched and 112 drafts written into the owner's real Gmail Drafts folder, replies to
    # threads months dead. Classification and suggestions are in-app and harmless, but drafting is
    # the one step that writes outside the app, so a cold start now establishes a baseline instead
    # of acting on history. Recorded per-run rather than only logged: a run reporting job-related
    # mail and zero drafts must be able to say why, or it reads as a broken drafting path.
    drafting_skipped=models.BooleanField(default=False)
    error=models.TextField(blank=True, default='')
    class Meta: ordering=['-started_at']
    def __str__(self): return f'Run {self.started_at}: ' + (f'skipped ({self.skip_reason})' if self.skipped else f'{self.fetched_count} fetched')

class MailboxMessage(models.Model):
    """TASK-109 AC5: the append-only log of every message check_mailbox read.

    Rows are created once and never updated -- no view in this app exposes PATCH/DELETE for this
    model. Only sender/subject/date/classification are stored, never the body (task's minimal-
    metadata requirement); the body is read transiently off the wire to classify and then dropped.
    `uid` is the mailbox's own IMAP UID and doubles as the last-seen marker: check_mailbox resumes
    from MAX(uid) instead of keeping a separate state row. TASK-109 AC1's Gmail-API OAuth transport has
    no IMAP UID (its message ids are hex strings) -- for a Gmail-API-sourced row, `uid` is instead a
    locally-assigned sequence number (see services.mailbox.run_check) and `internal_date_ms` (Gmail's
    own ascending ms-epoch received time) is the real resume marker GmailApiTransport.fetch_new()
    consumes; `gmail_id` is Gmail's own opaque message id, kept as a dedup guard against the same
    message coming back on two consecutive runs. Both are blank/null for every IMAP-sourced row.
    """
    CLASSIFICATIONS=[('rejection','Rejection'),('interview_invitation','Interview invitation'),('offer','Offer'),('recruiter_reply','Recruiter reply'),('uncertain','Uncertain'),('not_job_related','Not job related')]
    run=models.ForeignKey(MailboxRun, related_name='messages', on_delete=models.CASCADE)
    uid=models.PositiveIntegerField(unique=True)
    gmail_id=models.CharField(max_length=32, blank=True, default='')
    internal_date_ms=models.PositiveBigIntegerField(null=True, blank=True)
    message_id=models.CharField(max_length=250, blank=True, default='')
    sender=models.CharField(max_length=254, blank=True, default='')
    subject=models.CharField(max_length=500, blank=True, default='')
    received_at=models.DateTimeField(null=True, blank=True)
    classification=models.CharField(max_length=30, choices=CLASSIFICATIONS, default='uncertain')
    evaluator=models.CharField(max_length=30, default='heuristic')
    matched_job=models.ForeignKey(JobLead, null=True, blank=True, related_name='mailbox_messages', on_delete=models.SET_NULL)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-uid']
    def __str__(self): return f'{self.sender}: {self.subject[:60]} ({self.classification})'

class MailboxSuggestion(models.Model):
    """TASK-109 AC3: a reviewable, owner-confirmed change derived from one MailboxMessage.

    `payload` carries what confirming will apply (e.g. {'status':'rejected'} or
    {'interview_at': iso}) via JobLeadSerializer.update(), so confirm() never has to re-derive it
    from the message. Created once; only `status`/`decided_at` change afterward, and only through
    the confirm/dismiss actions below -- never a generic field edit, and never automatically.
    """
    TYPES=[('status_change','Status change'),('interview_date','Interview date'),('feedback_clear','Feedback clock clear')]
    STATUSES=[('pending','Pending'),('confirmed','Confirmed'),('dismissed','Dismissed')]
    message=models.ForeignKey(MailboxMessage, related_name='suggestions', on_delete=models.CASCADE)
    job=models.ForeignKey(JobLead, related_name='mailbox_suggestions', on_delete=models.CASCADE)
    suggestion_type=models.CharField(max_length=20, choices=TYPES)
    payload=models.JSONField(default=dict)
    status=models.CharField(max_length=10, choices=STATUSES, default='pending')
    created_at=models.DateTimeField(auto_now_add=True)
    decided_at=models.DateTimeField(null=True, blank=True)
    class Meta: ordering=['-created_at']
    def __str__(self): return f'{self.get_suggestion_type_display()} for {self.job} ({self.status})'

class MailboxDraft(models.Model):
    """TASK-110 AC5: append-only decision log for every reply draft check_mailbox generates --
    whether it was written to Gmail's Drafts folder or blocked by a guardrail. Same shape as
    MailboxMessage: created once, no PATCH/DELETE view ever touches it. One row per MailboxMessage
    that classify_email flagged as reply-wanting (see services.mailbox._DRAFT_WORTHY_CLASSIFICATIONS)
    and that matched a tracked job -- rejection/not_job_related/uncertain, and any message with no
    matched job, never get a row here at all.
    """
    STATUSES=[('written','Written to Gmail Drafts'),('blocked','Blocked')]
    message=models.OneToOneField(MailboxMessage, related_name='draft', on_delete=models.CASCADE)
    job=models.ForeignKey(JobLead, null=True, blank=True, related_name='mailbox_drafts', on_delete=models.SET_NULL)
    status=models.CharField(max_length=10, choices=STATUSES)
    # Empty for a written draft; the guardrail's short human-readable reason for a blocked one (AC2).
    block_reason=models.CharField(max_length=250, blank=True, default='')
    subject=models.CharField(max_length=500, blank=True, default='')
    body_text=models.TextField(blank=True, default='')
    # 'template' for the no-LLM floor (AC4), or the LLM_PROVIDER value when the local-LLM upgrade
    # produced the text -- same vocabulary as MailboxMessage.evaluator/PracticeSession.evaluator.
    evaluator=models.CharField(max_length=30, default='template')
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']
    def __str__(self): return f'Draft for {self.message}: {self.get_status_display()}'
