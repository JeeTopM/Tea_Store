from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .forms import StoreForm, ProductCategoryForm, ProductForm, ProductBatchForm
from .models import ProductCategory, Product, ProductBatch
from .models import Store


# --- Главная страница ---
def home(request):
    today = timezone.now().date()
    soon7 = today + timedelta(days=settings.EXPIRING_SOON_DAYS)
    soon30 = today + timedelta(days=settings.EXPIRING_WARNING_DAYS)

    stores = (
        Store.objects
        .annotate(
            expired_count=Count(
                "batches",
                filter=Q(batches__is_available=True, batches__expiration_date__lt=today),
            ),
            expiring7_count=Count(
                "batches",
                filter=Q(batches__is_available=True, batches__expiration_date__gte=today, batches__expiration_date__lte=soon7),
            ),
            expiring30_count=Count(
                "batches",
                filter=Q(batches__is_available=True, batches__expiration_date__gt=soon7, batches__expiration_date__lte=soon30),
            ),
        )
        .order_by("name")
    )

    store_statuses = []
    for store in stores:
        if store.expired_count > 0:
            status_text, status_class = "❌ ПРОСРОЧКА", "bg-danger text-white"
        elif store.expiring7_count > 0:
            status_text, status_class = "⚠️ СКОРО", "bg-warning"
        else:
            status_text, status_class = "✅ ВСЁ ОК", "bg-success text-white"

        store_statuses.append({
            "store": store,
            "status_text": status_text,
            "status_class": status_class,
            "expired_count": store.expired_count,
            "expiring_count": store.expiring7_count,
            "warning_count": store.expiring30_count,
        })

    return render(request, "catalog/home.html", {"store_statuses": store_statuses})


# --- Универсальные CRUD-хелперы ---
def handle_form(request, form_class, template, redirect_name, instance=None, title=''):
    form = form_class(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{title} успешно сохранено!')
        return redirect(redirect_name)
    return render(request, template, {'form': form, 'title': title})

def store_detail(request, pk):
    store = get_object_or_404(Store, pk=pk)

    batches = (
        ProductBatch.objects
        .select_related('product__category')
        .filter(store=store, is_available=True)
        .order_by('expiration_date')
    )

    return render(request, 'catalog/store_detail.html', {
        'store': store,
        'batches': batches,
    })

# --- Магазины ---
def store_list(request):
    return render(request, 'catalog/store_list.html', {'stores': Store.objects.all()})


def store_create(request):
    return handle_form(request, StoreForm, 'catalog/store_form.html', 'store_list', title='Магазин')


def store_update(request, pk):
    return handle_form(request, StoreForm, 'catalog/store_form.html', 'store_list',
                       instance=get_object_or_404(Store, pk=pk), title='Магазин')


def store_delete(request, pk):
    store = get_object_or_404(Store, pk=pk)
    if request.method == 'POST':
        store.delete()
        messages.success(request, 'Магазин удалён!')
        return redirect('store_list')
    return render(request, 'catalog/store_confirm_delete.html', {'store': store})


# --- Категории ---
def category_list(request):
    return render(request, 'catalog/category_list.html', {'categories': ProductCategory.objects.all()})


def category_create(request):
    return handle_form(request, ProductCategoryForm, 'catalog/category_form.html', 'category_list', title='Категория')


def category_update(request, pk):
    return handle_form(request, ProductCategoryForm, 'catalog/category_form.html', 'category_list',
                       instance=get_object_or_404(ProductCategory, pk=pk), title='Категория')


def category_delete(request, pk):
    category = get_object_or_404(ProductCategory, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Категория удалена!')
        return redirect('category_list')
    return render(request, 'catalog/category_confirm_delete.html', {'category': category})


# --- Продукты ---
def product_list(request):
    products = Product.objects.select_related('category').all()
    return render(request, 'catalog/product_list.html', {'products': products})


def product_create(request):
    return handle_form(request, ProductForm, 'catalog/product_form.html', 'product_list', title='Продукт')


def product_update(request, pk):
    return handle_form(request, ProductForm, 'catalog/product_form.html', 'product_list',
                       instance=get_object_or_404(Product, pk=pk), title='Продукт')


def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Продукт удалён!')
        return redirect('product_list')
    return render(request, 'catalog/product_confirm_delete.html', {'product': product})


# --- Партии ---
def batch_list(request):
    batches = ProductBatch.objects.select_related('product__category', 'store').order_by('expiration_date')
    return render(request, 'catalog/batch_list.html', {'batches': batches})


def batch_create(request):
    return handle_form(request, ProductBatchForm, 'catalog/batch_form.html', 'batch_list', title='Партия')


def batch_update(request, pk):
    return handle_form(request, ProductBatchForm, 'catalog/batch_form.html', 'batch_list',
                       instance=get_object_or_404(ProductBatch, pk=pk), title='Партия')


def batch_delete(request, pk):
    batch = get_object_or_404(ProductBatch, pk=pk)
    if request.method == 'POST':
        batch.delete()
        messages.success(request, 'Партия удалена!')
        return redirect('batch_list')
    return render(request, 'catalog/batch_confirm_delete.html', {'batch': batch})


# --- Отчёт по срокам ---
def expiring_report(request):
    expired = ProductBatch.objects.expired()
    expiring_soon = ProductBatch.objects.expiring_soon()
    good = ProductBatch.objects.filter(is_available=True).exclude(pk__in=expired | expiring_soon)

    return render(request, 'catalog/expiring_report.html', {
        'expired': expired,
        'expiring_soon': expiring_soon,
        'good': good,
    })