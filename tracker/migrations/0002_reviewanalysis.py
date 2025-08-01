# Generated by Django 5.1.7 on 2025-06-08 04:39

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReviewAnalysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('summary', models.TextField(blank=True, null=True)),
                ('pros', models.TextField(blank=True, null=True)),
                ('cons', models.TextField(blank=True, null=True)),
                ('analyzed_at', models.DateTimeField(auto_now_add=True)),
                ('url', models.ForeignKey(db_column='url', on_delete=django.db.models.deletion.CASCADE, to='tracker.scrapedproduct', to_field='url')),
            ],
            options={
                'ordering': ['-analyzed_at'],
                'indexes': [models.Index(fields=['url'], name='tracker_rev_url_72fef1_idx'), models.Index(fields=['analyzed_at'], name='tracker_rev_analyze_690bc3_idx')],
            },
        ),
    ]
