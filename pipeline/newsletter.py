"""Newsletter generation node: structured data → Substack-style FMCG deal newsletter."""

import os
from collections import Counter
from datetime import datetime

from config import MODEL, OPENROUTER_BASE_URL, OUTPUT_DIR

# Emoji mapping for deal types
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_llm():
    import os
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=MODEL,
        temperature=0.3,
        max_tokens=1500,
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base=OPENROUTER_BASE_URL,
    )


def _llm_generate(llm, prompt: str) -> str:
    """Call LLM and return content string. Returns empty string on failure."""
    try:
        return llm.invoke(prompt).content
    except Exception as e:
        print(f"    [newsletter] LLM generation failed: {e}")
        return ""


def _format_deal_oneliner(deal: dict) -> str:
    """Format a deal as a structured one-liner for prompts."""
    return (
        f"- {deal.get('acquirer') or '?'} → {deal.get('target') or '?'} "
        f"({deal.get('deal_type', '?')}, {deal.get('deal_value_structured') or 'Undisclosed'}, "
        f"{deal.get('sector') or 'FMCG'}) "
        f"[{deal.get('deal_status', '?')}] "
        f"Story angle: {deal.get('story_angle', 'N/A')}"
    )


def _has_structured_fields(deal: dict) -> bool:
    """Check whether a deal has LLM-extracted structured data."""
    return deal.get("deal_type") is not None


# ---------------------------------------------------------------------------
# Section generators
# ---------------------------------------------------------------------------

def _headline_deal(deals: list[dict], llm=None) -> str:
    """Section: deep-dive on the #1 ranked deal."""
    if not deals:
        return "_No deals to report this period._"

    top = deals[0]

    if llm and _has_structured_fields(top):
        prompt = f"""Write the headline section of a weekly FMCG deal newsletter.

Write a 3-paragraph analysis following this structure:

🎯 **WHAT:** Open with the story angle as a hook, then cover the deal facts — who, what, how much, which sector.
💡 **WHY IT MATTERS:** Strategic rationale. What does this mean for the acquirer, the target, and the broader FMCG landscape?
🔮 **WHAT TO WATCH:** Implications, who wins/loses, what happens next.

DEAL DATA:
- Acquirer: {top.get('acquirer', 'Unknown')}
- Target: {top.get('target', 'Unknown')}
- Deal type: {top.get('deal_type', 'Unknown')}
- Value: {top.get('deal_value_structured', 'Undisclosed')}
- Status: {top.get('deal_status', 'announced')}
- Sector: {top.get('sector', 'FMCG')}
- Story angle: {top.get('story_angle', 'N/A')}
- Why it matters: {top.get('why_it_matters', 'N/A')}
- Key insight: {top.get('key_insight', 'N/A')}
- Summary: {top.get('headline_summary', 'N/A')}

Be specific — name companies, cite values, reference the sector. Use emojis."""
        result = _llm_generate(llm, prompt)
        if result:
            return result

    # Template fallback
    if _has_structured_fields(top):
        emoji = _DEAL_EMOJI.get(top.get("deal_type", ""), "📌")
        summary = top.get("headline_summary") or top.get("key_insight") or top.get("title", "")
        return (
            f"{emoji} **{top.get('acquirer', 'The acquirer')}** is making a move on "
            f"**{top.get('target', 'the target')}** in a "
            f"{top.get('deal_value_structured', 'undisclosed')} {top.get('deal_type', 'deal')}.\n\n"
            f"> {summary}\n\n"
            f"💡 **Why it matters:** {top.get('why_it_matters', 'This transaction signals continued FMCG sector consolidation.')}\n\n"
            f"🔮 **Story angle:** {top.get('story_angle', 'Standard sector transaction.')}"
        )

    # Bare fallback (keyword-only article)
    return (
        f"📌 **{top.get('title', 'Deal of the Week')}**\n\n"
        f"Source: {top.get('source', 'N/A')} — "
        f"Score: {top.get('relevance_score', 'N/A')}"
    )


def _deal_briefs(deals: list[dict]) -> str:
    """Section: template-assembled briefs for deals #2-6. No LLM call."""
    briefs_pool = deals[1:6]  # Skip #1 (headline), take next 5
    if not briefs_pool:
        return "_No additional deals to highlight._"

    lines = []
    for d in briefs_pool:
        if _has_structured_fields(d):
            emoji = _DEAL_EMOJI.get(d.get("deal_type", ""), "📌")
            status_emoji = _STATUS_EMOJI.get(d.get("deal_status", ""), "")
            acquirer = d.get("acquirer") or "Undisclosed buyer"
            target = d.get("target") or "undisclosed target"
            deal_type = d.get("deal_type", "deal")
            value = d.get("deal_value_structured") or "Undisclosed"
            sector = d.get("sector") or "FMCG"

            line = (
                f"{emoji} **{acquirer} {deal_type}s {target}** — "
                f"{value} | {sector} {status_emoji}\n"
                f"> {d.get('key_insight', d.get('title', ''))}"
            )
        else:
            # Keyword-only fallback
            line = (
                f"📌 **{d.get('title', 'Untitled')}**\n"
                f"> {d.get('source', 'Unknown')}"
            )
        lines.append(line)

    return "\n\n".join(lines)


def _sector_pulse(deals: list[dict], llm=None) -> str:
    """Section: thematic trends across this week's deals. LLM-generated."""
    # Need at least 3 deals for meaningful trend analysis
    if len(deals) < 3:
        if deals:
            return (
                f"📊 With only {len(deals)} deal(s) this week, it's too early to call a trend — "
                f"but keep an eye on **{deals[0].get('sector', 'the FMCG space')}** "
                f"where activity is picking up."
            )
        return "_Not enough deal activity this week to identify sector trends._"

    structured_deals = [d for d in deals if _has_structured_fields(d)]

    if llm and len(structured_deals) >= 3:
        deals_summary = "\n".join(_format_deal_oneliner(d) for d in structured_deals[:10])
        prompt = f"""Write the "Sector Pulse" section of an FMCG deal newsletter.

Identify 2-3 patterns or themes from these deals. For each:
1. Name the pattern with a relevant emoji (e.g., "🚀 D2C Roll-Up Acceleration")
2. Cite specific deals as evidence (name the companies)
3. One sentence on what this means going forward

THIS WEEK'S DEALS:
{deals_summary}

Total deals: {len(deals)}

One paragraph per theme. Every claim must reference a specific deal above."""
        result = _llm_generate(llm, prompt)
        if result:
            return result

    # Template fallback — aggregate stats
    sectors = Counter(d.get("sector") or "FMCG" for d in deals if _has_structured_fields(d))
    types = Counter(d.get("deal_type") or "deal" for d in deals if _has_structured_fields(d))

    lines = [f"📊 **This week at a glance:** {len(deals)} deals tracked.\n"]
    if sectors:
        top_sector = sectors.most_common(1)[0]
        lines.append(f"🏭 **Hottest sector:** {top_sector[0]} ({top_sector[1]} deals)")
    if types:
        top_type = types.most_common(1)[0]
        lines.append(f"📈 **Most common deal type:** {top_type[0]}s ({top_type[1]})")

    return "\n\n".join(lines)


def _watchlist(deals: list[dict]) -> str:
    """Section: rumored and in-progress deals to monitor. Template only."""
    watch = [d for d in deals if d.get("deal_status") in ("rumored", "in-progress")]

    if not watch:
        return "👁️ _No early-stage deals or rumors on the radar this week._"

    lines = []
    for d in watch:
        status = d.get("deal_status", "rumored")
        emoji = _STATUS_EMOJI.get(status, "👁️")
        if _has_structured_fields(d):
            lines.append(
                f"{emoji} **{d.get('acquirer', '?')} + {d.get('target', '?')}** — "
                f"{d.get('deal_value_structured', 'Undisclosed')} {d.get('deal_type', 'deal')} "
                f"({status})\n"
                f"> {d.get('key_insight', d.get('title', ''))}"
            )
        else:
            lines.append(
                f"👁️ **{d.get('title', 'Untitled')}** — {status}\n"
                f"> Source: {d.get('source', 'Unknown')}"
            )

    return "\n\n".join(lines)


def _executive_summary(sections: dict, deals: list[dict], llm=None) -> str:
    """Section: TL;DR generated LAST, synthesizing all other sections."""
    if llm and deals:
        prompt = f"""Write the opening TL;DR for an FMCG deal newsletter.

Write exactly 4 bullet points:
- 🔥 The biggest deal this week and why it matters
- 📊 Deal flow snapshot — how many deals, which sectors
- 💡 One key trend or pattern (reference the sector pulse)
- 👀 What to watch next

HEADLINE DEAL SECTION:
{sections.get('headline_deal', '')[:600]}

DEAL BRIEFS:
{sections.get('deal_briefs', '')[:600]}

SECTOR PULSE:
{sections.get('sector_pulse', '')[:600]}

WATCHLIST:
{sections.get('watchlist', '')[:400]}

Total deals this week: {len(deals)}

Each bullet = one sentence. Emoji-prefixed."""
        result = _llm_generate(llm, prompt)
        if result:
            return result

    # Template fallback
    top = deals[0] if deals else {}
    rumored = sum(1 for d in deals if d.get("deal_status") == "rumored")
    return (
        f"- 🔥 **Top deal:** {top.get('title', 'N/A')}\n"
        f"- 📊 **This week:** {len(deals)} FMCG deals tracked across the sector\n"
        f"- 💡 **Trend:** Continued M&A activity signals sector consolidation\n"
        f"- 👀 **Watch:** {rumored} rumored deal(s) in the pipeline"
    )


# ---------------------------------------------------------------------------
# Markdown assembly
# ---------------------------------------------------------------------------

def _assemble_markdown(sections: dict, deals: list[dict], run_date: str) -> str:
    """Assemble all sections into a single newsletter Markdown document."""
    return f"""# 🏪 FMCG Deal Pulse — Week of {run_date}

## ⚡ TL;DR

{sections['executive_summary']}

---

## 🎯 Deal of the Week

{sections['headline_deal']}

---

## 📋 Deal Briefs

{sections['deal_briefs']}

---

## 📊 Sector Pulse

{sections['sector_pulse']}

---

## 👁️ Watchlist

{sections['watchlist']}

---

_Tracked {len(deals)} deals this week. Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}._
"""


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

def newsletter_node(state: dict) -> dict:
    """LangGraph node: generate newsletter from scored articles."""
    deals = state.get("scored_articles", [])
    metadata = {**state.get("metadata", {})}
    run_date = metadata.get("run_date", datetime.now().strftime("%Y-%m-%d"))

    if not deals:
        print("  [newsletter] No scored articles — skipping newsletter generation")
        return {
            "newsletter_sections": {},
            "output_paths": state.get("output_paths", {}),
            "metadata": metadata,
        }

    print(f"  [newsletter] Generating newsletter from {len(deals)} deals")

    # Initialize LLM if available
    no_api = metadata.get("no_api", False)
    llm = None
    if not no_api and os.getenv("OPENROUTER_API_KEY"):
        try:
            llm = _get_llm()
            print("  [newsletter] LLM available — generating narrative sections")
        except Exception as e:
            print(f"  [newsletter] LLM unavailable ({e}), using templates")

    # Generate sections (executive summary LAST)
    sections = {}

    print("  [newsletter] Section 1/5: Headline Deal" + (" (LLM)" if llm else " (template)"))
    sections["headline_deal"] = _headline_deal(deals, llm)

    print("  [newsletter] Section 2/5: Deal Briefs (template)")
    sections["deal_briefs"] = _deal_briefs(deals)

    print("  [newsletter] Section 3/5: Sector Pulse" + (" (LLM)" if llm else " (template)"))
    sections["sector_pulse"] = _sector_pulse(deals, llm)

    print("  [newsletter] Section 4/5: Watchlist (template)")
    sections["watchlist"] = _watchlist(deals)

    print("  [newsletter] Section 5/5: Executive Summary" + (" (LLM)" if llm else " (template)"))
    sections["executive_summary"] = _executive_summary(sections, deals, llm)

    # Assemble and save Markdown
    md_content = _assemble_markdown(sections, deals, run_date)
    OUTPUT_DIR.mkdir(exist_ok=True)
    md_path = OUTPUT_DIR / "newsletter.md"
    md_path.write_text(md_content)

    print(f"  [newsletter] Saved → {md_path}")

    metadata["newsletter_deals"] = len(deals)
    metadata["newsletter_generated"] = datetime.now().isoformat()

    return {
        "newsletter_sections": sections,
        "output_paths": {
            **state.get("output_paths", {}),
            "newsletter_md": str(md_path),
        },
        "metadata": metadata,
    }
