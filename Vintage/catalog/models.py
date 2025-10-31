from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta

import re


# Create your models here.
class Store(models.Model):
    """Список магазинов и адресов"""
    name = models.CharField(max_length=100, verbose_name='Название магазина')
    address = models.CharField(max_length=500, verbose_name='Адрес')

    class Meta:
        verbose_name = 'Адрес'
        verbose_name_plural = 'Адреса'

    def __str__(self):
        return self.name

class ProductCategory(models.Model):
    """Список категорий"""
    name = models.CharField(max_length=20, unique=True, verbose_name='Название')
    description = models.TextField(null=True, blank=True, verbose_name='Описание')
    # order = models.PositiveIntegerField(default=0, verbose_name='Порядок отображения')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        # ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """Список продуктов общий"""
    name = models.CharField(max_length=50, verbose_name='Название')
    description = models.TextField(null=True, blank=True, verbose_name='Описание')
    category = models.ForeignKey(
        to=ProductCategory,
        on_delete=models.PROTECT,
        verbose_name='Категория',
        related_name='products'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    # quantity = models.PositiveIntegerField(default=0)
    # image = models.ImageField(upload_to='products_images')

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'

    def __str__(self):
        return self.name


class ProductBatch(models.Model):
    """Поставки"""
    product = models.ForeignKey(
        to=Product,
        on_delete=models.CASCADE,
        verbose_name='Продукт',
        related_name='batches'
    )
    store = models.ForeignKey(
        to=Store,
        on_delete=models.PROTECT,
        verbose_name='Магазин',
        related_name='batches'
    )
    barcode = models.CharField(
        max_length=50, # поменять на нужное значение, наверно тут 13 цифр максимум
        verbose_name="Штрихкод",
        blank=True,
        null=True
        # , unique=True
    )
    production_date = models.DateField(verbose_name='Дата изготовления')
    expiration_date = models.DateField(verbose_name='Срок годности до')
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name='Количество'
    ) # бывает ли больше одного товара в поставке с одним штрих-кодом?
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена') # нужен ли?
    is_available = models.BooleanField(default=True, verbose_name='Доступен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления партии')

    class Meta:
        verbose_name = 'Партия товара'
        verbose_name_plural = 'Партии товаров'
        ordering = ['expiration_date']

    def clean(self):
        """Валидация дат"""
        if self.production_date and self.expiration_date:
            if self.expiration_date <= self.production_date:
                raise ValidationError('Срок годности должен быть позже даты изготовления')

        if self.barcode:
            # Базовая валидация штрихкода (только цифры)
            if not re.match(r'^\d+$', self.barcode):
                raise ValidationError({'barcode': 'Штрихкод должен содержать только цифры'})

    def __str__(self):
        barcode_info = f" - {self.barcode}" if self.barcode else ""
        return f"{self.product.name} в {self.store.name} (изг.: {self.production_date}){barcode_info}"

    @property
    def days_until_expiration(self):
        """Количество дней до истечения срока годности"""
        if not self.expiration_date:
            return None  # или какое-то значение по умолчанию
        return (self.expiration_date - timezone.now().date()).days

    @property
    def is_expiring_soon(self):
        """Истекает ли срок годности в ближайшие 30 дней"""
        if self.days_until_expiration is None:
            return False
        return 0 <= self.days_until_expiration <= 30

    @property
    def is_expired(self):
        """Просрочен ли товар"""
        if self.days_until_expiration is None:
            return False
        return self.days_until_expiration < 0

    @property
    def total_value(self):
        """Общая стоимость партии"""
        return self.quantity * self.price