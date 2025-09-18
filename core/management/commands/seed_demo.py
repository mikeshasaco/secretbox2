from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from services.nfl import refresh_week_cache


class Command(BaseCommand):
    help = 'Create demo user and prefetch latest completed 2025 week'

    def handle(self, *args, **options):
        # Create demo user if it doesn't exist
        username = 'demo'
        email = 'demo@secretbox.com'
        password = 'demo123'
        
        if not User.objects.filter(username=username).exists():
            User.objects.create_user(username=username, email=email, password=password)
            self.stdout.write(f'Created demo user: {username}/{password}')
        else:
            self.stdout.write(f'Demo user already exists: {username}')
        
        # Prefetch week 1 data
        self.stdout.write('Prefetching week 1 data...')
        refresh_week_cache(1)
        self.stdout.write(self.style.SUCCESS('Demo data ready!'))
