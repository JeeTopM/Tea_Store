import re
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Store(models.Model):
    """Магазин и его адрес"""
    name = models.CharField(max_length=100, unique=True, verbose_name='Название магазина')
    address = models.CharField(max_length=500, verbose_name='Адрес')

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Магазины'

    def __str__(self):
        return self.name


class ProductCategory(models.Model):
    """Категория продуктов"""
    name = models.CharField(max_length=50, unique=True, verbose_name='Название')
    description = models.TextField(null=True, blank=True, verbose_name='Описание')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """Продукт"""
    name = models.CharField(max_length=100, verbose_name='Название')
    description = models.TextField(null=True, blank=True, verbose_name='Описание')
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.PROTECT,
        verbose_name='Категория',
        related_name='products'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'
        unique_together = ('name', 'category')
        ordering = ['name']

    def __str__(self):
        return self.name


class ProductBatchManager(models.Manager):
    def expiring_soon(self, days=None):
        if days is None:
            days = settings.EXPIRING_WARNING_DAYS
        today = timezone.now().date()
        return self.filter(
            expiration_date__range=[today, today + timedelta(days=days)],
            is_available=True
        )

    def expiring_critical(self):
        today = timezone.now().date()
        return self.filter(
            expiration_date__range=[today, today + timedelta(days=settings.EXPIRING_SOON_DAYS)],
            is_available=True
        )

    def expired(self):
        return self.filter(expiration_date__lt=timezone.now().date(), is_available=True)


class ProductBatch(models.Model):
    """Партии (поставки) товаров"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='batches', verbose_name='Продукт')
    barcode = models.CharField(max_length=50, blank=True, null=True, verbose_name='Штрихкод')
    production_date = models.DateField(verbose_name='Дата изготовления')
    expiration_date = models.DateField(verbose_name='Срок годности до')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    is_available = models.BooleanField(default=True, verbose_name='Доступен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления партии')

    objects = ProductBatchManager()

    class Meta:
        verbose_name = 'Партия товара'
        verbose_name_plural = 'Партии товаров'
        ordering = ['expiration_date']

    def clean(self):
        if self.production_date and self.expiration_date:
            if self.expiration_date <= self.production_date:
                raise ValidationError('Срок годности должен быть позже даты изготовления')
        if self.production_date and self.production_date > timezone.now().date():
            raise ValidationError('Дата изготовления не может быть в будущем')
        if self.barcode and not re.match(r'^\d+$', self.barcode):
            raise ValidationError({'barcode': 'Штрихкод должен содержать только цифры'})

    def __str__(self):
        bc = f" [{self.barcode}]" if self.barcode else ""
        return f"{self.product.name}{bc} — {self.production_date} → {self.expiration_date}"

    # --- Свойства состояния ---
    @property
    def days_until_expiration(self):
        return (self.expiration_date - timezone.now().date()).days

    @property
    def is_expired(self):
        return self.days_until_expiration < 0

    @property
    def is_expiring_critical(self):
        d = self.days_until_expiration
        return d is not None and 0 <= d <= settings.EXPIRING_SOON_DAYS

    @property
    def is_expiring_warning(self):
        d = self.days_until_expiration
        return d is not None and 0 <= d <= settings.EXPIRING_WARNING_DAYS

    @property
    def total_value(self):
        return self.quantity * self.price

class Stock(models.Model):
    """Остаток конкретной партии в конкретном магазине"""

    batch = models.ForeignKey(
        'ProductBatch',
        on_delete=models.CASCADE,
        related_name='stocks',
        verbose_name='Партия'
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='stocks',
        verbose_name='Магазин'
    )

    quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Остаток'
    )

    class Meta:
        verbose_name = 'Остаток'
        verbose_name_plural = 'Остатки'
        constraints = [
            models.UniqueConstraint(
                fields=['batch', 'store'],
                name='unique_batch_store'
            )
        ]

    def __str__(self):
        return f"{self.store.name} — {self.batch} ({self.quantity})"