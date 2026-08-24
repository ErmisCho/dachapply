from datetime import time

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
    # TASK-141 AC1/AC3/AC7: how far back check_mailbox looks for NEW mail -- read by
    # GmailApiTransport.fetch_new() to build the query's `after:` floor (services/mailbox.py, out of
    # this file's territory) so a cold start (or a raised window) stays bounded instead of reading the
    # account's entire history the way TASK-136 left it. Bounding what is fetched only; mail already
    # stored outside the window is never deleted by this setting (AC7 -- that is a different decision
    # with its own task if it is ever wanted).
    # Range is 1-60 months (five years): a floor of 1 keeps the window meaningful, a ceiling of 60
    # keeps it a window rather than "no limit" spelled as a very large number. Deliberately NOT the
    # same "0/falsy means unset" idiom mailbox_check_cadence_minutes documents above -- that idiom
    # would make 0 read back as unset and silently fall back to unlimited lookback, which is the one
    # meaning the owner explicitly ruled out ("that should also be configurable" -- 6 months, not
    # "off"). See CandidateProfileSerializer.validate_mailbox_lookback_months for the rejection.
    mailbox_lookback_months=models.PositiveIntegerField(default=6)
    # TASK-169: a THIRD window, distinct from mailbox_lookback_months (FETCH, above) and from views.
    # UNMATCHED_RECENCY_WINDOW_DAYS (DISPLAY, views.py -- now only the default's own source of truth,
    # see that constant's comment) -- how far back the unmatched-mail panel ATTEMPTS to identify a
    # job for a message at all. Measured against production 2026-08-21: the owner set
    # mailbox_lookback_months to 3 and the panel barely changed, because that field bounds FETCHING
    # only -- 247 of 309 panel rows were already stored from before the narrower fetch, so nothing
    # about them could be affected by it. This field is what actually bounds the identification
    # attempt itself, not just what gets fetched.
    # Nullable, and null is deliberately NOT this field's "unlimited" (the one meaning AC3/AC4 forbid,
    # same reasoning as mailbox_lookback_months's own comment below) -- null means "nobody has
    # explicitly chosen a value", read as the 3-month default everywhere this is consumed (views.py's
    # `unmatched` action). A non-null value means the OWNER explicitly chose it, which matters for
    # AC7: TASK-161 measured that 15 of 41 currently-unattached high-consequence rows (rejection/
    # interview_invitation) are themselves over a year old, so a DEFAULT the owner never touched must
    # never bury them -- but a window they DID set is honoured even there, with its own separately-
    # reported, revealable count (views.py). See CandidateProfileSerializer.
    # validate_mailbox_identify_window_months for the accepted range once a value is given.
    mailbox_identify_window_months=models.PositiveIntegerField(null=True, blank=True, default=None)
    mailbox_check_calendar_aware=models.BooleanField(default=True)
    # TASK-125 AC1/AC2: the explicit off switch. Deliberately not cadence=0 -- the validator above
    # rejects 0 for a documented reason (it would read back as "unset" through the profile codec and
    # fall back to the default, silently meaning "every hour" rather than "never"). Default True so
    # every existing account keeps checking exactly as it did before this field existed.
    mailbox_check_enabled=models.BooleanField(default=True)
    # TASK-125 AC3/AC4/AC5: the check only runs inside this window, interpreted in settings.TIME_ZONE
    # (Europe/Vienna) via timezone.localtime() -- see services.mailbox.is_within_check_window and
    # run_check, the one place both fields are read. Two times rather than a string, so the
    # midnight-wrap case (e.g. 22:00-06:00) is a comparison, not a parse. Equal start/end (the
    # default for both) means "no restriction" -- every existing account keeps checking around the
    # clock exactly as before until it explicitly sets a window.
    mailbox_check_window_start=models.TimeField(default=time(0, 0))
    mailbox_check_window_end=models.TimeField(default=time(0, 0))
    # TASK-110 AC2. Guardrails, not prompt text -- neither field is in prompt_builder.PROFILE_FIELDS,
    # so it never reaches an LLM prompt; services.mailbox.check_guardrails reads it only to check the
    # *generated* draft text in code. 0 / '' both mean "not configured" (no floor, no blocklist), same
    # falsy-is-unset idiom as mailbox_check_cadence_minutes. An env var (MAILBOX_SALARY_FLOOR_EUR /
    # MAILBOX_DO_NOT_DISCLOSE) on the machine running check_mailbox overrides this profile value, so a
    # web-only compromise can never raise the floor or shrink the blocklist below the machine's own.
    mailbox_salary_floor_eur=models.PositiveIntegerField(default=0)
    mailbox_do_not_disclose=models.TextField(blank=True, default='')
    # TASK-122 AC4: the owner's last-chosen (provider, model) for the mailbox draft-chat
    # conversation, so it survives a page reload instead of resetting like CV generation's
    # React-state-only picker does. '' means "nothing chosen yet" -- services.draft_chat.
    # available_model_options() is what the picker offers; these two fields only ever mirror one
    # of those options back, never a second source of truth for what the machine can run.
    mailbox_chat_provider=models.CharField(max_length=30, blank=True, default='')
    mailbox_chat_model=models.CharField(max_length=120, blank=True, default='')
    # TASK-116: one or more Google Calendar ids the owner has selected for quiet hours, one per line
    # (same one-per-line idiom as mailbox_do_not_disclose above -- see
    # services.mailbox._effective_calendar_ids). Replaces TASK-115's mailbox_calendar_ics_urls: the
    # picker (services.mailbox.list_calendars, via calendarList.list on the same Gmail OAuth client)
    # lets the owner select calendars BY NAME, so a calendar id ('primary',
    # 'xxx@group.calendar.google.com') is what gets stored here, never a URL. This profile value is
    # the only place these are configured (AC7, carried over from TASK-115): no environment-variable
    # fallback and nothing in the UI or docs points anywhere else.
    # Unlike TASK-115's field, a calendar id is NOT a secret -- it grants no access on its own (the
    # OAuth refresh token is what does that, and it lives only in the local, gitignored token file --
    # see GMAIL_OAUTH_TOKEN_PATH). So, unlike that field, this one is never masked on read and needs
    # no masked-round-trip merge on write.
    mailbox_calendar_ids=models.TextField(blank=True, default='')
    # TASK-145 AC4/AC8: the board's saved multi-sort, per account and synced (the owner's explicit
    # choice over localStorage) -- same wire format `?ordering=` already accepts and
    # views.parse_board_ordering already parses (e.g. 'status,-fit_score'), so no second parser or
    # allowlist exists for this value. Blank is "no saved sort" and is how a user clears it back to
    # views.DEFAULT_BOARD_ORDERING (AC8) -- parse_board_ordering already falls back to that default
    # on blank/absent input, and already caps at 3 keys and drops anything outside BOARD_ORDERINGS
    # (AC7/AC9), so a hostile or stale saved value degrades the same way a hostile query param does
    # rather than erroring. Deliberately unvalidated here for that same reason: rejecting an invalid
    # value at save time would be a second enforcement point to keep in sync with the one that
    # already exists.
    board_sort_keys=models.CharField(max_length=120, blank=True, default='')
    # TASK-83: the capability that gates the nine CV endpoints. Off by default -- generation shells
    # out to a model CLI and LaTeX on the server, so it is granted per account in the admin, never
    # by signing up. services.cv_generator.is_cv_owner still honours CODEX_CV_OWNER_EMAIL as a
    # fallback so the owner's access cannot be lost by a flag that was never set.
    # The help text changed with TASK-99a and the change is the point: templates and the photo are
    # now this account's own CvAsset rows, so the flag no longer hands anyone the owner's files. The
    # shared output directory is still shared -- that half is TASK-99b and is not fixed here.
    can_generate_cv=models.BooleanField(default=False, help_text="Generates CVs and cover letters from this account's own LaTeX templates and photograph, and writes them into a shared output directory on the server. An account with no templates of its own cannot generate anything.")
    evaluation_prompt_template=models.TextField(blank=True, default='')
    combined_prompt_template=models.TextField(blank=True, default='')
    enrichment_prompt_template=models.TextField(blank=True, default='')
    bulk_links_prompt_template=models.TextField(blank=True, default='')
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.user} -> {self.submit_for or self.requested_submit_for or "self"}'

class CvAsset(models.Model):
    """One LaTeX template, or the photograph, belonging to exactly one account.

    TASK-99a. Until this existed, "which template" and "whose photo" were answered by
    settings.CODEX_CV_WORKSPACE -- a directory that exists on one laptop -- so every account with
    can_generate_cv shipped applications built from the owner's templates and wearing the owner's
    face. services.cv_generator resolves both from these rows now, filtered on the owning user with
    no fallback: no env-owner default, no "the only template anyone has", no workspace glob.

    In the database rather than on disk on purpose. There is no MEDIA_ROOT in this project and the
    deployed container's filesystem is ephemeral, so a FileField would mean "a file that survives
    until the next restart". Templates are ~12 KB of text and a photograph is ~1 MB; both fit a row.

    Deliberately NOT columns on UserProfile: that row is loaded on nearly every authenticated
    request, and a megabyte of JPEG would ride along with each one.
    """
    KIND_CV='cv'
    KIND_LETTER='letter'
    KIND_PHOTO='photo'
    KINDS=[(KIND_CV,'CV template'),(KIND_LETTER,'Letter template'),(KIND_PHOTO,'Photograph')]
    user=models.ForeignKey(settings.AUTH_USER_MODEL, related_name='cv_assets', on_delete=models.CASCADE)
    kind=models.CharField(max_length=10, choices=KINDS)
    # 'en'/'de' for a CV, the letter's own key ('anschreiben', 'motivation_letter', ...) for a
    # letter, '' for the photograph -- one photo per account, which is what unique_together below
    # enforces by giving every photo row the same empty key.
    key=models.CharField(max_length=40, blank=True, default='')
    # Which language's option list this appears under. Letters are chosen inside the CV's language
    # (see cv_generator.user_templates), so a letter's language is what binds it to a CV.
    language=models.CharField(max_length=5, blank=True, default='')
    label=models.CharField(max_length=120, blank=True, default='')
    # The name this gets in the compile directory. For the photograph it defaults to Picture.jpg
    # because that is the name the CV templates' own \includegraphics line already uses; changing
    # it means changing that line too.
    filename=models.CharField(max_length=200, blank=True, default='')
    source=models.TextField(blank=True, default='')
    # Empty for a template. editable=False keeps a megabyte of JPEG out of admin forms; the photo
    # is written by the import_cv_assets management command, not typed into a textarea.
    image=models.BinaryField(blank=True, default=b'', editable=False)
    # Where the import came from, for display only -- the preview endpoint shows it so the owner can
    # still open the file they edit in C:\latex. Never read to resolve anything: this row is the
    # source of truth, and a path here that no longer exists changes nothing about generation.
    source_path=models.CharField(max_length=400, blank=True, default='')
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        unique_together=[('user','kind','key')]
        ordering=['user','kind','key']
    def __str__(self): return f'{self.user}: {self.get_kind_display()} {self.key or self.filename}'.strip()

class JobLead(models.Model):
    WORK_MODES=[('onsite','Onsite'),('hybrid','Hybrid'),('remote','Remote'),('unknown','Unknown')]
    STATUSES=[('new','New'),('reviewed','Reviewed'),('to_apply','To apply'),('applied','Applied'),('interview','Interview'),('offer','Offer'),('accepted','Accepted'),('rejected','Rejected'),('withdrawn','Withdrawn'),('skipped','Skipped'),('archived','Archived')]
    DATED_STATUSES=['applied','interview','offer']  # active statuses that carry a status_date and can go stale
    UNAPPLIED_STATUSES=['new','reviewed','to_apply']  # lead is still ours to act on; ages out from created_at
    # TASK-143 AC1: the owner's "when I can still do something about it" split of STATUSES, defined
    # ONCE here so it cannot drift between the mailbox review panel's queryset (views.
    # MailboxSuggestionViewSet.list) and suggestion/draft generation (services.mailbox, gated there
    # separately -- out of this task's file territory). Not yet exposed on /api/auth/me/'s
    # BOARD_THRESHOLDS -- a frontend component that needs this list should read it from there rather
    # than re-typing it (same pattern as unapplied_statuses/dated_statuses above), but wiring that up
    # is a one-line addition plus a one-line fix to test_api.py's exact-dict assertion, both outside
    # this task's file territory this wave. 'accepted' is deliberately included: an accepted offer
    # still produces mail worth reading (start date, paperwork onboarding) -- the owner's question is
    # "can I still act on this", not "is the application still open". The complement (rejected, withdrawn,
    # skipped, archived) is never spelled out as its own list; it is just "not in this one".
    ACTIONABLE_STATUSES=['new','reviewed','to_apply','applied','interview','offer','accepted']
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
    # TASK-124 AC4: set only by services.mailbox._claim_run while a run for this task is actually in
    # flight, and cleared by _release_run() the instant it finishes (success, error, or any skip) --
    # a dedicated marker rather than reading MailboxRun.finished_at IS NULL, because plenty of test
    # fixtures (and seed_fake_run's historical-baseline rows) create a MailboxRun directly without
    # ever setting finished_at, which would misread as "still running" if this reused that column.
    running_since=models.DateTimeField(null=True, blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    def __str__(self): return f'{self.name}: {self.last_run_at or "never"}'

class MailboxRun(models.Model):
    """TASK-109 AC4: one row per check_mailbox tick that actually ran or was deliberately skipped.

    Never created at all when GMAIL_IMAP_USER/APP_PASSWORD are unset or the cadence isn't due yet --
    only a real attempt (whether it goes on to skip for calendar-quiet-hours or fetches mail) is
    worth a row, so this table doubles as the run digest AC4 asks for without extra bookkeeping.
    """
    # TASK-125 AC6: every reason a run does nothing is a value here, never a second mechanism --
    # this column is the one place a skip is recorded, and the gate order in services.mailbox.run_check
    # decides which one wins when more than one would apply (disabled, then outside_window, then
    # quiet_hours -- cheapest and most specific first).
    SKIP_REASONS=[
        ('', 'Not skipped'),
        ('quiet_hours', 'Calendar busy'),
        ('disabled', 'Checking turned off'),
        ('outside_window', 'Outside the allowed time window'),
    ]
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
    # TASK-154 AC2: the suggestion side of draft_blocked_count above. Drafting refusals have been
    # counted on the run since TASK-114, and surfaced by check_mailbox and the run-status panel, so an
    # owner asking "why did nothing turn up for this mail" can answer it without server logs. A
    # suggestion refused as bulk mail needs the same answer available in the same place -- a log line
    # in a container is not something the owner can reach.
    suggestion_blocked_count=models.PositiveIntegerField(default=0)
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

class MailboxCheckRequest(models.Model):
    """TASK-124 AC2/AC3: a manual "run now" request recorded on a backend with no mail credentials
    (the deployed site), for the owner's own machine to pick up on its next check_mailbox tick.

    Deliberately its own model rather than overloading ScheduledTaskRun, which tracks a recurring
    SCHEDULE's last-run-at, not a one-off ask -- see the task notes. `handled_at` is the once-only
    marker (AC3: picked up and run on the next tick, then never acted on again, whatever the
    outcome); `result_run` links to the MailboxRun the request actually produced -- including a
    skipped one (disabled/outside_window/quiet_hours all still count as "this was handled") -- so the
    app can show the outcome of the specific thing that was asked for.
    """
    requested_at=models.DateTimeField(auto_now_add=True)
    requested_by=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    handled_at=models.DateTimeField(null=True, blank=True)
    result_run=models.ForeignKey(MailboxRun, null=True, blank=True, related_name='fulfilled_requests', on_delete=models.SET_NULL)
    class Meta: ordering=['-requested_at']
    def __str__(self): return f'Request at {self.requested_at}: ' + (f'handled -> run {self.result_run_id}' if self.handled_at else 'pending')

class MailboxMessage(models.Model):
    """TASK-109 AC5: the append-only log of every message check_mailbox read.

    Rows are created once and never updated by check_mailbox itself -- no view in this app exposes a
    generic PATCH/DELETE for this model. There are now TWO deliberate exceptions. The first is
    `matched_job`: TASK-117 AC6 lets the owner attach a message that matched no job to one by hand
    (services.mailbox.attach_message_to_job), which mutates a row after creation, and (before TASK-171)
    was the only thing anywhere that did. The second is `dismissed_at` -- see its own field comment
    below (TASK-171 AC3/AC5/AC6). Both are owner-initiated, single-field mutations; neither is
    something check_mailbox/ingest_threads/backfill_historical_mail ever touch, so re-ingestion can
    never undo either one (those functions' own gmail_id-existence dedup guards mean a message already
    in this table is never recreated at all, whatever its matched_job/dismissed_at say).

    TASK-117 AC1 (2026-08-18): the owner reversed this model's earlier minimal-metadata default.
    `body_text` now stores the received body, capped at the 5000 chars the wire read already applies
    (both transports truncate before this model ever sees the text -- see RawMessage.body_text -- and
    the write below re-applies the same cap so the column cannot exceed it even if a transport
    changes). Recorded here, not just in the commit, because the previous version of this docstring
    said "never the body (task's minimal-metadata requirement)" and a test enforced it
    (test_run_check_never_stores_the_message_body, now replaced by a test asserting the body IS
    stored and IS capped) -- neither was ever an acceptance criterion of TASK-109; it was an
    implementation default, not a spec requirement, and it did real harm: a classification the owner
    cannot check is one they cannot trust, and TASK-114 shipped two reply drafts aimed at newsletters
    that a visible body would have made obvious immediately instead of after the fact. What changes:
    recruiter email bodies now live in the same database the deployed Azure app reads -- a real
    widening of what that database holds, taken knowingly (see the task file for the full record). Do
    not "fix" this back to dropping the body; that reopens the exact gap TASK-117 closed.

    `uid` is the mailbox's own IMAP UID and doubles as the last-seen marker: check_mailbox resumes
    from MAX(uid) instead of keeping a separate state row. TASK-109 AC1's Gmail-API OAuth transport has
    no IMAP UID (its message ids are hex strings) -- for a Gmail-API-sourced row, `uid` is instead a
    locally-assigned sequence number (see services.mailbox.run_check) and `internal_date_ms` (Gmail's
    own ascending ms-epoch received time) is the real resume marker GmailApiTransport.fetch_new()
    consumes; `gmail_id` is Gmail's own opaque message id, kept as a dedup guard against the same
    message coming back on two consecutive runs. Both are blank/null for every IMAP-sourced row.

    TASK-121 AC2: `thread_id` is Gmail's own thread id for this INBOUND message (RawMessage.thread_id,
    previously documented as "transient, never persisted") -- a different id from anything on
    MailboxDraft (that one threads the REPLY), and it is what a per-message "open this conversation in
    Gmail" link needs. Blank for every IMAP-sourced row, same as gmail_id.

    TASK-132 (2026-08-19, the owner's decision, recorded here not just in the commit): this table now
    also stores the owner's OWN sent mail, not just what they received -- services.mailbox.
    ingest_threads() ingests a matched thread's whole `users.threads.get` result, including the
    owner's replies, so a "conversation" reads as an exchange instead of one side of it. That is a
    second widening of what this database holds beyond TASK-117's body_text (see above); do not
    revert it back to inbound-only. `sent_by_owner` is what makes the widening honest instead of
    silent: a message this app stored because it wrote it (a reply drafted here) is indistinguishable
    at this field from one the owner sent from Gmail directly -- both are simply "the owner spoke".

    TASK-136 (2026-08-19): `GmailApiTransport.fetch_new` no longer restricts itself to `labelIds=
    INBOX` -- an application confirmation is routinely archived (moved out of the inbox) the moment
    it is read, and thread ingestion above only ever expands a thread this app already knows about, so
    an archived FIRST message of a thread was invisible and stayed that way forever. This table can
    therefore now contain anything the owner's Gmail account holds except Spam/Trash (the Gmail API's
    own default `messages.list` scope with no `labelIds` given), not just what was still sitting in
    the inbox at fetch time -- a further, deliberate widening in the same spirit as the two above; see
    services.mailbox.GmailApiTransport.fetch_new for the date-floor bound that keeps a cold start
    finite. `classification` gained `application_confirmed` in the same change: an "application
    received"/"thank you for applying" acknowledgment previously had no category of its own and
    landed as `not_job_related` or `recruiter_reply`, neither of which proposes anything -- see
    services.mailbox.build_suggestions, which now proposes moving the job to `applied` (with
    `applied_at` taken from the message's own received date, not "today") when it sees one.

    TASK-135 (2026-08-19): `calendar_summary`/`calendar_location`/`calendar_organizer`/
    `calendar_start`/`calendar_end` are the what/when/with-whom of the FIRST iCalendar VEVENT found in
    a `text/calendar` MIME part (services.mailbox.parse_calendar_invitation) -- blank/null when the
    message carries no invitation. `attachments` is a JSON list of `{filename, mime_type, size}` for
    every OTHER MIME part carrying a filename -- METADATA ONLY, a deliberate decision (this repo has a
    filed history of pulling personal-data files into this same database and reversing it: TASK-69,
    TASK-90, TASK-117's own body_text reversal-of-a-reversal above). The Gmail API's `format=raw` read
    this module already used hands the full attachment bytes over as an unavoidable side effect of
    decoding the whole RFC822 message; `size` is measured from those bytes and the bytes themselves
    are discarded immediately after, never assigned to this model or any other. "Reply in Gmail"
    remains the only route to the actual file, same as before this task.
    """
    CLASSIFICATIONS=[('rejection','Rejection'),('interview_invitation','Interview invitation'),('offer','Offer'),('recruiter_reply','Recruiter reply'),('application_confirmed','Application confirmed'),('uncertain','Uncertain'),('not_job_related','Not job related')]
    run=models.ForeignKey(MailboxRun, related_name='messages', on_delete=models.CASCADE)
    uid=models.PositiveIntegerField(unique=True)
    gmail_id=models.CharField(max_length=32, blank=True, default='')
    internal_date_ms=models.PositiveBigIntegerField(null=True, blank=True)
    message_id=models.CharField(max_length=250, blank=True, default='')
    thread_id=models.CharField(max_length=32, blank=True, default='')
    sender=models.CharField(max_length=254, blank=True, default='')
    subject=models.CharField(max_length=500, blank=True, default='')
    # TASK-132 AC1/AC2/TASK-133 AC2/AC7: the raw To/Cc/Reply-To header values (TextField, not capped
    # to CharField's 254 like `sender`, because a header can list several addresses with display
    # names) -- TASK-114 stopped short of these, adding only the bulk-marker headers. Read by
    # services.mailbox.derive_reply_recipients() to build reply-all without a second Gmail fetch.
    # `sent_by_owner` is a STORED flag (never a From-address comparison at render time -- the owner
    # has several addresses; see services.mailbox._is_owner_address), set once at ingest time by
    # run_check()/ingest_threads(), so "who spoke" in a conversation never depends on a guess made
    # fresh on every page load.
    reply_to=models.TextField(blank=True, default='')
    to_addrs=models.TextField(blank=True, default='')
    cc_addrs=models.TextField(blank=True, default='')
    sent_by_owner=models.BooleanField(default=False)
    # TASK-117 AC1: capped to 5000 chars, the same cap RawMessage.body_text already applies off the wire.
    body_text=models.TextField(blank=True, default='')
    # TASK-135 AC1/AC2/AC3/AC4: see the class docstring. Blank/null/empty-list on every message with
    # no calendar invitation and no attachment -- the overwhelming majority of rows.
    calendar_summary=models.CharField(max_length=500, blank=True, default='')
    calendar_location=models.CharField(max_length=500, blank=True, default='')
    calendar_organizer=models.CharField(max_length=500, blank=True, default='')
    calendar_start=models.DateTimeField(null=True, blank=True)
    calendar_end=models.DateTimeField(null=True, blank=True)
    attachments=models.JSONField(default=list, blank=True)
    # TASK-150: set ONLY by services.mailbox.backfill_message_bodies(calendar_missing=True) the moment
    # it definitively resolves a body-bearing row's calendar status (found real calendar data OR
    # confirmed the refetch carries none) -- never touched by any other path. This is the discriminator
    # that lets a genuinely calendar-less row leave that mode's candidate set: calendar_summary=='' AND
    # calendar_checked_at IS NULL is "never checked"; calendar_summary=='' AND calendar_checked_at IS
    # NOT NULL is "checked, confirmed none" -- distinguishable from "never checked" without writing a
    # lying sentinel into calendar_summary or attachments (both of which are legitimately empty on the
    # overwhelming majority of real rows, checked or not). Left null/blank on every row this app is not
    # deliberately auditing for missing calendar data.
    calendar_checked_at=models.DateTimeField(null=True, blank=True)
    received_at=models.DateTimeField(null=True, blank=True)
    classification=models.CharField(max_length=30, choices=CLASSIFICATIONS, default='uncertain')
    evaluator=models.CharField(max_length=30, default='heuristic')
    matched_job=models.ForeignKey(JobLead, null=True, blank=True, related_name='mailbox_messages', on_delete=models.SET_NULL)
    # TASK-171 AC3/AC5/AC6: the panel's "not attachable to any job" decision. A nullable timestamp,
    # not a boolean, for the same reason decided_at/calendar_checked_at above are timestamps rather
    # than booleans -- "when" is free once the column exists. Set only by views.
    # MailboxMessageViewSet.dismiss, cleared only by its undismiss counterpart -- the second
    # deliberate exception to this model's append-only guarantee (see the class docstring). Writes NO
    # matched_job and generates NO suggestion; attach_message_to_job remains the only path that does
    # either, so dismissing can never be mistaken for (or implemented as) attaching to a placeholder.
    dismissed_at=models.DateTimeField(null=True, blank=True)
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

    TASK-121 AC1: `gmail_draft_id`/`gmail_message_id`/`gmail_thread_id` are the Gmail API's own
    `users.drafts.create` response ids (services.mailbox.GmailApiTransport.append_draft used to POST
    and discard them) -- `gmail_draft_id` is what a later `users.drafts.update`/`.delete` call is keyed
    on (see services.mailbox.update_draft_text/purge_app_drafts), `gmail_message_id` is the draft's own
    message id (distinct from MailboxMessage.message_id, the RFC 822 header of the INBOUND mail this is
    a reply to), and `gmail_thread_id` is the thread the draft was placed in. All three are blank for
    an IMAP-written draft (ImapTransport.append_draft returns no ids -- Gmail assigns them itself on
    APPEND, unreachable from an IMAP response) and for every row written before this task.
    """
    STATUSES=[('written','Written to Gmail Drafts'),('blocked','Blocked')]
    message=models.OneToOneField(MailboxMessage, related_name='draft', on_delete=models.CASCADE)
    job=models.ForeignKey(JobLead, null=True, blank=True, related_name='mailbox_drafts', on_delete=models.SET_NULL)
    status=models.CharField(max_length=10, choices=STATUSES)
    # Empty for a written draft; the guardrail's short human-readable reason for a blocked one (AC2).
    block_reason=models.CharField(max_length=250, blank=True, default='')
    subject=models.CharField(max_length=500, blank=True, default='')
    body_text=models.TextField(blank=True, default='')
    # 'template' for the no-LLM floor (AC4), the LLM_PROVIDER value when the local-LLM upgrade produced
    # the text, or 'human' once update_draft_text() records an owner hand-edit (TASK-122 AC1) -- same
    # vocabulary as MailboxMessage.evaluator/PracticeSession.evaluator.
    evaluator=models.CharField(max_length=30, default='template')
    gmail_draft_id=models.CharField(max_length=32, blank=True, default='')
    gmail_message_id=models.CharField(max_length=32, blank=True, default='')
    gmail_thread_id=models.CharField(max_length=32, blank=True, default='')
    # TASK-122 AC4/AC5: the multi-turn draft-chat transcript, as a JSON list of
    # {"user_message": ..., "revised_text": ...} -- one dict per services.draft_chat.ChatTurn,
    # in order, so `[ChatTurn(**item) for item in chat_history]` reconstructs it exactly. Only a
    # turn the model actually produced (ChatTurnResult.reason == '') is ever appended here -- a
    # provider failure or a guardrail block never becomes part of the conversation a later turn
    # re-feeds. Reset to [] whenever body_text changes through the `edit` action (see
    # MailboxDraftViewSet.edit): once accepted, that text is the new baseline, not one more turn.
    chat_history=models.JSONField(default=list, blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']
    def __str__(self): return f'Draft for {self.message}: {self.get_status_display()}'
