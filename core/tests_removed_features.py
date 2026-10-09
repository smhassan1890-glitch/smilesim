"""Phone refresh, SMS gateway and SIM inventory are gone from the product."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import UserProfile
from core.models import AppSettings
from customers.services import create_customer

User = get_user_model()


class RemovedFeaturesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("mgr_removed", password="x")
        UserProfile.objects.update_or_create(
            user=cls.user,
            defaults={"role": UserProfile.Role.MANAGEMENT, "is_active_profile": True},
        )

    def setUp(self):
        from django.utils import translation

        translation.activate("en")
        AppSettings.objects.update_or_create(pk=1, defaults={"default_language": "en"})
        self.client = Client()
        self.client.cookies["django_language"] = "en"
        self.client.force_login(self.user)

    def test_removed_routes_return_404(self):
        for url in (
            "/management/inventory/",
            "/management/inventory/main/",
            "/phone-refresh/",
            "/phone-refresh/api/refresh/",
            "/management/phone-refresh/settings/",
            "/management/sms-gateway/settings/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_sidebar_has_no_removed_sections(self):
        response = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(response.status_code, 200)
        for marker in (
            'data-rd-nav-group="update-link"',
            'data-rd-nav-group="messages-update"',
            "/management/inventory/",
        ):
            self.assertNotContains(response, marker)

    def test_customer_detail_has_no_sim_stock_card(self):
        customer = create_customer(name="Removed Features", user=self.user)
        response = self.client.get(reverse("customers:customer_detail", args=[customer.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "SIM stock")
