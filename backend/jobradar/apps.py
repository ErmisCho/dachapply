from django.apps import AppConfig


class JobradarConfig(AppConfig):
    default_auto_field='django.db.models.BigAutoField'
    name='jobradar'

    def ready(self):
        from jobradar.services.demo_scheduler import start_demo_seed_scheduler
        start_demo_seed_scheduler()
        from jobradar.services.mailbox_loop import start_local_mailbox_loop
        start_local_mailbox_loop()
