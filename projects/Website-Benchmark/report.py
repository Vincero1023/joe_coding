from __future__ import annotations

from pathlib import Path

from analyzer import Finding, PageAnalysis, SiteAnalysis


def render_markdown(site: SiteAnalysis) -> str:
    lines: list[str] = []
    lines.append("# Website Benchmark Report")
    lines.append("")
    lines.append(f"- Generated: {site.generated_at}")
    lines.append(f"- Source: `{site.source}`")
    lines.append(f"- Pages analyzed: {len(site.pages)}")
    lines.append("")

    lines.append("## Executive Summary")
    lines.append("")
    if site.navigation:
        lines.append(f"- Primary navigation signals: {', '.join(site.navigation[:6])}")
    else:
        lines.append("- Primary navigation signals: not enough navigation links detected")
    lines.append(f"- Common components: {format_findings(site.common_components) or 'No strong common component pattern detected'}")
    lines.append(f"- Key features: {format_findings(site.feature_summary[:6]) or 'No high-confidence feature signal detected'}")
    lines.append(f"- Candidate user flows: {format_findings(site.flows[:5]) or 'No high-confidence user flow detected'}")
    if site.load_issues:
        lines.append(f"- Load issues: {len(site.load_issues)}")
    lines.append("")

    if site.load_issues:
        lines.append("## Load Notes")
        lines.append("")
        for issue in site.load_issues:
            lines.append(f"- `{issue.source}`: {issue.message}")
        lines.append("")

    lines.append("## Page Inventory")
    lines.append("")
    for page in site.pages:
        lines.extend(render_page(page))

    lines.append("## Cross-Page Patterns")
    lines.append("")
    lines.append("### Common Components")
    lines.append("")
    if site.common_components:
        for component in site.common_components:
            lines.append(f"- {component.name}: {', '.join(component.evidence) if component.evidence else 'detected'}")
    else:
        lines.append("- None strong enough to count as common yet.")
    lines.append("")

    lines.append("### Feature Summary")
    lines.append("")
    if site.feature_summary:
        for feature in site.feature_summary:
            lines.append(f"- {feature.name}: {', '.join(feature.evidence) if feature.evidence else 'detected'}")
    else:
        lines.append("- No feature summary available.")
    lines.append("")

    lines.append("### Candidate User Flows")
    lines.append("")
    if site.flows:
        for index, flow in enumerate(site.flows, start=1):
            evidence = f" ({', '.join(flow.evidence)})" if flow.evidence else ""
            lines.append(f"{index}. {flow.name}{evidence}")
    else:
        lines.append("1. No cross-page flow stood out strongly enough to report.")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_page(page: PageAnalysis) -> list[str]:
    lines: list[str] = []
    title = page.title or Path(page.source).name
    lines.append(f"### {title}")
    lines.append("")
    lines.append(f"- Source: `{page.source}`")
    if page.encoding:
        lines.append(f"- Encoding: `{page.encoding}`")
    lines.append(f"- Role: `{page.page_role}`")
    lines.append(f"- Summary: {page.summary}")
    if page.meta_description:
        lines.append(f"- Meta description: {page.meta_description}")
    lines.append(
        "- Stats: "
        f"{page.stats.get('sections', 0)} sections, "
        f"{page.stats.get('links', 0)} links, "
        f"{page.stats.get('forms', 0)} forms, "
        f"{page.stats.get('buttons', 0)} buttons"
    )
    lines.append(f"- Features: {format_findings(page.features) or 'No strong feature signal'}")
    lines.append(f"- Components: {format_findings(page.components) or 'No strong component signal'}")
    lines.append(f"- User flows: {format_findings(page.flows) or 'No strong page-level flow'}")
    lines.append("")

    if page.sections:
        lines.append("#### Main Sections")
        lines.append("")
        for section in page.sections:
            lines.append(
                f"- {section.label} [{section.kind}]: "
                f"{section.headline} "
                f"(links: {section.link_count}, buttons: {section.button_count})"
            )
        lines.append("")

    if page.forms:
        lines.append("#### Forms")
        lines.append("")
        for form in page.forms:
            fields = ", ".join(form.fields) if form.fields else "No fields captured"
            actions = form.action or "inline/no action"
            submits = ", ".join(form.submit_labels) if form.submit_labels else "No submit label"
            lines.append(f"- `{form.method}` `{actions}` -> fields: {fields}; submit: {submits}")
        lines.append("")

    if page.links:
        lines.append("#### Notable Links")
        lines.append("")
        for link in page.links[:8]:
            scope = "internal" if link.internal else "external"
            lines.append(f"- {link.text} [{scope}] -> `{link.target}`")
        lines.append("")

    return lines


def format_findings(findings: list[Finding]) -> str:
    if not findings:
        return ""
    return ", ".join(finding.name for finding in findings)
