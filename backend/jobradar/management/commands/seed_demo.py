from django.core.management.base import BaseCommand

from jobradar.services.demo_data import DEMO_PASSWORD, DEMO_USERNAME
from jobradar.services.demo_scheduler import seed_demo_if_due


class Command(BaseCommand):
    help='Seed DACHApply demo data, including the public demo user, friend referrals, interviews, evaluations, and follow-ups.'

    def handle(self, *args, **opts):
        _ran, user, jobs = seed_demo_if_due(force=True)
        interview_count = sum(1 for job in jobs if job.status == 'interview')
        referral_count = sum(1 for job in jobs if job.submitted_for_id == user.id)
        self.stdout.write(self.style.SUCCESS(
            f'Seeded demo user {DEMO_USERNAME} / {DEMO_PASSWORD}: '
            f'{len(jobs)} jobs, {interview_count} interviews, {referral_count} friend referrals.'
        ))
