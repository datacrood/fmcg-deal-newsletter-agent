"""HTML newsletter renderer for the FMCG Deal newsletter."""

import html
from datetime import datetime

from config import OUTPUT_DIR

_DEAL_EMOJI = {
    "acquisition": "🏷️",
    "merger": "🤝",
    "jv": "🤝",
    "investment": "💰",
    "divestiture": "✂️",
    "ipo": "🔔",
    "partnership": "🤝",
    "other": "📌",
}

_STATUS_EMOJI = {
    "completed": "✅",
    "announced": "📢",
    "rumored": "🔮",
    "in-progress": "⏳",
}

_BADGE_COLORS = {
    "acquisition": "#e74c3c",
    "merger": "#3498db",
    "jv": "#2ecc71",
    "investment": "#f39c12",
    "divestiture": "#9b59b6",
    "ipo": "#1abc9c",
    "partnership": "#2ecc71",
    "other": "#95a5a6",
}

_STATUS_COLORS = {
    "completed": "#27ae60",
    "announced": "#2980b9",
    "rumored": "#8e44ad",
    "in-progress": "#e67e22",
}


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


def _has_structured_fields(deal: dict) -> bool:
    return deal.get("deal_type") is not None


def _badge(text: str, color: str) -> str:
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;'
        f'background:{color};color:#fff;font-size:12px;font-weight:600;">'
        f'{_esc(text)}</span>'
    )


def _render_tldr(summary_text: str) -> str:
    bullets = []
    for line in summary_text.strip().splitlines():
        line = line.strip().lstrip("- ").strip()
        if line:
            bullets.append(f"<li>{_esc(line)}</li>")
    bullet_html = "\n".join(bullets)
    return f"""
    <div style="background:#fffbea;border-left:4px solid #f39c12;padding:20px;border-radius:8px;margin-bottom:32px;">
      <h2 style="margin-top:0;color:#e67e22;">⚡ TL;DR</h2>
      <ul style="margin:0;padding-left:20px;line-height:1.8;">{bullet_html}</ul>
    </div>"""


def _render_deal_of_week(headline_text: str, deals: list) -> str:
    meta_html = ""
    if deals:
        top = deals[0]
        if _has_structured_fields(top):
            deal_type = top.get("deal_type", "other")
            badge_color = _BADGE_COLORS.get(deal_type, "#95a5a6")
            status = top.get("deal_status", "announced")
            status_color = _STATUS_COLORS.get(status, "#95a5a6")
            meta_html = f"""
            <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
              {_badge(deal_type.upper(), badge_color)}
              {_badge(top.get('deal_value_structured') or 'Undisclosed', '#34495e')}
              {_badge(top.get('sector') or 'FMCG', '#16a085')}
              {_badge(status, status_color)}
            </div>"""

    # Convert markdown-ish paragraphs to HTML
    paras = []
    for p in headline_text.split("\n\n"):
        p = p.strip()
        if p:
            paras.append(f"<p style='margin:8px 0;line-height:1.6;'>{_esc(p)}</p>")
    body = "\n".join(paras)

    return f"""
    <div style="background:#f8f9fa;border-radius:12px;padding:24px;margin-bottom:32px;border:1px solid #e9ecef;">
      <h2 style="margin-top:0;color:#1a1a2e;">🎯 Deal of the Week</h2>
      {meta_html}
      {body}
    </div>"""


def _render_deal_briefs(deals: list) -> str:
    briefs = deals[1:6]
    if not briefs:
        return ""

    cards = []
    for d in briefs:
        if _has_structured_fields(d):
            deal_type = d.get("deal_type", "other")
            badge_color = _BADGE_COLORS.get(deal_type, "#95a5a6")
            acquirer = _esc(d.get("acquirer") or "Undisclosed")
            target = _esc(d.get("target") or "Undisclosed")
            value = _esc(d.get("deal_value_structured") or "Undisclosed")
            sector = _esc(d.get("sector") or "FMCG")
            insight = _esc(d.get("key_insight") or d.get("title", ""))
            emoji = _DEAL_EMOJI.get(deal_type, "📌")

            cards.append(f"""
            <div style="background:#fff;border:1px solid #e9ecef;border-radius:8px;padding:16px;margin-bottom:12px;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <strong>{emoji} {acquirer} → {target}</strong>
                {_badge(deal_type, badge_color)}
              </div>
              <div style="color:#666;font-size:14px;">{value} · {sector}</div>
              <p style="margin:8px 0 0;color:#444;font-size:14px;">{insight}</p>
            </div>""")
        else:
            title = _esc(d.get("title", "Untitled"))
            source = _esc(d.get("source", "Unknown"))
            cards.append(f"""
            <div style="background:#fff;border:1px solid #e9ecef;border-radius:8px;padding:16px;margin-bottom:12px;">
              <strong>📌 {title}</strong>
              <div style="color:#888;font-size:13px;">Source: {source}</div>
            </div>""")

    return f"""
    <div style="margin-bottom:32px;">
      <h2 style="color:#1a1a2e;">📋 Deal Briefs</h2>
      {"".join(cards)}
    </div>"""


def _render_sector_pulse(pulse_text: str, deals: list) -> str:
    from collections import Counter
    structured = [d for d in deals if _has_structured_fields(d)]
    sectors = Counter(d.get("sector", "FMCG") for d in structured)
    types = Counter(d.get("deal_type", "other") for d in structured)

    top_sector = sectors.most_common(1)[0][0] if sectors else "N/A"
    top_type = types.most_common(1)[0][0] if types else "N/A"

    stats_html = f"""
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;">
      <div style="flex:1;min-width:120px;background:#eaf2f8;border-radius:8px;padding:16px;text-align:center;">
        <div style="font-size:28px;font-weight:700;color:#2980b9;">{len(deals)}</div>
        <div style="font-size:13px;color:#666;">Total Deals</div>
      </div>
      <div style="flex:1;min-width:120px;background:#eafaf1;border-radius:8px;padding:16px;text-align:center;">
        <div style="font-size:16px;font-weight:700;color:#27ae60;">{_esc(top_sector)}</div>
        <div style="font-size:13px;color:#666;">Hottest Sector</div>
      </div>
      <div style="flex:1;min-width:120px;background:#fef9e7;border-radius:8px;padding:16px;text-align:center;">
        <div style="font-size:16px;font-weight:700;color:#e67e22;">{_esc(top_type)}</div>
        <div style="font-size:13px;color:#666;">Top Deal Type</div>
      </div>
    </div>"""

    paras = []
    for p in pulse_text.split("\n\n"):
        p = p.strip()
        if p:
            paras.append(f"<p style='margin:8px 0;line-height:1.6;color:#444;'>{_esc(p)}</p>")

    return f"""
    <div style="margin-bottom:32px;">
      <h2 style="color:#1a1a2e;">📊 Sector Pulse</h2>
      {stats_html}
      {"".join(paras)}
    </div>"""


def _render_watchlist(watchlist_text: str, deals: list) -> str:
    watch = [d for d in deals if d.get("deal_status") in ("rumored", "in-progress")]

    if not watch:
        return f"""
        <div style="margin-bottom:32px;">
          <h2 style="color:#1a1a2e;">👁️ Watchlist</h2>
          <p style="color:#888;">No early-stage deals or rumors on the radar this week.</p>
        </div>"""

    items = []
    for d in watch:
        status = d.get("deal_status", "rumored")
        status_color = _STATUS_COLORS.get(status, "#95a5a6")
        emoji = _STATUS_EMOJI.get(status, "👁️")

        if _has_structured_fields(d):
            label = f"{_esc(d.get('acquirer', '?'))} + {_esc(d.get('target', '?'))}"
            detail = f"{_esc(d.get('deal_value_structured') or 'Undisclosed')} {_esc(d.get('deal_type', 'deal'))}"
        else:
            label = _esc(d.get("title", "Untitled"))
            detail = f"Source: {_esc(d.get('source', 'Unknown'))}"

        items.append(f"""
        <div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #eee;">
          <span>{emoji}</span>
          <div style="flex:1;">
            <strong>{label}</strong>
            <span style="color:#888;font-size:13px;margin-left:8px;">{detail}</span>
          </div>
          {_badge(status, status_color)}
        </div>""")

    return f"""
    <div style="margin-bottom:32px;">
      <h2 style="color:#1a1a2e;">👁️ Watchlist</h2>
      {"".join(items)}
    </div>"""


def render_html(sections: dict, deals: list, run_date: str) -> str:
    """Render the newsletter as a complete HTML document.

    Returns the HTML string.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    tldr = _render_tldr(sections.get("executive_summary", ""))
    deal_of_week = _render_deal_of_week(sections.get("headline_deal", ""), deals)
    briefs = _render_deal_briefs(deals)
    pulse = _render_sector_pulse(sections.get("sector_pulse", ""), deals)
    watchlist = _render_watchlist(sections.get("watchlist", ""), deals)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FMCG Deal Pulse — Week of {_esc(run_date)}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #333; }}
    .container {{ max-width: 720px; margin: 0 auto; padding: 20px; }}
  </style>
</head>
<body>
  <!-- Header -->
  <div style="background:linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);padding:40px 20px;text-align:center;">
    <div style="max-width:720px;margin:0 auto;">
      <h1 style="color:#fff;font-size:32px;margin-bottom:8px;">🏪 FMCG Deal Pulse</h1>
      <p style="color:#a8b2d1;font-size:16px;">Week of {_esc(run_date)}</p>
    </div>
  </div>

  <div class="container">
    {tldr}
    {deal_of_week}
    {briefs}
    {pulse}
    {watchlist}

    <!-- Footer -->
    <div style="text-align:center;padding:24px;color:#999;font-size:13px;border-top:1px solid #e9ecef;margin-top:24px;">
      Generated by FMCG Deal Intelligence Pipeline — {timestamp}
    </div>
  </div>
</body>
</html>"""
