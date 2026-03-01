from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),

    # Магазины
    path('stores/', views.store_list, name='store_list'),
    path('stores/<int:pk>/', views.store_detail, name='store_detail'),
    path('stores/add/', views.store_create, name='store_create'),
    path('stores/<int:pk>/edit/', views.store_update, name='store_update'),
    path('stores/<int:pk>/delete/', views.store_delete, name='store_delete'),

    # Категории
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    # Продукты
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_update, name='product_update'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),

    # Партии
    path('batches/', views.batch_list, name='batch_list'),
    path('batches/add/', views.batch_create, name='batch_create'),
    path('batches/<int:pk>/edit/', views.batch_update, name='batch_update'),
    path('batches/<int:pk>/delete/', views.batch_delete, name='batch_delete'),

    # Отчёт
    path('report/', views.expiring_report, name='expiring_report'),

    # Движения товаров
    path("stocks/<int:stock_id>/<str:action>/", views.stock_move, name="stock_move"),

]
