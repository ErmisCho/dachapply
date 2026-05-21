from rest_framework import serializers
from .models import JobLead, JobEvaluation, ApplicationNote, FollowUp, InviteCode


def normalize_job_url(value):
    """Accept normal URLs plus common copy/paste mistakes like
    https-www.karriere.at-jobs-7794074 -> https://www.karriere.at/jobs/7794074.
    """
    value=(value or '').strip()
    if not value:
        return ''
    if value.startswith('http://') or value.startswith('https://'):
        return value
    if value.startswith('https-') or value.startswith('http-'):
        scheme, rest=value.split('-', 1)
        parts=rest.split('-')
        if len(parts) >= 2 and '.' in parts[0]:
            return f'{scheme}://' + parts[0] + '/' + '/'.join(parts[1:])
    if '.' in value and ' ' not in value:
        return 'https://' + value
    return value


def value_is_valid_url(value):
    value=normalize_job_url(value)
    if not value:
        return False
    try:
        serializers.URLField(max_length=1000).run_validation(value)
        return True
    except serializers.ValidationError:
        return False


class JobEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model=JobEvaluation; fields='__all__'; read_only_fields=('created_at','updated_at')
    def validate_fit_score(self, v):
        if v < 0 or v > 100: raise serializers.ValidationError('fit_score must be 0..100')
        return v

class ApplicationNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model=ApplicationNote; fields='__all__'; read_only_fields=('created_by','created_at')

class FollowUpSerializer(serializers.ModelSerializer):
    company=serializers.CharField(source='job.company', read_only=True)
    title=serializers.CharField(source='job.title', read_only=True)
    class Meta:
        model=FollowUp; fields='__all__'; read_only_fields=('created_at','updated_at')

class JobLeadSerializer(serializers.ModelSerializer):
    latest_evaluation=serializers.SerializerMethodField()
    url=serializers.CharField(max_length=1000, required=False, allow_blank=True)
    class Meta:
        model=JobLead; fields='__all__'; read_only_fields=('created_by','created_at','updated_at')
        extra_kwargs={'company': {'required': False, 'allow_blank': True}, 'title': {'required': False, 'allow_blank': True}}
    def validate_url(self, value):
        value=normalize_job_url(value)
        if value:
            serializers.URLField(max_length=1000).run_validation(value)
        return value
    def validate(self, attrs):
        if not attrs.get('url') and value_is_valid_url(attrs.get('company')):
            attrs['url']=normalize_job_url(attrs.get('company'))
            attrs['company']=''
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
    def create(self, attrs):
        attrs['company']=attrs.get('company') or 'Unknown company'
        attrs['title']=attrs.get('title') or 'Untitled role'
        return super().create(attrs)
    def get_latest_evaluation(self, obj):
        ev=obj.evaluations.first()
        return JobEvaluationSerializer(ev).data if ev else None

class PublicSubmissionSerializer(serializers.Serializer):
    invite_code=serializers.CharField(max_length=80)
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
    def validate_invite_code(self, code):
        try: inv=InviteCode.objects.get(code=code)
        except InviteCode.DoesNotExist: raise serializers.ValidationError('Invalid invite code')
        if not inv.is_valid(): raise serializers.ValidationError('Inactive or expired invite code')
        return code
    def validate(self, attrs):
        if attrs.get('website'): raise serializers.ValidationError('Spam rejected')
        if not attrs.get('url') and value_is_valid_url(attrs.get('company')):
            attrs['url']=normalize_job_url(attrs.get('company'))
            attrs['company']=''
        if not (attrs.get('url') or attrs.get('raw_description') or attrs.get('company') or attrs.get('title')):
            raise serializers.ValidationError('Provide at least a job URL, description, company, or title')
        return attrs
    def create(self, data):
        data.pop('invite_code', None); data.pop('website', None)
        data['company']=data.get('company') or 'Unknown company'
        data['title']=data.get('title') or 'Untitled role'
        return JobLead.objects.create(source='friend', **data)
