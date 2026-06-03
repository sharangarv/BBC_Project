import json
from pathlib import Path
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError
from news.models import Article


class Command(BaseCommand):
    help = 'Import BBC articles from a JSON file into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='clean_articles.json',
            help='Path to the JSON file (default: clean_articles.json)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing articles before importing',
        )

    def handle(self, *args, **options):
        filepath = Path(options['file'])

        if not filepath.exists():
            raise CommandError(f"File not found: {filepath.resolve()}")

        if options['clear']:
            count = Article.objects.count()
            Article.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Cleared {count} existing articles.'))

        # Load JSON with utf-8 encoding (fixes Windows cp1252 error)
        with open(filepath, encoding='utf-8') as f:
            articles = json.load(f)

        self.stdout.write(f"\nImporting {len(articles)} articles from {filepath}...\n")

        created_count = 0
        skipped_count = 0
        error_count   = 0

        for i, data in enumerate(articles, 1):
            url = (data.get('url') or '').strip()
            if not url:
                error_count += 1
                continue

            # Parse scraped_at datetime
            scraped_at = None
            raw_scraped = data.get('scraped_at', '')
            if raw_scraped:
                try:
                    scraped_at = datetime.fromisoformat(raw_scraped.replace('Z', '+00:00'))
                except ValueError:
                    pass

            try:
                obj, created = Article.objects.update_or_create(
                    url=url,
                    defaults={
                        'headline':       (data.get('headline')       or '')[:500],
                        'description':    (data.get('description')    or ''),
                        'author':         (data.get('author')         or '')[:200],
                        'published_date': (data.get('published_date') or '')[:100],
                        'section':        (data.get('section')        or 'other')[:50],
                        'body_text':       data.get('body_text')      or '',
                        'word_count':      data.get('word_count')     or len((data.get('body_text') or '').split()),
                        'images':          data.get('images')         or [],
                        'tags':            data.get('tags')           or [],
                        'scraped_at':      scraped_at,
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(f"  [NEW]  {obj.headline[:65]}")
                else:
                    skipped_count += 1
                    self.stdout.write(f"  [UPD]  {obj.headline[:65]}")

            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"  [ERR]  {url[:60]} → {e}"))

        # Summary
        self.stdout.write("\n" + "="*55)
        self.stdout.write(self.style.SUCCESS(f"  ✅  Created : {created_count}"))
        self.stdout.write(                   f"  🔄  Updated : {skipped_count}")
        self.stdout.write(self.style.ERROR(  f"  ❌  Errors  : {error_count}") if error_count else f"  ❌  Errors  : 0")
        self.stdout.write(                   f"  📦  Total in DB : {Article.objects.count()}")
        self.stdout.write("="*55 + "\n")
