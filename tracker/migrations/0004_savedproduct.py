# Generated by Django 5.1.7 on 2025-06-09 18:08

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0003_remove_reviewanalysis_tracker_rev_url_72fef1_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_name', models.CharField(max_length=255)),
                ('image_url', models.URLField()),
                ('product_url', models.URLField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('store_name', models.CharField(max_length=100)),
                ('saved_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'product_url')},
            },
        ),
    ]
