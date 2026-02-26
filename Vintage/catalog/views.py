from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Prefetch
from .models import Store, ProductCategory, Product, ProductBatch
from .forms import StoreForm, ProductCategoryForm, ProductForm, ProductBatchForm


# --- Главная страница ---
def home(request):
    """Главная страница - краткий дашборд по магазинам"""
    stores = Store.objects.prefetch_related(
        Prefetch('batches', queryset=ProductBatch.objects.filter(is_available=True))
    )

    store_statuses = []
    for store in stores:
        batches = store.batches.all()
        expired = [b for b in batches if b.is_expired]
        expiring = [b for b in batches if b.is_expiring_soon]

        if expired:
            status = ('❌ ПРОСРОЧКА', 'bg-danger text-white', len(expired))
        elif expiring:
            status = ('⚠️ СКОРО', 'bg-warning', len(expiring))
        else:
            status = ('✅ ВСЁ ОК', 'bg-success text-white', 0)

        store_statuses.append({
            'store': store,
            'status_text': status[0],
            'status_class': status[1],
            'expired_count': len(expired),
            'expiring_count': len(expiring),
        })

    return render(request, 'catalog/home.html', {'store_statuses': store_statuses})


# --- Универсальные CRUD-хелперы ---
def handle_form(request, form_class, template, redirect_name, instance=None, title=''):
    form = form_class(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{title} успешно сохранено!')
        return redirect(redirect_name)
    return render(request, template, {'form': form, 'title': title})


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