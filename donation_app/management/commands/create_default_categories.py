from django.core.management.base import BaseCommand
from donation_app.models import DonationCategory

class Command(BaseCommand):
    help = 'Creates default donation categories'

    def handle(self, *args, **kwargs):
        categories = [
            {
                'name': 'Food for Life',
                'description': 'Support our program to provide nutritious meals to those in need.'
            },
            {
                'name': 'Prasadam Donation',
                'description': 'Contribute to preparing and distributing sanctified food to devotees and visitors.'
            },
            {
                'name': 'Sudama Seva',
                'description': 'Support temple construction and maintenance activities.'
            },
            {
                'name': 'Ekadashi Donation',
                'description': 'Special donations on Ekadashi days for spiritual benefit.'
            },
            {
                'name': 'Shravan Kumar Seva',
                'description': 'Support activities for elderly care and assistance.'
            },
            {
                'name': 'Bhagavad Gita',
                'description': 'Help distribute spiritual literature to spread knowledge and wisdom.'
            },
        ]

        for category_data in categories:
            category, created = DonationCategory.objects.get_or_create(
                name=category_data['name'],
                defaults={'description': category_data['description']}
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created category: {category.name}'))
            else:
                self.stdout.write(f'Category already exists: {category.name}') 