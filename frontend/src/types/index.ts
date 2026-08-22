export type Evaluation={id:number;job:number;fit_score:number;priority:'high'|'medium'|'low';recommendation:'apply'|'maybe'|'skip';summary:string;main_match_reasons:string[];main_gaps:string[];required_skills:string[];nice_to_have_skills:string[];matched_skills:string[];missing_skills:string[];cv_adjustment_notes:string;interview_prep_notes:string;risk_notes:string;next_action:string;skill_statuses?:Record<string,string>;created_at:string}
// TASK-126 AC4: has_mailbox_history is list-only (JobLeadListSerializer's Exists() annotation) --
// undefined on a job fetched from /api/jobs/<id>/ (JobLeadSerializer, no such field on the wire).
export type Job={id:number;company:string;title:string;location:string;url:string;source:string;raw_description:string;original_source_text?:string;submitted_by:string;submitter_reason:string;salary_info:string;language_requirements:string;work_mode:string;status:string;status_date?:string|null;interview_stage?:number|null;interview_total?:number|null;interview_at?:string|null;interview_note?:string;apply_by?:string|null;last_update_date?:string|null;feedback_due_date?:string|null;created_by_username?:string;created_by_email?:string;submitted_for_username?:string;submitted_for_email?:string;created_at:string;updated_at?:string;latest_evaluation?:Evaluation|null;has_mailbox_history?:boolean}
export type FollowUp={id:number;job:number;company:string;title:string;follow_up_date:string;reason:string;completed:boolean}
// TASK-146. GET /api/jobs/feedback-due/'s row shape - already sorted overdue-group-first then
// soonest-first by the server. The exact key the backend uses to mark a row overdue-vs-upcoming is
// deliberately not modeled here: the client recomputes that itself from feedback_due_date vs today
// (groupFeedbackDueRows in appUtils.ts), so it never has to agree on a field name with the backend.
// `[key:string]:any` absorbs whatever extra field the backend does send for that marker.
export type FeedbackDueRow={id:number;company:string;title:string;status:string;feedback_due_date:string;[key:string]:any}
// /api/stats/ funnel + source rows. Rates are number|null on purpose: null is "no denominator yet",
// which must never render as 0% ("you convert nothing"). `offers` here is *reached* offer over the
// application cohort - a different measure from the flat stats.offers, which is *currently* in offer.
export type FunnelCounts={applications:number;interviews:number;offers:number;applied_to_interview_rate:number|null;interview_to_offer_rate:number|null}
export type Funnel={recent_window_days:number;recent_window_start:string;all_time:FunnelCounts;recent:FunnelCounts;interviews_without_application:number}
export type SourceEffectiveness={source:string;applications:number;interviews:number;interview_rate:number|null}
export type Stats={funnel?:Funnel;source_effectiveness?:SourceEffectiveness[];[key:string]:any}
// TASK-125 AC1/AC2/AC5: mailbox_check_enabled is the explicit off switch (never a cadence of 0 --
// see the model comment on UserProfile.mailbox_check_cadence_minutes for why). The window fields are
// "HH:MM:SS" strings (DRF TimeField's default representation) interpreted in settings.TIME_ZONE,
// Europe/Vienna - see services.mailbox.is_within_check_window. Equal start/end means no restriction.
// TASK-141 AC1/AC3: mailbox_lookback_months bounds how far back fetch_new/backfill_historical_mail
// reach (default 6, the owner's own number) - same UserProfile family as the fields above, and the
// same "0 is rejected, not unlimited" idiom as mailbox_check_cadence_minutes (see that field's own
// comment) rather than the 0-means-unset idiom used elsewhere, because an unbounded lookback is the
// one outcome AC3 forbids by accident.
// TASK-145 AC4/AC5: board_sort_keys is UserProfile's saved multi-sort, wire-compatible with the board's
// own `?ordering=` string (e.g. "status,-fit_score") - the owner chose this over localStorage so the
// same sort follows the account across devices. '' means "no saved sort, use the server default".
// TASK-169 AC1/AC3/AC7: mailbox_identify_window_months is a THIRD window, distinct from
// mailbox_lookback_months (that one bounds FETCHING; this one bounds the app's ATTEMPT to identify a
// job for mail already stored). null means "the owner has not explicitly chosen a value" - read as a
// 3-month default server-side - not "unlimited" (see the backend model field's own comment). A
// non-null value is an explicit choice, which also changes whether rejection/interview-invitation
// mail can be hidden by age (see high_consequence_hidden_count, read inline off GET
// /mailbox-messages/unmatched/ in App.tsx's loadMailboxPanel - that response has no named type here).
export type CandidateProfile={candidate_profile:string;candidate_evidence:string;target_roles:string;preferred_locations:string;salary_expectations:string;language_levels:string;preferred_stack:string;red_flags:string;selling_points:string;learned_application_preferences:string;follow_up_digest_enabled:boolean;mailbox_check_cadence_minutes:number;mailbox_check_calendar_aware:boolean;mailbox_check_enabled:boolean;mailbox_check_window_start:string;mailbox_check_window_end:string;mailbox_salary_floor_eur:number;mailbox_lookback_months:number;mailbox_identify_window_months:number|null;mailbox_do_not_disclose:string;mailbox_calendar_ids:string;board_sort_keys:string;evaluation_prompt_template:string;combined_prompt_template:string;enrichment_prompt_template:string;bulk_links_prompt_template:string}
export type InviteCode={id:number;code:string;label:string;active:boolean;expires_at:string|null;created_at:string}
export type PracticeSession={id:number;job:number|null;job_company:string;job_title:string;question:string;answer_text:string;language:'de'|'en';clarity_score:number;structure_score:number;confidence_score:number;overall_score:number;feedback:string[];stronger_answer:string;evaluator:string;model:string|null;fallback_used:boolean;created_at:string}
// TASK-109: mailbox check ingest + review. classification is a MailboxMessage.CLASSIFICATIONS key.
// TASK-110: draft is null unless this message's classification wanted a reply and matched a job.
// TASK-121 AC1: gmail_draft_id/gmail_message_id/gmail_thread_id are '' on every row written before
// that task, and on every row from a machine on the IMAP transport (no Gmail API ids at all).
// gmail_url is the SAME builder as MailboxMessage.gmail_url below (both key off the underlying
// inbound message's RFC822 Message-ID, not the draft's own gmail_message_id - see serializers.py),
// null when that id is not usable.
// TASK-122 AC2/AC4: chat_history is the app-owned transcript re-fed to the (stateless) model on
// every turn - server-authoritative (never trust a client-resent copy), reset to [] the moment a
// revision is accepted via /edit/ (see views.py's MailboxDraftViewSet.edit).
export type MailboxChatTurn={user_message:string;revised_text:string}
export type MailboxDraft={id:number;status:'written'|'blocked';block_reason:string;subject:string;body_text:string;evaluator:string;gmail_draft_id:string;gmail_message_id:string;gmail_thread_id:string;gmail_url:string|null;chat_history:MailboxChatTurn[];created_at:string}
// TASK-117 AC1: body_text is the received email body (5000-char cap applied at the wire read),
// stored now instead of dropped - see the model docstring for why the minimal-metadata default
// was reversed 2026-08-18.
// TASK-121 AC2/AC4: thread_id is the inbound Gmail thread id (a different id from a draft's own
// gmail_thread_id above). gmail_url is null when this message's RFC822 Message-ID is not usable -
// render no link at all in that case, never a link that 404s into an empty Gmail search.
// TASK-132/TASK-134 AC4: sent_by_owner is a STORED flag (MailboxMessageSerializer, never a
// From-address comparison at render time) distinguishing the owner's own sent mail from what they
// received - the one thing that makes a message list read as an exchange rather than a flat log.
// TASK-135: MailboxMessage's own docstring is the source of truth. calendar_summary/location/
// organizer/start/end are the what/where/with-whom/when of the FIRST iCalendar VEVENT found in a
// text/calendar MIME part - blank string / null on every message with no invitation. attachments is
// METADATA ONLY (filename, mime_type, size) for every OTHER MIME part carrying a filename - no file
// content is ever stored or served, "Reply in Gmail" remains the only route to the actual file.
export type MailboxAttachment={filename:string;mime_type:string;size:number}
// TASK-163: suggested_job is only ever populated by the unmatched-mail endpoint (a SUGGESTION the
// owner confirms, computed from the message's own subject/body - see services.mailbox.
// suggest_job_for_message) - optional because every other MailboxMessage-shaped response (retrieve,
// job mailbox, digest) never sets it, and null when the row names no tracked company or more than one.
// TASK-171 AC1/AC2/AC3: body_truncated/dismissed are also unmatched-list-only (MailboxMessageListSerializer)
// - optional for the same reason suggested_job is. body_truncated says whether body_text here is the
// ~300-char preview or the whole (short) body already; a truncated row's full text is one more request
// away (GET /mailbox-messages/{id}/, TASK-142's retrieve). dismissed is true only when a row was
// explicitly revealed via ?include_dismissed=1 - the default list never includes a dismissed row at all.
export type MailboxMessage={id:number;sender:string;subject:string;body_text:string;received_at:string|null;classification:string;matched_job:number|null;matched_job_company:string;matched_job_title:string;draft:MailboxDraft|null;thread_id:string;gmail_url:string|null;sent_by_owner:boolean;created_at:string;calendar_summary:string;calendar_location:string;calendar_organizer:string;calendar_start:string|null;calendar_end:string|null;attachments:MailboxAttachment[];suggested_job?:{id:number;label:string}|null;body_truncated?:boolean;dismissed?:boolean}
export type MailboxSuggestion={id:number;message:MailboxMessage;job:number;job_company:string;job_title:string;suggestion_type:'status_change'|'interview_date'|'feedback_clear';payload:Record<string,any>;status:'pending'|'confirmed'|'dismissed';created_at:string;decided_at:string|null}
// TASK-117 AC2/AC6: GET /api/jobs/{id}/mailbox/ and POST /api/mailbox-messages/{id}/attach/ both
// answer with this shape (MailboxMessageWithSuggestionsSerializer) - each suggestion nested here is
// a complete MailboxSuggestion (server re-serializes message->suggestion, not the reverse), so the
// same MailboxSuggestionCard renders one from the board panel or one from a job's own mail.
export type JobMailboxMessage=MailboxMessage&{suggestions:MailboxSuggestion[]}
// TASK-120 AC3. ApplicationNote.Meta.ordering is ['-created_at'] (newest first). note_type is kept
// as a bare string rather than a union of the backend's five choices, so a type this file does not
// know about yet still renders (falls back to the raw value) instead of failing a type check.
export type ApplicationNote={id:number;job:number;note:string;note_type:string;created_by:number|null;created_at:string}
// TASK-120 AC1/AC3/AC4: GET /api/jobs/{id}/mailbox/'s response shape as of TASK-120 - every message
// matched to the job (not only ones with a pending suggestion) plus the job's own ApplicationNotes,
// in one round trip. This is a flat per-job list, not a reconstructed thread (see that endpoint's
// docstring) - messages arrive pre-sorted by received_at (nulls last), nothing here re-sorts them.
export type JobMailboxPayload={messages:JobMailboxMessage[];notes:ApplicationNote[]}
// TASK-125 AC6: skip_reason is now one of '' | 'quiet_hours' | 'disabled' | 'outside_window'
// (MailboxRun.SKIP_REASONS) - kept as a bare string, not a union, so a server-added reason still
// renders (falls back to the raw value) instead of failing a type check.
// drafting_skipped: true on a cold-start run that deliberately suppressed reply drafting so it did
// not draft replies to the whole mailbox history - see the model docstring for why this is recorded
// per-run rather than only logged, and check_mailbox.py for the wording this UI mirrors.
export type MailboxRun={id:number;started_at:string;finished_at:string|null;skipped:boolean;skip_reason:string;fetched_count:number;job_related_count:number;uncertain_count:number;suggestion_count:number;draft_written_count:number;draft_blocked_count:number;drafting_skipped:boolean;error:string;digest_messages:MailboxMessage[]}
