"""
formatter.py — Converts DigestPackage into a polished HTML email
and a plain-text fallback.
"""

from datetime import datetime
from jinja2 import Template
from summarizer import DigestItem, DigestPackage


# ─────────────────────────────────────────────────────────────────────────────
# Email Template
# ─────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Immigration Compliance Alert</title>
<style>
  body        { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: #f5f5f5; margin: 0; padding: 0; color: #1a1a1a; }
  .wrapper    { max-width: 640px; margin: 24px auto; background: #fff;
                border-radius: 8px; overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,.08); }
  .header     { background: #1e3a5f; padding: 28px 32px; }
  .header h1  { color: #fff; margin: 0; font-size: 22px; font-weight: 700; }
  .header p   { color: #a8c4e0; margin: 6px 0 0; font-size: 13px; }
  .badge-bar  { background: #f0f4f8; padding: 10px 32px;
                font-size: 12px; color: #5a6e82; border-bottom: 1px solid #e2e8f0; }
  .content    { padding: 24px 32px; }
  .item       { border: 1px solid #e2e8f0; border-radius: 6px;
                margin-bottom: 20px; overflow: hidden; }
  .item-header{ padding: 14px 18px; }
  .urgency-action { background: #fff5f5; border-left: 4px solid #e53e3e; }
  .urgency-monitor{ background: #fffaf0; border-left: 4px solid #dd6b20; }
  .urgency-fyi    { background: #f0fff4; border-left: 4px solid #38a169; }
  .urgency-tag    { display: inline-block; font-size: 11px; font-weight: 700;
                    text-transform: uppercase; letter-spacing: .5px;
                    padding: 3px 8px; border-radius: 3px; margin-bottom: 8px; }
  .tag-action  { background: #fed7d7; color: #c53030; }
  .tag-monitor { background: #feebc8; color: #c05621; }
  .tag-fyi     { background: #c6f6d5; color: #276749; }
  .item-title { font-size: 15px; font-weight: 600; color: #1a1a1a;
                margin: 0 0 4px; }
  .item-source{ font-size: 12px; color: #718096; }
  .item-body  { padding: 14px 18px; border-top: 1px solid #e2e8f0; }
  .item-summary { font-size: 14px; line-height: 1.6; color: #2d3748;
                  margin: 0 0 12px; }
  .actions    { background: #f7fafc; border-radius: 4px;
                padding: 12px 14px; margin: 0 0 10px; }
  .actions h4 { font-size: 12px; font-weight: 700; color: #4a5568;
                text-transform: uppercase; letter-spacing: .4px; margin: 0 0 8px; }
  .actions ul { margin: 0; padding-left: 18px; }
  .actions li { font-size: 13px; color: #2d3748; margin-bottom: 4px; line-height: 1.5; }
  .deadline   { font-size: 12px; color: #718096; margin-top: 8px; }
  .deadline strong { color: #e53e3e; }
  .read-more  { display: inline-block; font-size: 12px; color: #3182ce;
                text-decoration: none; margin-top: 6px; }
  .footer     { background: #f7fafc; padding: 20px 32px;
                border-top: 1px solid #e2e8f0; font-size: 12px; color: #718096; }
  .footer a   { color: #3182ce; }
  .divider    { height: 1px; background: #e2e8f0; margin: 4px 0 20px; }
  .no-items   { text-align: center; padding: 40px; color: #718096; font-size: 14px; }
  .summary-bar{ background: #ebf8ff; border: 1px solid #bee3f8;
                border-radius: 6px; padding: 12px 18px; margin-bottom: 24px;
                font-size: 13px; color: #2c5282; }
</style>
</head>
<body>
<div class="wrapper">

  <!-- Header -->
  <div class="header">
    <h1>🇺🇸 Immigration Compliance Alert</h1>
    <p>{{ date_str }} &nbsp;·&nbsp; {{ item_count }} update{{ 's' if item_count != 1 else '' }} today</p>
  </div>

  <!-- Summary badge -->
  <div class="badge-bar">
    {% if action_count > 0 %}⚠️ {{ action_count }} item{{ 's' if action_count != 1 else '' }} require action &nbsp;|&nbsp; {% endif %}
    📌 {{ monitor_count }} to monitor &nbsp;|&nbsp; ℹ️ {{ fyi_count }} FYI
  </div>

  <div class="content">

    {% if items %}
    <div class="summary-bar">
      <strong>Quick brief:</strong> Today's digest covers changes from
      {{ source_names | join(', ') }}.
      {% if action_count > 0 %}
      <strong>{{ action_count }} item{{ 's require' if action_count != 1 else ' requires' }} immediate attention.</strong>
      {% endif %}
    </div>

    {% for item in items %}
    <div class="item">

      <!-- Item header with urgency color -->
      <div class="item-header {% if item.urgency == 'Action required' %}urgency-action
        {%- elif item.urgency == 'Monitor' %}urgency-monitor
        {%- else %}urgency-fyi{% endif %}">
        <span class="urgency-tag {% if item.urgency == 'Action required' %}tag-action
          {%- elif item.urgency == 'Monitor' %}tag-monitor
          {%- else %}tag-fyi{% endif %}">
          {{ item.urgency }}
        </span>
        <p class="item-title">{{ item.headline }}</p>
        <span class="item-source">{{ item.source_name }}</span>
      </div>

      <!-- Item body -->
      <div class="item-body">
        <p class="item-summary">{{ item.plain_summary }}</p>

        {% if item.action_items %}
        <div class="actions">
          <h4>What to do</h4>
          <ul>
            {% for action in item.action_items %}
            <li>{{ action }}</li>
            {% endfor %}
          </ul>
        </div>
        {% endif %}

        {% if item.deadline and item.deadline != 'No deadline' %}
        <p class="deadline">📅 Deadline: <strong>{{ item.deadline }}</strong></p>
        {% endif %}

        <a class="read-more" href="{{ item.url }}" target="_blank">
          Read official source →
        </a>
      </div>

    </div>
    {% endfor %}

    {% else %}
    <div class="no-items">
      ✅ No material changes today across monitored sources.<br>
      We'll be back tomorrow.
    </div>
    {% endif %}

  </div><!-- /content -->

  <div class="footer">
    <p>
      You're receiving this because you subscribed to 
      <strong>Immigration Compliance Daily</strong>.
      This digest is a summary of publicly available regulatory news 
      for informational purposes only — not legal advice. 
      Consult qualified immigration counsel for specific situations.
    </p>
    <p>
      <a href="{{ unsubscribe_url }}">Unsubscribe</a> &nbsp;·&nbsp;
      <a href="{{ manage_url }}">Manage subscription</a> &nbsp;·&nbsp;
      <a href="{{ archive_url }}">View archive</a>
    </p>
  </div>

</div>
</body>
</html>
"""

PLAIN_TEXT_TEMPLATE = """IMMIGRATION COMPLIANCE ALERT — {{ date_str }}
{{ item_count }} update{{ 's' if item_count != 1 else '' }} today
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{% for item in items %}
[{{ item.urgency | upper }}] {{ item.headline }}
Source: {{ item.source_name }}

{{ item.plain_summary }}
{% if item.action_items %}
ACTION ITEMS:
{% for action in item.action_items %}  • {{ action }}
{% endfor %}{% endif %}
{% if item.deadline and item.deadline != 'No deadline' %}Deadline: {{ item.deadline }}{% endif %}
More: {{ item.url }}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{% endfor %}
This is a news summary, not legal advice. Consult immigration counsel for specific situations.
Unsubscribe: {{ unsubscribe_url }}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Formatter
# ─────────────────────────────────────────────────────────────────────────────

def format_digest(
    package: DigestPackage,
    unsubscribe_url: str = "{{unsubscribe_url}}",   # Beehiiv fills these in
    manage_url:     str = "{{manage_url}}",
    archive_url:    str = "{{archive_url}}",
) -> tuple[str, str, str]:
    """
    Returns: (subject_line, html_body, plain_text_body)
    """
    items = package.items
    now   = datetime.now()
    date_str = now.strftime("%A, %B %-d, %Y")

    action_count  = sum(1 for i in items if i.urgency == "Action required")
    monitor_count = sum(1 for i in items if i.urgency == "Monitor")
    fyi_count     = sum(1 for i in items if i.urgency == "FYI")
    source_names  = list(dict.fromkeys(i.source_name for i in items))  # dedup, preserve order

    ctx = dict(
        items          = items,
        date_str       = date_str,
        item_count     = len(items),
        action_count   = action_count,
        monitor_count  = monitor_count,
        fyi_count      = fyi_count,
        source_names   = source_names,
        unsubscribe_url= unsubscribe_url,
        manage_url     = manage_url,
        archive_url    = archive_url,
    )

    # Subject line
    if action_count > 0:
        subject = f"⚠️ {action_count} Action Required — Immigration Compliance Alert {now.strftime('%b %-d')}"
    elif items:
        subject = f"📋 {len(items)} Updates — Immigration Compliance Digest {now.strftime('%b %-d')}"
    else:
        subject = f"✅ No Changes Today — Immigration Compliance {now.strftime('%b %-d')}"

    html  = Template(HTML_TEMPLATE).render(**ctx)
    plain = Template(PLAIN_TEXT_TEMPLATE).render(**ctx)

    return subject, html, plain


if __name__ == "__main__":
    # Test with dummy data
    from summarizer import DigestItem, DigestPackage

    dummy_items = [
        DigestItem(
            source_name  = "USCIS News",
            title        = "New I-9 Form Required",
            url          = "https://uscis.gov/example",
            priority     = "critical",
            tags         = ["i9"],
            headline     = "USCIS requires new I-9 form version starting April 1, 2026",
            plain_summary= "All US employers must use the updated Form I-9 (Rev. 10/15/25) "
                           "for all new hires starting April 1, 2026. Using old versions "
                           "after this date can result in fines up to $2,500 per violation.",
            action_items = [
                "Download the new I-9 form from uscis.gov/i-9 immediately",
                "Update your onboarding packet before April 1",
                "Train HR staff on the 2 new List C documents",
            ],
            urgency      = "Action required",
            deadline     = "April 1, 2026",
        ),
        DigestItem(
            source_name  = "Federal Register",
            title        = "H-1B Wage Rule Update",
            url          = "https://federalregister.gov/example",
            priority     = "high",
            tags         = ["h1b", "prevailing_wage"],
            headline     = "DOL proposes updated prevailing wage methodology for H-1B filings",
            plain_summary= "A proposed rule would change how prevailing wages are calculated "
                           "for H-1B positions, potentially increasing required salary levels "
                           "by 10–20% in tech roles. Public comment period open until May 15.",
            action_items = [
                "Review current H-1B employees' salaries against proposed new levels",
                "Consider submitting a public comment if impacted",
            ],
            urgency      = "Monitor",
            deadline     = "May 15, 2026 (comment deadline)",
        ),
    ]

    package = DigestPackage(
        items            = dummy_items,
        quality_score    = 9,
        quality_notes    = "Strong digest with actionable items.",
        send_recommended = True,
    )

    subject, html, plain = format_digest(package)
    print(f"Subject: {subject}\n")
    print("--- PLAIN TEXT ---")
    print(plain)

    # Save HTML for preview
    with open("/tmp/digest_preview.html", "w") as f:
        f.write(html)
    print("\nHTML saved to /tmp/digest_preview.html")
