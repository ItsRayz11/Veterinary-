from django.core.management.base import BaseCommand, CommandError

from apps.automation.tasks import TASKS, run_task


class Command(BaseCommand):
    help = "Run an automation task now: " + ", ".join(sorted(TASKS))

    def add_arguments(self, parser):
        parser.add_argument("task", choices=sorted(TASKS))

    def handle(self, *args, **opts):
        run = run_task(opts["task"])
        self.stdout.write(f"{run.task}: {run.status} {run.summary} {run.error}")
        if run.status != "ok":
            raise CommandError(run.error)
