from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .forms import StoreForm, ProductCategoryForm, ProductForm, ProductBatchForm, StockForm
from .models import ProductCategory, Product, ProductBatch, Store, Stock
from django.forms import inlineformset_factory


from django import forms

# --- Главная страница ---
def home(request):
    today = timezone.now().date()
    soon7 = today + timedelta(days=settings.EXPIRING_SOON_DAYS)
    soon30 = today + timedelta(days=settings.EXPIRING_WARNING_DAYS)

    stores = (
        Store.objects
        .annotate(
            expired_count=Count(
                "stocks",
                filter=Q(
                    stocks__quantity__gt=0,
                    stocks__batch__expiration_date__lt=today
                ),
            ),
            expiring7_count=Count(
                "stocks",
                filter=Q(
                    stocks__quantity__gt=0,
                    stocks__batch__expiration_date__gte=today,
                    stocks__batch__expiration_date__lte=soon7
                ),
            ),
            expiring30_count=Count(
                "stocks",
                filter=Q(
                    stocks__quantity__gt=0,
                    stocks__batch__expiration_date__gt=soon7,
                    stocks__batch__expiration_date__lte=soon30
                ),
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

    stocks = (
        Stock.objects
        .select_related('batch__product__category')
        .filter(store=store, quantity__gt=0)
        .order_by('batch__expiration_date')
    )

    return render(request, 'catalog/store_detail.html', {
        'store': store,
        'stocks': stocks,
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
    stocks = (
        Stock.objects
        .select_related('store', 'batch__product__category')
        .filter(quantity__gt=0)
        .order_by('batch__expiration_date')
    )
    return render(request, 'catalog/batch_list.html', {'stocks': stocks})


def batch_create(request):
    if request.method == 'POST':
        batch_form = ProductBatchForm(request.POST)
        stock_form = StockForm(request.POST)

        if batch_form.is_valid() and stock_form.is_valid():
            batch = batch_form.save()

            stock = stock_form.save(commit=False)
            stock.batch = batch
            stock.save()

            messages.success(request, "Партия успешно создана")
            return redirect('batch_list')
    else:
        batch_form = ProductBatchForm()
        stock_form = StockForm()

    return render(request, 'catalog/batch_form.html', {
        'batch_form': batch_form,
        'stock_form': stock_form,
        'title': 'Партия'
    })

def batch_update(request, pk):
    batch = get_object_or_404(ProductBatch, pk=pk)

    # Берём существующий Stock этой партии (если есть).
    # Если у партии может быть несколько stocks, это временное упрощение:
    # редактируем первый. Позже сделаем formset аккуратно.
    stock = Stock.objects.filter(batch=batch).first()

    if request.method == 'POST':
        batch_form = ProductBatchForm(request.POST, instance=batch)
        stock_form = StockForm(request.POST, instance=stock)

        if batch_form.is_valid() and stock_form.is_valid():
            batch = batch_form.save()
            stock = stock_form.save(commit=False)
            stock.batch = batch
            stock.save()

            messages.success(request, "Партия обновлена")
            return redirect('batch_list')
    else:
        batch_form = ProductBatchForm(instance=batch)
        stock_form = StockForm(instance=stock)

    return render(request, 'catalog/batch_form.html', {
        'batch_form': batch_form,
        'stock_form': stock_form,
        'title': 'Партия',
        'is_edit': True,
        'batch': batch,
    })


def batch_delete(request, pk):
    batch = get_object_or_404(ProductBatch, pk=pk)
    if request.method == 'POST':
        batch.delete()
        messages.success(request, 'Партия удалена!')
        return redirect('batch_list')
    return render(request, 'catalog/batch_confirm_delete.html', {'batch': batch})


# --- Отчёт по срокам ---
def expiring_report(request):
    today = timezone.now().date()
    soon = today + timedelta(days=settings.EXPIRING_WARNING_DAYS)

    base = (
        Stock.objects
        .select_related('store', 'batch__product__category')
        .filter(quantity__gt=0, batch__is_available=True)
    )

    expired = base.filter(batch__expiration_date__lt=today).order_by('batch__expiration_date')
    expiring = base.filter(
        batch__expiration_date__gte=today,
        batch__expiration_date__lte=soon
    ).order_by('batch__expiration_date')

    return render(request, 'catalog/expiring_report.html', {
        'expired': expired,
        'expiring': expiring,
        'soon': soon,
    })