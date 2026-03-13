from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .forms import StoreForm, ProductCategoryForm, ProductForm, ProductBatchForm, StockForm, StockMovementForm, \
    GiftForm, GiftAddStockItemForm, GiftAddExtraItemForm, GiftCreateForStoreForm, GiftSellForm
from .models import ProductCategory, Product, ProductBatch, Store, Stock, StockMovement, apply_stock_movement, Gift, \
    GiftItem


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


def stock_move(request, stock_id, action):
    stock = get_object_or_404(
        Stock.objects.select_related("store", "batch__product"),
        pk=stock_id
    )

    action_map = {
        "in": (StockMovement.REASON_IN, +1, "Корректировка ➕"),
        "out": (StockMovement.REASON_OUT, -1, "Корректировка ➖"),
    }

    if action not in action_map:
        return redirect("store_detail", pk=stock.store_id)

    reason, sign, title = action_map[action]

    if request.method == "POST":
        form = StockMovementForm(request.POST)
        if form.is_valid():
            qty = form.cleaned_data["quantity"]
            comment = form.cleaned_data["comment"]
            delta = sign * qty
            try:
                apply_stock_movement(
                    stock=stock,
                    delta=delta,
                    reason=reason,
                    user=request.user,
                    comment=comment,
                )
                messages.success(request, f"{title}: выполнено")
                return redirect("store_detail", pk=stock.store_id)
            except ValidationError as e:
                form.add_error(None, e.message)
    else:
        form = StockMovementForm()

    return render(request, "catalog/stock_move_form.html", {
        "form": form,
        "stock": stock,
        "title": title,
    })


@login_required
def gift_list(request):
    gifts = Gift.objects.select_related("store", "created_by", "sold_by").all()
    return render(request, "catalog/gift_list.html", {"gifts": gifts})


@login_required
def gift_create(request):
    if request.method == "POST":
        form = GiftForm(request.POST)
        if form.is_valid():
            gift = form.save(commit=False)
            gift.created_by = request.user
            gift.save()
            messages.success(request, "Подарок создан")
            return redirect("gift_detail", pk=gift.pk)
    else:
        form = GiftForm()
    return render(request, "catalog/gift_form.html", {"form": form, "title": "Новый подарок"})


@login_required
def gift_detail(request, pk):
    gift = get_object_or_404(
        Gift.objects.select_related("store", "created_by", "sold_by"),
        pk=pk,
    )
    items = gift.items.select_related("stock__batch__product__category", "stock__store").all()
    editable = gift.status not in (Gift.STATUS_SOLD, Gift.STATUS_CANCELED)

    profit = None
    if gift.sale_price is not None:
        profit = gift.sale_price - gift.calculated_total

    return render(request, "catalog/gift_detail.html", {
        "gift": gift,
        "items": items,
        "editable": editable,
        "profit": profit,
        "stock_form": GiftAddStockItemForm(store=gift.store),
        "extra_form": GiftAddExtraItemForm(),
    })


def ensure_gift_editable(request, gift):
    if gift.status in (Gift.STATUS_SOLD, Gift.STATUS_CANCELED):
        messages.error(request, "Нельзя изменять проданный или отменённый подарок.")
        return False
    return True


@login_required
def gift_add_stock_item(request, pk):
    gift = get_object_or_404(Gift.objects.select_related("store"), pk=pk)

    if request.method != "POST":
        return redirect("gift_detail", pk=gift.pk)

    if not ensure_gift_editable(request, gift):
        return redirect("gift_detail", pk=gift.pk)

    form = GiftAddStockItemForm(request.POST, store=gift.store)
    if not form.is_valid():
        messages.error(request, "Проверь заполнение формы добавления со склада.")
        return redirect("gift_detail", pk=gift.pk)

    stock = form.cleaned_data["stock"]
    qty = form.cleaned_data["quantity"]
    note = form.cleaned_data["note"]

    if stock.store_id != gift.store_id:
        messages.error(request, "Нельзя добавлять остаток из другого магазина.")
        return redirect("gift_detail", pk=gift.pk)

    try:
        with transaction.atomic():
            apply_stock_movement(
                stock=stock,
                delta=-qty,
                reason=StockMovement.REASON_RESERVE_GIFT,
                user=request.user,
                comment=f"Подарок #{gift.pk}. {note}".strip(),
            )

            product = stock.batch.product
            batch_price = stock.batch.price
            if product.unit == "g":
                line_total = (Decimal(qty) / Decimal("1000")) * batch_price
            else:
                line_total = Decimal(qty) * batch_price

            GiftItem.objects.create(
                gift=gift,
                stock=stock,
                quantity=qty,
                note=note,
                unit_price=batch_price,
                line_total=line_total.quantize(Decimal("0.01")),
            )
        messages.success(request, "Позиция со склада добавлена в подарок.")
    except ValidationError as e:
        messages.error(request, e.message)

    return redirect("gift_detail", pk=gift.pk)


@login_required
def gift_add_extra_item(request, pk):
    gift = get_object_or_404(Gift, pk=pk)

    if request.method != "POST":
        return redirect("gift_detail", pk=gift.pk)

    if not ensure_gift_editable(request, gift):
        return redirect("gift_detail", pk=gift.pk)

    form = GiftAddExtraItemForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Проверь заполнение формы дополнительной позиции.")
        return redirect("gift_detail", pk=gift.pk)

    qty = form.cleaned_data["quantity"]
    unit_price = form.cleaned_data["unit_price"]
    line_total = (Decimal(qty) * unit_price).quantize(Decimal("0.01"))

    GiftItem.objects.create(
        gift=gift,
        extra_name=form.cleaned_data["extra_name"],
        quantity=qty,
        note=form.cleaned_data["note"],
        unit_price=unit_price,
        line_total=line_total,
    )
    messages.success(request, "Дополнительная позиция добавлена.")
    return redirect("gift_detail", pk=gift.pk)


@login_required
def gift_remove_item(request, pk, item_id):
    gift = get_object_or_404(Gift, pk=pk)
    item = get_object_or_404(GiftItem.objects.select_related("stock"), pk=item_id, gift=gift)

    if request.method != "POST":
        return redirect("gift_detail", pk=gift.pk)

    if not ensure_gift_editable(request, gift):
        return redirect("gift_detail", pk=gift.pk)

    try:
        with transaction.atomic():
            if item.stock_id:
                apply_stock_movement(
                    stock=item.stock,
                    delta=+item.quantity,
                    reason=StockMovement.REASON_RETURN_GIFT,
                    user=request.user,
                    comment=f"Удаление из подарка #{gift.pk}. {item.note}".strip(),
                )
            item.delete()
        messages.success(request, "Позиция удалена.")
    except ValidationError as e:
        messages.error(request, e.message)

    return redirect("gift_detail", pk=gift.pk)


@login_required
def gift_cancel(request, pk):
    gift = get_object_or_404(Gift, pk=pk)

    if request.method != "POST":
        return redirect("gift_detail", pk=gift.pk)

    if not ensure_gift_editable(request, gift):
        return redirect("gift_detail", pk=gift.pk)

    items = gift.items.select_related("stock").all()

    try:
        with transaction.atomic():
            for item in items:
                if item.stock_id:
                    apply_stock_movement(
                        stock=item.stock,
                        delta=+item.quantity,
                        reason=StockMovement.REASON_RETURN_GIFT,
                        user=request.user,
                        comment=f"Отмена/разбор подарка #{gift.pk}",
                    )
            gift.status = Gift.STATUS_CANCELED
            gift.save(update_fields=["status"])
        messages.success(request, "Подарок отменён, резерв возвращён.")
    except ValidationError as e:
        messages.error(request, e.message)

    return redirect("gift_detail", pk=gift.pk)


from django.contrib.auth.decorators import login_required


@login_required
def gift_create_for_store(request, store_pk):
    store = get_object_or_404(Store, pk=store_pk)

    if request.method == "POST":
        form = GiftCreateForStoreForm(request.POST)
        if form.is_valid():
            gift = form.save(commit=False)
            gift.store = store
            gift.created_by = request.user
            gift.save()
            messages.success(request, "Подарок создан")
            return redirect("gift_detail", pk=gift.pk)
    else:
        form = GiftCreateForStoreForm()

    return render(request, "catalog/gift_form.html", {
        "form": form,
        "title": f"Новый подарок — {store.name}",
        "store_locked": True,
        "store": store,
    })


@login_required
def gift_sell(request, pk):
    gift = get_object_or_404(Gift.objects.select_related("store", "created_by", "sold_by"), pk=pk)

    if gift.status == Gift.STATUS_SOLD:
        messages.error(request, "Подарок уже продан.")
        return redirect("gift_detail", pk=gift.pk)

    if gift.status == Gift.STATUS_CANCELED:
        messages.error(request, "Подарок отменён.")
        return redirect("gift_detail", pk=gift.pk)

    if not gift.items.exists():
        messages.error(request, "Нельзя продать пустой подарок.")
        return redirect("gift_detail", pk=gift.pk)

    if request.method == "POST":
        form = GiftSellForm(request.POST)
        if form.is_valid():
            gift.sale_price = form.cleaned_data["sale_price"]
            gift.sold_at = timezone.now()
            gift.sold_by = request.user
            gift.status = Gift.STATUS_SOLD
            gift.save(update_fields=["sale_price", "sold_at", "sold_by", "status"])
            messages.success(request, "Подарок продан. Изменения и возвраты запрещены.")
            return redirect("gift_detail", pk=gift.pk)
    else:
        form = GiftSellForm(initial={"sale_price": gift.calculated_total})

    cost_price = gift.calculated_total
    profit = None
    if gift.sale_price is not None:
        profit = gift.sale_price - cost_price

    return render(request, "catalog/gift_sell.html", {
        "gift": gift,
        "form": form,
        "cost_price": cost_price,
        "profit": profit,
    })
