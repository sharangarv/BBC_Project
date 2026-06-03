from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Article


def article_list(request):
    """Homepage — paginated list with search + section filter."""
    query   = request.GET.get('q', '')
    section = request.GET.get('section', '')

    articles = Article.objects.all()

    if query:
        articles = articles.filter(
            Q(headline__icontains=query) |
            Q(body_text__icontains=query) |
            Q(author__icontains=query)
        )
    if section:
        articles = articles.filter(section=section)

    paginator = Paginator(articles, 20)
    page      = paginator.get_page(request.GET.get('page'))

    sections = Article.objects.values_list('section', flat=True).distinct().order_by('section')

    return render(request, 'news/article_list.html', {
        'page_obj':       page,
        'query':          query,
        'section':        section,
        'sections':       sections,
        'total':          Article.objects.count(),
    })


def article_detail(request, pk):
    """Full article detail page."""
    article = get_object_or_404(Article, pk=pk)
    return render(request, 'news/article_detail.html', {'article': article})