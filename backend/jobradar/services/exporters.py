import csv, io, json
from jobradar.models import JobLead
from .prompt_builder import CANDIDATE_PROFILE

def jobs_json():
    rows=[]
    for j in JobLead.objects.prefetch_related('evaluations'):
        ev=j.evaluations.first()
        rows.append({'id':j.id,'company':j.company,'title':j.title,'location':j.location,'url':j.url,'status':j.status,'work_mode':j.work_mode,'latest_evaluation': None if not ev else {'fit_score':ev.fit_score,'priority':ev.priority,'recommendation':ev.recommendation,'summary':ev.summary}})
    return json.dumps(rows, indent=2, default=str)

def jobs_csv():
    buf=io.StringIO(); w=csv.writer(buf)
    w.writerow(['id','company','title','location','url','work_mode','status','fit_score','priority','recommendation','created_at'])
    for j in JobLead.objects.prefetch_related('evaluations'):
        ev=j.evaluations.first()
        w.writerow([j.id,j.company,j.title,j.location,j.url,j.work_mode,j.status, ev.fit_score if ev else '', ev.priority if ev else '', ev.recommendation if ev else '', j.created_at.isoformat()])
    return buf.getvalue()

def chatgpt_brief():
    parts=['# DACHApply ChatGPT Brief','', '## Candidate profile', CANDIDATE_PROFILE, '', '## Jobs']
    for j in JobLead.objects.all()[:100]:
        parts.append(f'- #{j.id} {j.company} — {j.title} ({j.location}, {j.work_mode}) {j.url}')
    return '\n'.join(parts)
