from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from openpyxl import Workbook
from rest_framework.test import APITestCase

from accounts.models import ExistingMember, UserProfile
from accounts.utils import normalize_nigerian_phone_number
from cms.models import Team, UserTeam
from payments.models import Payment
from payments.services import verify_payment


User = get_user_model()
PHONE = "+2348031234567"
PASSWORD = "A-very-strong-password-879!"


class ExistingMemberActivationTests(APITestCase):
    def setUp(self):
        self.member = ExistingMember.objects.create(phone_number=PHONE)
        self.activation_payload = {
            "phone_number": "08031234567",
            "email": "member@example.com",
            "password": PASSWORD,
        }

    def test_roster_member_activates_and_logs_in_by_phone_without_payment(self):
        response = self.client.post(
            "/api/auth/activate-existing-member",
            self.activation_payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        user = User.objects.get(email="member@example.com")
        profile = UserProfile.objects.get(user=user)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertTrue(user.is_active)
        self.assertEqual(normalize_nigerian_phone_number(profile.phone_number), PHONE)
        self.assertTrue(profile.is_active)
        self.member.refresh_from_db()
        self.assertEqual(self.member.user_id, user.pk)
        self.assertFalse(Payment.objects.filter(user=user).exists())

        login = self.client.post(
            "/api/auth/login",
            {"phone_number": "0803 123 4567", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        self.assertEqual(self.client.get("/api/cms/teams").status_code, 200)

    def test_unlisted_phone_cannot_activate_or_log_in(self):
        payload = {**self.activation_payload, "phone_number": "08031234568"}
        activation = self.client.post(
            "/api/auth/activate-existing-member",
            payload,
            format="json",
        )
        login = self.client.post(
            "/api/auth/login",
            {"phone_number": payload["phone_number"], "password": PASSWORD},
            format="json",
        )

        self.assertEqual(activation.status_code, 200)
        self.assertEqual(login.status_code, 401)
        self.assertEqual(User.objects.count(), 0)
        self.assertIsNone(self.member.user_id)
        self.assertEqual(self.client.get("/api/me/profile").status_code, 401)

    def test_activation_cannot_reset_an_already_active_member_password(self):
        first = self.client.post(
            "/api/auth/activate-existing-member",
            self.activation_payload,
            format="json",
        )
        self.assertEqual(first.status_code, 200, first.data)
        changed_payload = {
            **self.activation_payload,
            "password": "Different-password-890!",
            "email": "changed@example.com",
        }
        second = self.client.post(
            "/api/auth/activate-existing-member",
            changed_payload,
            format="json",
        )

        self.assertEqual(second.status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.get()
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.email, "member@example.com")

    def test_activation_preserves_existing_user_and_club_membership(self):
        user = User.objects.create_user(
            username="existing-club-member",
            email="old@example.com",
            password=PASSWORD,
            is_active=False,
        )
        UserProfile.objects.create(
            user=user,
            reference_code="ASV-EXIST1",
            phone_number=PHONE,
            is_active=False,
        )
        team = Team.objects.create(name="Existing Members")
        membership = UserTeam.objects.create(user=user, team=team)

        response = self.client.post(
            "/api/auth/activate-existing-member",
            self.activation_payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(User.objects.count(), 1)
        self.member.refresh_from_db()
        self.assertEqual(self.member.user_id, user.pk)
        self.assertTrue(UserTeam.objects.filter(pk=membership.pk, user=user).exists())
        login = self.client.post(
            "/api/auth/login",
            {"username": "08031234567", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        self.assertEqual(self.client.get("/api/cms/teams").data[0]["id"], team.pk)

    def test_existing_email_cannot_be_used_to_take_over_another_account(self):
        User.objects.create_user(
            username="unrelated-account",
            email="member@example.com",
            password=PASSWORD,
        )

        response = self.client.post(
            "/api/auth/activate-existing-member",
            self.activation_payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.member.__class__.objects.get(pk=self.member.pk).user_id)
        self.assertEqual(User.objects.count(), 1)

    def test_activation_does_not_bypass_an_unpaid_new_member_payment(self):
        user = User.objects.create_user(
            username="unpaid-new-member",
            email="old@example.com",
            password=PASSWORD,
            is_active=False,
        )
        profile = UserProfile.objects.create(
            user=user,
            reference_code="ASV-UNPAID1",
            phone_number=PHONE,
            is_active=False,
        )
        payment = Payment.objects.create(
            user=user,
            amount=Decimal("1000.00"),
            idempotency_key="unpaid-member-account-payment",
            purpose=Payment.Purpose.ACCOUNT_CREATION,
        )
        self.member.user = user
        self.member.save(update_fields=["user"])

        response = self.client.post(
            "/api/auth/activate-existing-member",
            self.activation_payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        profile.refresh_from_db()
        payment.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertFalse(profile.is_active)
        self.assertEqual(payment.status, Payment.Status.PENDING)


class ExistingMemberImportTests(TestCase):
    def create_workbook(self, directory, numbers):
        workbook_path = Path(directory) / "members.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Members"
        sheet.append(["Name", "Phone"])
        for row in numbers:
            sheet.append(row)
        workbook.save(workbook_path)
        return workbook_path

    def run_import(self, workbook_path, *extra_args):
        call_command(
            "import_existing_members",
            "--file",
            str(workbook_path),
            "--sheet",
            "Members",
            *extra_args,
        )

    def test_import_detects_duplicates_after_normalizing_phone_numbers(self):
        with TemporaryDirectory() as directory:
            workbook_path = self.create_workbook(
                directory,
                [
                    ["First", "08031234567"],
                    ["Second", "+234 803 123 4567"],
                ],
            )

            with self.assertRaisesRegex(CommandError, "Duplicate phone numbers"):
                self.run_import(workbook_path)

        self.assertFalse(ExistingMember.objects.exists())

    def test_import_rejects_invalid_phone_numbers_without_skip_option(self):
        with TemporaryDirectory() as directory:
            workbook_path = self.create_workbook(
                directory,
                [["Valid", "08031234567"], ["Invalid", "not a phone"]],
            )

            with self.assertRaisesRegex(CommandError, "Invalid Nigerian phone numbers"):
                self.run_import(workbook_path)

        self.assertFalse(ExistingMember.objects.exists())

    def test_import_can_skip_invalid_rows_after_explicit_confirmation(self):
        with TemporaryDirectory() as directory:
            workbook_path = self.create_workbook(
                directory,
                [["Valid", "08031234567"], ["Invalid", "not a phone"]],
            )

            self.run_import(workbook_path, "--skip-invalid")

        self.assertEqual(
            list(ExistingMember.objects.values_list("phone_number", flat=True)),
            [PHONE],
        )


class NewMemberRegistrationPaymentTests(APITestCase):
    def test_registration_still_requires_payment_to_activate_profile(self):
        registration = self.client.post(
            "/api/auth/register",
            {
                "username": "new-member",
                "email": "new-member@example.com",
                "password": PASSWORD,
                "phone_number": "08031234568",
            },
            format="json",
        )
        self.assertEqual(registration.status_code, 201, registration.data)
        user = User.objects.get(username="new-member")
        profile = UserProfile.objects.get(user=user)
        self.assertFalse(profile.is_active)
        self.assertFalse(ExistingMember.objects.exists())

        payment = Payment.objects.create(
            user=user,
            amount=Decimal("1000.00"),
            idempotency_key="new-member-account-payment",
            purpose=Payment.Purpose.ACCOUNT_CREATION,
        )
        settled = verify_payment(
            payment.idempotency_key,
            paystack_data={
                "status": "success",
                "amount": 100000,
                "currency": "NGN",
            },
        )

        profile.refresh_from_db()
        self.assertEqual(settled.status, Payment.Status.SUCCESS)
        self.assertTrue(profile.is_active)
