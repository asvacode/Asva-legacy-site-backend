from django.contrib import admin
from unfold import admin as UnfoldAdmin

from .models import ExistingMember, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(UnfoldAdmin.ModelAdmin):
    list_display = ("user", "reference_code")
    search_fields = ("user__username", "user__email", "reference_code")


@admin.register(ExistingMember)
class ExistingMemberAdmin(UnfoldAdmin.ModelAdmin):
    list_display = ("phone_number", "user", "created_at")
    search_fields = ("phone_number", "user__username", "user__email")
    autocomplete_fields = ("user",)
    fields = ("phone_number", "user", "created_at")
    readonly_fields = ("phone_number", "created_at")
