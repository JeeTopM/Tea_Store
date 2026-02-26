from django.conf import settings
from django.contrib import admin

from .models import ProductCategory, Product, ProductBatch, Store


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name','address']

@admin.register(ProductCategory)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name'] # , 'order']
    # list_editable = ['order']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'batch_count', 'created_at']
    list_filter = ['category']
    search_fields = ['name', 'description']

    def batch_count(self, obj):
        return obj.batches.count()

    batch_count.short_description = 'Количество партий'


@admin.register(ProductBatch)
class ProductBatchAdmin(admin.ModelAdmin):
    list_display = [
        'product',
        'store',
        'barcode',
        'production_date',
        'expiration_date',
        'days_until_expiration_display',
        'quantity',
        'price',
        'total_value',
        'is_available'
    ]
    list_filter = ['store','product__category', 'is_available', 'production_date']
    search_fields = ['product__name', 'barcode']
    list_editable = ['quantity', 'price', 'is_available']
    readonly_fields = ['created_at']

    def days_until_expiration_display(self, obj):
        if obj.days_until_expiration is None:
            return "—"
        days = obj.days_until_expiration
        if days < 0:
            return f"❌ Просрочен ({abs(days)} дн.)"
        elif days <= settings.EXPIRING_SOON_DAYS:
            return f"⚠️ Скоро истекает ({days} дн.)"
        elif days <= settings.EXPIRING_WARNING_DAYS:
            return f"🟡 {days} дн."
        else:
            return f"✅ {days} дн."

    days_until_expiration_display.short_description = 'До истечения срока'