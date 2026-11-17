"""News Pipeline - News ingestion, processing, and distribution pipeline."""

from .news import (
    NewsArticle, NewsCategory, NewsSource, NewsSentiment,
    NewsFilter, NewsIngestionPipeline, NLPProcessor,
    AlertManager, RSSFeedProvider, NewsAPIProvider,
    TwitterNewsProvider, RedditNewsProvider,
    NewsAggregator, create_news_pipeline,
    create_nlp_processor, create_alert_manager,
    create_rss_provider, create_news_aggregator
)

# Re-export with expected name
NewsPipeline = NewsIngestionPipeline

__all__ = [
    'NewsArticle',
    'NewsCategory',
    'NewsSource',
    'NewsSentiment',
    'NewsFilter',
    'NewsIngestionPipeline',
    'NewsPipeline',
    'NLPProcessor',
    'AlertManager',
    'RSSFeedProvider',
    'NewsAPIProvider',
    'TwitterNewsProvider',
    'RedditNewsProvider',
    'NewsAggregator',
    'create_news_pipeline',
    'create_nlp_processor',
    'create_alert_manager',
    'create_rss_provider',
    'create_news_aggregator',
]