from django.contrib import admin
from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display  = ('headline', 'section', 'author', 'word_count', 'published_date', 'created_at')
    list_filter   = ('section',)
    search_fields = ('headline', 'author', 'body_text')
    readonly_fields = ('created_at', 'scraped_at', 'word_count', 'url')
    ordering      = ('-created_at',)

    fieldsets = (
        ('Content', {
            'fields': ('headline', 'description', 'body_text')
        }),
        ('Metadata', {
            'fields': ('url', 'author', 'section', 'published_date', 'tags', 'images', 'word_count')
        }),
        ('Timestamps', {
            'fields': ('scraped_at', 'created_at'),
            'classes': ('collapse',),
        }),
    )