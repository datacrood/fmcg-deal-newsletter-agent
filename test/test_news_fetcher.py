import news_fetcher
from news_fetcher import fetch_from_newsapi


def test_newsapi_returns_empty_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("NEWS_API_KEY", raising=False)

    query = "FMCG"
    days_back = 14

    result = fetch_from_newsapi(query=query, days_back=days_back)

    assert result == []

def test_trafilatura_extract_full_text(monkeypatch):
    def fake_fetch_url(url):
        assert url == "https://example.com/article"
        return "<html>mock page</html>"

    def fake_extract(downloaded, include_comments=False):
        assert downloaded == "<html>mock page</html>"
        assert include_comments is False
        return "Full extracted text"

    monkeypatch.setattr(news_fetcher.trafilatura, "fetch_url", fake_fetch_url)
    monkeypatch.setattr(news_fetcher.trafilatura, "extract", fake_extract)

    result = news_fetcher._extract_full_text("https://rss.app/feed/Ge28VeNrwvgSCZvl")

    assert result == "Full extracted text"



