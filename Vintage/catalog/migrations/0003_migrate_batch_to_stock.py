from django.db import migrations

def forward_func(apps, schema_editor):
    ProductBatch = apps.get_model('catalog', 'ProductBatch')
    Stock = apps.get_model('catalog', 'Stock')

    for batch in ProductBatch.objects.all():
        if batch.store_id and batch.quantity:
            Stock.objects.create(
                batch=batch,
                store_id=batch.store_id,
                quantity=batch.quantity
            )

class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_alter_productbatch_quantity_stock'),
    ]

    operations = [
        migrations.RunPython(forward_func),
    ]