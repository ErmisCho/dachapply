import re
from urllib.parse import urlsplit, urlunsplit
from django.utils import timezone
from rest_framework import serializers
from .models import DEFAULT_CANDIDATE_PROFILE, JobLead, JobEvaluation, ApplicationNote, FollowUp, InviteCode, UserProfile
from .services.skill_matcher import smart_skill_status, display_skill_name
from .services.access import accessible_jobs
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
        return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/'), '', ''))
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
    text=text.replace('[','').replace(']','').replace('(','').replace(')','').replace('%22','').replace('"','')
    return re.sub(r'\s+', ' ', text).strip(' ,;:-')


def clean_job_title(value):
    text=clean_label_text(value)
    text=re.sub(r'\s*[-–—,;:]*\s*\(?\s*[mwfdx](?:\s*/\s*[mwfdx]){1,3}\s*\)?\s*$', '', text, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', text).strip(' ,;:-')


class CandidateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=UserProfile
        fields=('candidate_profile','target_roles','preferred_locations','salary_expectations','language_levels','preferred_stack','red_flags','selling_points','evaluation_prompt_template','combined_prompt_template','enrichment_prompt_template','bulk_links_prompt_template')
    def to_representation(self, instance):
        data=super().to_representation(instance)
        return {k: decode_profile_value(v) for k,v in data.items()}
    def validate_candidate_profile(self, value):
        return value or DEFAULT_CANDIDATE_PROFILE
    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, encode_profile_value(field, value))
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
    submitted_for_username=serializers.SerializerMethodField()
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
        if attrs.get('status') in ['applied','interview'] and not attrs.get('status_date'):
            attrs['status_date']=timezone.localdate()
        return super().create(attrs)
    def update(self, instance, attrs):
        new_status=attrs.get('status')
        if new_status in ['applied','interview'] and instance.status != new_status and not attrs.get('status_date'):
            attrs['status_date']=timezone.localdate()
        if new_status and instance.status != new_status and not attrs.get('last_update_date'):
            attrs['last_update_date']=timezone.localdate()
        if new_status and new_status not in ['applied','interview'] and instance.status != new_status and 'status_date' not in attrs:
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
    def get_submitted_for_username(self, obj): return obj.submitted_for.username if obj.submitted_for else ''

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
        if not (attrs.get('url') or attrs.get('raw_description') or attrs.get('company') or attrs.get('title')):
            raise serializers.ValidationError('Provide at least a job URL, description, company, or title')
        return attrs
    def create(self, data):
        data.pop('invite_code', None); data.pop('website', None)
        data['company']=data.get('company') or 'Unknown company'
        data['title']=data.get('title') or 'Untitled role'
        return JobLead.objects.create(source='friend', **data)
