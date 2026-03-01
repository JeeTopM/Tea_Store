from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from catalog.models import ProductCategory, Product, ProductBatch, Store, Stock


class ExpiringReportTests(TestCase):

    def setUp(self):
        self.category = ProductCategory.objects.create(name="Молоко")
        self.product = Product.objects.create(
            name="Молоко 3.2%",
            category=self.category
        )
        self.store = Store.objects.create(
            name="Магазин 1",
            address="Адрес"
        )

    def test_expired_batch_with_quantity_appears(self):
        batch = ProductBatch.objects.create(
            product=self.product,
            production_date=timezone.now().date() - timedelta(days=10),
            expiration_date=timezone.now().date() - timedelta(days=1),
            price=100,
            is_available=True
        )

        Stock.objects.create(
            batch=batch,
            store=self.store,
            quantity=5
        )

        response = self.client.get("/report/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Молоко 3.2%")

    def test_batch_with_zero_quantity_not_in_report(self):
        batch = ProductBatch.objects.create(
            product=self.product,
            production_date=timezone.now().date(),
            expiration_date=timezone.now().date(),
            price=100,
            is_available=True
        )

        Stock.objects.create(
            batch=batch,
            store=self.store,
            quantity=0
        )

        response = self.client.get("/report/")
        self.assertNotContains(response, "Молоко 3.2%")