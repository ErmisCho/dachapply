import json
import sys
from collections import Counter

from django.core.management.base import BaseCommand

from jobradar.models import ApplicationNote
from jobradar.services.cv_tasks import BASE_TEMPLATE_NOTE_PREFIX


def _console_safe(text):
    encoding=getattr(sys.stdout,'encoding','') or 'utf-8'
    return text.encode(encoding,'replace').decode(encoding,'replace')


class Command(BaseCommand):
    help='Report how many recorded generations used each CV or letter base. Historical generated files are not backfilled.'

    def handle(self, *args, **options):
        counts=Counter()
        skipped=0
        notes=ApplicationNote.objects.filter(note_type='cv_change',note__startswith=BASE_TEMPLATE_NOTE_PREFIX)
        for note in notes.iterator():
            try:
                value=json.loads(note.note[len(BASE_TEMPLATE_NOTE_PREFIX):])
                names={name for group in value.values() if isinstance(group,list)
                       for name in group if isinstance(name,str) and name}
            except (AttributeError,json.JSONDecodeError):
                skipped+=1
                continue
            counts.update(names)

        self.stdout.write('Base template usage:')
        if counts:
            for filename,count in sorted(counts.items()):
                self.stdout.write(_console_safe(f'  {filename}: {count} generation(s)'))
        else:
            self.stdout.write('  No recorded usage yet.')

        self.stdout.write('Bases used exactly once:')
        once=sorted(filename for filename,count in counts.items() if count == 1)
        for filename in once:
            self.stdout.write(_console_safe(f'  {filename}'))
        if not once:
            self.stdout.write('  (none)')
        if skipped:
            self.stdout.write(self.style.WARNING(f'Skipped {skipped} malformed provenance note(s).'))
        self.stdout.write('The 16 existing CVs and 5 existing letters cannot be attributed retrospectively; this report includes only generations recorded after provenance tracking was added.')
