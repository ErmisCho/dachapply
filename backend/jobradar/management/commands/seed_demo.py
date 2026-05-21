from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from jobradar.models import InviteCode, JobLead, JobEvaluation, FollowUp

class Command(BaseCommand):
    help='Seed DACHApply demo data. Create an admin with: python manage.py createsuperuser'
    def handle(self,*args,**opts):
        InviteCode.objects.get_or_create(code='FRIEND-DEMO', defaults={'label':'Demo friends invite','active':True})
        jobs=[]
        samples=[('Dynatrace','Python Backend Engineer','Vienna','hybrid'),('Elastic','Search Engineer','Germany Remote','remote'),('FinTech GmbH','Django Developer','Berlin','hybrid'),('CloudOps AG','SRE Engineer','Munich','onsite'),('AI Search Lab','RAG Engineer','Vienna','hybrid')]
        for c,t,l,w in samples:
            j,_=JobLead.objects.get_or_create(company=c,title=t,defaults={'location':l,'work_mode':w,'url':'https://example.com/jobs/'+c.lower().split()[0],'source':'seed','raw_description':f'{t} role using Python, APIs, SQL, Docker and search systems.','language_requirements':'English; German helpful'})
            jobs.append(j)
        for j,score,prio,rec in [(jobs[0],86,'high','apply'),(jobs[3],55,'low','maybe')]:
            if not j.evaluations.exists():
                JobEvaluation.objects.create(job=j,fit_score=score,priority=prio,recommendation=rec,summary='Seed evaluation',main_match_reasons=['Python/backend/search fit'],main_gaps=['Cloud depth'],required_skills=['Python','SQL'],nice_to_have_skills=['Azure'],matched_skills=['Python'],missing_skills=['Terraform'],cv_adjustment_notes='Emphasize backend impact.',interview_prep_notes='Prepare system design.',risk_notes='Be honest about gaps.',next_action='Tailor CV and apply.',structured_json_raw={})
        FollowUp.objects.get_or_create(job=jobs[0], follow_up_date=timezone.localdate()+timedelta(days=2), defaults={'reason':'Check recruiter reply'})
        FollowUp.objects.get_or_create(job=jobs[2], follow_up_date=timezone.localdate()-timedelta(days=1), defaults={'reason':'Overdue application decision'})
        self.stdout.write(self.style.SUCCESS('Seeded demo data. Admin setup: python manage.py createsuperuser'))
