# Generated by Django 5.2 on 2025-04-10 11:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('donation_app', '0004_donation_verification_date_donation_verified_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='donation',
            name='is_amount_modified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='donation',
            name='original_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
