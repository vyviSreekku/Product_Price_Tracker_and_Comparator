from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Lists all tables in the PostgreSQL database'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = cursor.fetchall()
            
            self.stdout.write(self.style.SUCCESS('Found {} tables in the database:'.format(len(tables))))
            for table in tables:
                self.stdout.write('  - {}'.format(table[0]))
                
            # Show table content counts
            self.stdout.write('\nTable row counts:')
            for table in tables:
                cursor.execute('SELECT COUNT(*) FROM {}'.format(table[0]))
                count = cursor.fetchone()[0]
                self.stdout.write('  - {}: {} rows'.format(table[0], count)) 