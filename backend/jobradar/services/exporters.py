import csv, io, json
from jobradar.models import DEFAULT_CANDIDATE_PROFILE, JobLead

def jobs_json(queryset=None):
    rows=[]
    qs=(queryset if queryset is not None else JobLead.objects.all()).prefetch_related('evaluations')
    for j in qs:
        ev=j.evaluations.first()
        rows.append({'id':j.id,'company':j.company,'title':j.title,'location':j.location,'url':j.url,'status':j.status,'status_date':j.status_date,'interview_stage':j.interview_stage,'interview_total':j.interview_total,'last_update_date':j.last_update_date,'feedback_due_date':j.feedback_due_date,'work_mode':j.work_mode,'latest_evaluation': None if not ev else {'fit_score':ev.fit_score,'priority':ev.priority,'recommendation':ev.recommendation,'summary':ev.summary}})
    return json.dumps(rows, indent=2, default=str)

def jobs_csv(queryset=None):
    buf=io.StringIO(); w=csv.writer(buf)
    w.writerow(['id','company','title','location','url','work_mode','status','status_date','interview_stage','interview_total','last_update_date','feedback_due_date','fit_score','priority','recommendation','created_at'])
    qs=(queryset if queryset is not None else JobLead.objects.all()).prefetch_related('evaluations')
    for j in qs:
        ev=j.evaluations.first()
        w.writerow([j.id,j.company,j.title,j.location,j.url,j.work_mode,j.status,j.status_date or '',j.interview_stage or '',j.interview_total or '',j.last_update_date or '',j.feedback_due_date or '',ev.fit_score if ev else '',ev.priority if ev else '',ev.recommendation if ev else '',j.created_at.isoformat()])
    return buf.getvalue()

def chatgpt_brief(queryset=None, candidate_profile=None):
    parts=['# DACHApply ChatGPT Brief','', '## Candidate profile', candidate_profile or DEFAULT_CANDIDATE_PROFILE, '', '## Jobs']
    qs=queryset if queryset is not None else JobLead.objects.all()
    for j in qs[:100]:
        outcome=f'status: {j.status}'
        if j.status_date: outcome+=f', status date: {j.status_date}'
        if j.interview_stage: outcome+=f', interview stage: {j.interview_stage}/{j.interview_total or "?"}'
        if j.last_update_date: outcome+=f', last update: {j.last_update_date}'
        if j.feedback_due_date: outcome+=f', feedback due: {j.feedback_due_date}'
        parts.append(f'- #{j.id} {j.company} - {j.title} ({j.location}, {j.work_mode}; {outcome}) {j.url}')
    return '\n'.join(parts)
