from django.apps import AppConfig


class JobradarConfig(AppConfig):
    default_auto_field='django.db.models.BigAutoField'
    name='jobradar'

    def ready(self):
        from jobradar.services.demo_scheduler import start_demo_seed_scheduler
        start_demo_seed_scheduler()
