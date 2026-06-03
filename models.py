from django.db import models


class Article(models.Model):
    SECTION_CHOICES = [
        ('top',           'Top Stories'),
        ('world',         'World'),
        ('uk',            'UK'),
        ('technology',    'Technology'),
        ('science',       'Science'),
        ('business',      'Business'),
        ('health',        'Health'),
        ('sport',         'Sport'),
        ('india',         'India'),
        ('entertainment', 'Entertainment'),
        ('other',         'Other'),
    ]

    url            = models.URLField(unique=True, max_length=500)
    headline       = models.CharField(max_length=500)
    description    = models.TextField(blank=True)
    author         = models.CharField(max_length=200, blank=True)
    published_date = models.CharField(max_length=100, blank=True)   # keep as string from RSS
    section        = models.CharField(max_length=50, choices=SECTION_CHOICES, default='other')
    body_text      = models.TextField()
    word_count     = models.PositiveIntegerField(default=0)
    images         = models.JSONField(default=list, blank=True)     # list of image URLs
    tags           = models.JSONField(default=list, blank=True)     # list of tag strings
    scraped_at     = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Article'
        verbose_name_plural = 'Articles'

    def __str__(self):
        return self.headline[:80]
