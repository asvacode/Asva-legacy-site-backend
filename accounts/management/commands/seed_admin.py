from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.contrib.auth.models import Group, User
from dotenv import load_dotenv
import os
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
import traceback
load_dotenv()

DEFAULT_ACTIONS = ["add", "view", "delete", "change"]

MANAGER_PERMISSIONS = {
    "cms": {
        "certificate": DEFAULT_ACTIONS, 
        "team": DEFAULT_ACTIONS, 
        "teamjoinrequest": DEFAULT_ACTIONS, 
        "userteam": DEFAULT_ACTIONS,
        "event": DEFAULT_ACTIONS,
        "link": DEFAULT_ACTIONS, 
        "internship": DEFAULT_ACTIONS, 
        "document": DEFAULT_ACTIONS, 
        "content": DEFAULT_ACTIONS
    }, 
    "payments": {
        f"paymentclaim": ["view"]
    }
}

class Command(BaseCommand):
    help = "This command creates a django command with the configuration provided from the environment variables"

    def handle(self, *args, **kwargs):
        self._create_manager_group()
        self._create_super_admin()
        self.stdout.write(self.style.SUCCESS("You have successfully created the user admin"))

    def _create_manager_group(self):
        group, _ = Group.objects.get_or_create(name="Manager")

        permissions_to_add = []
        for app_label, models in MANAGER_PERMISSIONS.items():
            for model_name, actions in models.items():
                for action in actions:
                    try:
                        permissions_to_add.append(
                            self._resolve_permission(app_label, model_name.lower(), action)
                        )
                    except (ContentType.DoesNotExist, Permission.DoesNotExist) as e:
                        print([(x.app_label, x.model) for x in ContentType.objects.all()])
                        traceback.print_exc()
                        raise CommandError(e)
        if permissions_to_add:
            group.permissions.set(permissions_to_add)

        group.save()

    def _create_super_admin(self):
        user, is_created = User.objects.get_or_create(
            username=os.environ.get("ADMIN_USERNAME"),
            defaults={
                "email": os.environ.get("ADMIN_EMAIL"),
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if is_created:
            user.set_password(os.environ.get("ADMIN_PASSWORD"))
        user.is_staff = True
        user.is_superuser = True
        user.save()
            
    def _resolve_permission(self, app_label: str, model_name: str, action: str) -> Permission:
        content_type = ContentType.objects.get(app_label=app_label, model=model_name)
        codename = f"{action}_{model_name}" if action in DEFAULT_ACTIONS else action
        return Permission.objects.get(codename=codename, content_type=content_type)
    
    