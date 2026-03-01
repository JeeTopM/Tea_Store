import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
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
    UNIT_G = "g"
    UNIT_PCS = "pcs"

    UNIT_CHOICES = [
        (UNIT_G, "г"),
        (UNIT_PCS, "шт"),
    ]

    name = models.CharField(max_length=100, verbose_name='Название')
    description = models.TextField(null=True, blank=True, verbose_name='Описание')
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.PROTECT,
        verbose_name='Категория',
        related_name='products'
    )
    unit = models.CharField(
        max_length=10,
        choices=UNIT_CHOICES,
        default=UNIT_PCS,
        verbose_name="Ед. изм."
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


User = get_user_model()


class StockMovement(models.Model):
    """Журнал движений остатков (приход/списание/резерв/возврат)"""

    REASON_IN = "IN"
    REASON_OUT = "OUT"
    REASON_RESERVE_GIFT = "RESERVE_GIFT"
    REASON_RETURN_GIFT = "RETURN_GIFT"
    REASON_ADJUST = "ADJUST"

    REASON_CHOICES = [
        (REASON_IN, "Корректировка (+"),
        (REASON_OUT, "Корректировка (-)"),
        (REASON_RESERVE_GIFT, "Резерв в подарок"),
        (REASON_RETURN_GIFT, "Возврат из подарка"),
        (REASON_ADJUST, "Корректировка"),
    ]

    stock = models.ForeignKey(
        "Stock",
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name="Остаток (партия+магазин)",
    )

    # delta: +N увеличивает остаток, -N уменьшает
    delta = models.IntegerField(verbose_name="Изменение (дельта)")

    reason = models.CharField(max_length=20, choices=REASON_CHOICES, verbose_name="Причина")

    comment = models.CharField(max_length=255, blank=True, default="", verbose_name="Комментарий")

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_movements",
        verbose_name="Кто сделал",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Когда")

    class Meta:
        verbose_name = "Движение остатка"
        verbose_name_plural = "Движения остатков"
        ordering = ["-created_at"]

    def __str__(self):
        sign = "+" if self.delta >= 0 else ""
        return f"{self.stock} {sign}{self.delta} ({self.get_reason_display()})"

def apply_stock_movement(*, stock: Stock, delta: int, reason: str, user=None, comment: str = "") -> StockMovement:
    if delta == 0:
        raise ValidationError("Дельта не может быть 0")

    with transaction.atomic():
        stock_locked = Stock.objects.select_for_update().get(pk=stock.pk)

        new_qty = stock_locked.quantity + delta
        if new_qty < 0:
            raise ValidationError(f"Недостаточно остатка. Сейчас {stock_locked.quantity}, пытаешься изменить на {delta}.")

        stock_locked.quantity = new_qty
        stock_locked.save(update_fields=["quantity"])

        movement = StockMovement.objects.create(
            stock=stock_locked,
            delta=delta,
            reason=reason,
            created_by=user if (user and getattr(user, "is_authenticated", False)) else None,
            comment=comment,
        )
        return movement