"""
Report generation - PDF report building and rendering.
"""

import html as html_escape
import io
import os
from typing import Any, AsyncGenerator

import aiofiles
from fastapi.concurrency import run_in_threadpool
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape="html",
)

# Match colors for pair comparison (light, readable)
MATCH_COLORS = [
    (255, 200, 200), (200, 255, 200), (200, 200, 255),
    (255, 255, 200), (255, 200, 255), (200, 255, 255),
]

def format_datetime(dt_str):
    """Format ISO datetime to DD-MM-YYYY HH:MM."""
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
        return dt.strftime('%d-%m-%Y %H:%M')
    except Exception:
        return str(dt_str)

def generate_snippet_html(lines, start_line, end_line, start_col, end_col, context=5):
    """Generate code snippet with context lines and highlighted match region."""
    result = []
    start_idx = start_line - 1
    end_idx = end_line - 1
    snippet_start = max(0, start_idx - context)
    snippet_end = min(len(lines), end_idx + context + 1)
    
    for i in range(snippet_start, snippet_end):
        line_num = i + 1
        raw_line = lines[i].rstrip("\n")
        escaped = html_escape.escape(raw_line)
        
        if start_line <= line_num <= end_line:
            if line_num == start_line and line_num == end_line:
                before = escaped[:start_col - 1]
                match_part = escaped[start_col - 1:end_col - 1]
                after = escaped[end_col - 1:]
                formatted = f"{before}<span class='highlight'>{match_part}</span>{after}"
            elif line_num == start_line:
                before = escaped[:start_col - 1]
                match_part = escaped[start_col - 1:]
                formatted = f"{before}<span class='highlight'>{match_part}</span>"
            elif line_num == end_line:
                match_part = escaped[:end_col - 1]
                after = escaped[end_col - 1:]
                formatted = f"<span class='highlight'>{match_part}</span>{after}"
            else:
                formatted = f"<span class='highlight'>{escaped}</span>"
        else:
            formatted = escaped
        result.append(f"{line_num:4d}: {formatted}")
    return "\n".join(result)

# PDF backend options: "weasyprint", "playwright", or "fpdf2"
# Note: This is now a function to allow runtime changes via environment variable
def get_pdf_backend():
    """Get the configured PDF backend (supports runtime changes via PDF_BACKEND env var)."""
    return os.getenv("PDF_BACKEND", "playwright").lower()


# Playwright browser instance (lazy-loaded)
_playwright_browser = None


def render_report_html(context: dict) -> str:
    """Render the Jinja2 template with the given context."""
    import sys
    import logging
    logger = logging.getLogger(__name__)
    try:
        template = env.get_template("report.html.jinja2")
        result = template.render(**context)
        print(f"DEBUG render_report_html: Rendered HTML size={len(result)} bytes", flush=True, file=sys.stderr)
        return result
    except Exception as e:
        logger.error(f"Template render error: {e}")
        raise


async def html_to_pdf(html_content: str) -> bytes:
    """Convert HTML content to PDF using configured backend (playwright, weasyprint, or fpdf2).

    Note: This function expects HTML content. For fpdf2 with context dict, use generate_report_pdf() instead.
    """
    import logging
    import sys
    logger = logging.getLogger(__name__)

    try:
        backend = get_pdf_backend()
        print(f"DEBUG html_to_pdf: Starting conversion ({len(html_content)} bytes) using {backend}", flush=True, file=sys.stderr)

        if backend == "playwright":
            result = await html_to_pdf_playwright(html_content)
        elif backend == "fpdf2":
            result = await html_to_pdf_fpdf2(html_content)
        else:
            result = await html_to_pdf_weasyprint(html_content)

        print(f"DEBUG html_to_pdf: Done ({len(result)} bytes)", flush=True, file=sys.stderr)
        return result
    except Exception as e:
        print(f"DEBUG html_to_pdf: ERROR {e}", flush=True, file=sys.stderr)
        logger.error(f"PDF conversion error: {e}")
        raise


async def generate_report_pdf(context: dict) -> bytes:
    """Generate PDF report from context dict using configured backend.

    This is the preferred function for generating PDF reports as it allows
    backends like fpdf2 to use the context directly without HTML conversion.

    Args:
        context: Dict with assignment, file_a, file_b, matches, etc.

    Returns:
        PDF bytes
    """
    import logging
    import sys
    logger = logging.getLogger(__name__)

    try:
        backend = get_pdf_backend()
        print(f"DEBUG generate_report_pdf: Starting with backend={backend}", flush=True, file=sys.stderr)

        if backend == "fpdf2":
            result = await generate_pdf_fpdf2(context)
        else:
            # Use HTML-based backends (playwright or weasyprint)
            html_content = render_report_html(context)
            result = await html_to_pdf(html_content)

        print(f"DEBUG generate_report_pdf: Done ({len(result)} bytes)", flush=True, file=sys.stderr)
        return result
    except Exception as e:
        print(f"DEBUG generate_report_pdf: ERROR {e}", flush=True, file=sys.stderr)
        logger.error(f"PDF generation error: {e}")
        raise


async def get_playwright_browser():
    """Get or create a shared Playwright browser instance."""
    global _playwright_browser

    if _playwright_browser is None:
        from playwright.async_api import async_playwright

        p = await async_playwright().start()
        _playwright_browser = await p.chromium.launch(args=['--no-sandbox'])

    return _playwright_browser


async def close_playwright_browser():
    """Close the shared Playwright browser instance."""
    global _playwright_browser

    if _playwright_browser is not None:
        await _playwright_browser.close()
        _playwright_browser = None


async def html_to_pdf_playwright(html_content: str, browser=None) -> bytes:
    """Convert HTML to PDF using Playwright (Chromium).

    Args:
        html_content: HTML string to convert
        browser: Optional shared browser instance (for bulk operations)
    """
    if browser is None:
        browser = await get_playwright_browser()

    page = await browser.new_page()
    await page.set_content(html_content)

    pdf_bytes = await page.pdf(
        format='A4',
        print_background=True,
        margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'}
    )

    await page.close()
    return pdf_bytes


async def html_to_pdf_weasyprint(html_content: str) -> bytes:
    """Convert HTML to PDF using WeasyPrint (legacy)."""
    from weasyprint import HTML

    return await run_in_threadpool(
        lambda: HTML(string=html_content).write_pdf()
    )


class ReportPDF(FPDF):
    """Custom PDF class with automatic footer and context access."""
    def __init__(self, context, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = context

    def footer(self):
        # Footer background
        self.set_fill_color(247, 250, 252)
        self.rect(0, self.h - 15, 210, 15, 'F')
        # Footer line
        self.set_draw_color(226, 232, 240)
        self.line(10, self.h - 15, 200, self.h - 15)
        
        # Logo (fixed spacing)
        logo_y = self.h - 13
        self.set_xy(10, logo_y)
        self.set_font('Courier', 'B', 8)
        
        self.set_text_color(45, 55, 72)
        w1 = self.get_string_width('plagi')
        self.cell(w1, 5, 'plagi', 0, new_x=XPos.RIGHT, new_y=YPos.TOP)
        
        self.set_text_color(72, 187, 120)
        w2 = self.get_string_width('type')
        self.cell(w2, 5, 'type', 0, new_x=XPos.RIGHT, new_y=YPos.TOP)
        
        self.set_text_color(45, 55, 72)
        w3 = self.get_string_width('_')
        self.cell(w3, 5, '_', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        # Generated date
        self.set_xy(150, logo_y)
        self.set_font('Helvetica', '', 7)
        self.set_text_color(160, 174, 192)
        reviewed_at = self.context.get('reviewed_at', 'N/A')
        self.cell(50, 5, f"Generated on {format_datetime(reviewed_at)}", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')


async def generate_pdf_fpdf2(context: dict) -> bytes:
    """Generate PDF from context dict using fpdf2 (no HTML conversion needed)."""
    pdf = ReportPDF(context)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ---------- HEADER ----------
    pdf.set_fill_color(26, 32, 44)
    pdf.rect(0, 0, 210, 28, 'F')

    # Logo text (fixed spacing)
    pdf.set_xy(10, 8)
    pdf.set_font('Courier', 'B', 16)
    
    pdf.set_text_color(255, 255, 255)
    w1 = pdf.get_string_width('plagi')
    pdf.cell(w1, 6, 'plagi', 0, new_x=XPos.RIGHT, new_y=YPos.TOP)
    
    pdf.set_text_color(72, 187, 120)
    w2 = pdf.get_string_width('type')
    pdf.cell(w2, 6, 'type', 0, new_x=XPos.RIGHT, new_y=YPos.TOP)
    
    pdf.set_text_color(255, 255, 255)
    w3 = pdf.get_string_width('_')
    pdf.cell(w3, 6, '_', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Badge (moved left from 170 to 150)
    pdf.set_xy(150, 8)
    pdf.set_fill_color(72, 187, 120)
    pdf.set_text_color(154, 230, 180)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.cell(30, 6, 'Plagiarism Detection Report', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=False)

    # More space between logo and title
    pdf.ln(2)

    # Title
    pdf.set_x(10)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 6, context.get('assignment', {}).get('name', 'Report'), 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Subtitle
    pdf.set_x(10)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(160, 174, 192)
    assignment_id = context.get('assignment', {}).get('id', 'N/A')
    pdf.cell(0, 5, f"Assignment ID: {assignment_id}", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ---------- CONTENT ----------
    pdf.set_y(35)
    pdf.set_text_color(0, 0, 0)

    # Meta table
    _draw_meta_table(pdf, context)

    # Pair comparison with multi-color matches
    _draw_pair_comparison(pdf, context)

    # Match cards
    matches = context.get('matches', [])
    if matches:
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 6, 'Match Regions', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)
        for i, m in enumerate(matches):
            _draw_match_card(pdf, m, i + 1)
    else:
        _draw_no_matches(pdf)

    return bytes(pdf.output())


def _draw_meta_table(pdf, context: dict):
    """Draw the meta information table."""
    from fpdf.enums import XPos, YPos

    pdf.set_fill_color(247, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    pdf.set_font('Helvetica', 'B', 7)
    pdf.ln(3)

    # Row 1: Files
    pdf.cell(95, 7, 'FILE A', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, fill=True)
    pdf.cell(95, 7, 'FILE B', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)

    pdf.set_font('Courier', '', 9)
    pdf.cell(95, 6, context['file_a']['filename'], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, fill=False)
    pdf.cell(95, 6, context['file_b']['filename'], 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=False)

    # Row 2: Upload dates (formatted)
    pdf.set_font('Helvetica', 'B', 7)
    pdf.cell(95, 7, 'UPLOADED (FILE A)', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, fill=True)
    pdf.cell(95, 7, 'UPLOADED (FILE B)', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)

    pdf.set_font('Helvetica', '', 9)
    pdf.cell(95, 6, format_datetime(context['file_a']['uploaded']), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, fill=False)
    pdf.cell(95, 6, format_datetime(context['file_b']['uploaded']), 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=False)

    # Row 3: Confirmed By (full width, no Detection Source)
    pdf.set_font('Helvetica', 'B', 7)
    pdf.cell(190, 7, 'CONFIRMED BY', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)

    pdf.set_font('Helvetica', '', 9)
    reviewer = context.get('reviewer') or 'Auto-detected'
    pdf.cell(190, 6, reviewer, 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=False)

    # Row 4: Review date & Total matches
    pdf.set_font('Helvetica', 'B', 7)
    pdf.cell(95, 7, 'REVIEW DATE', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, fill=True)
    pdf.cell(95, 7, 'TOTAL MATCHES', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)

    pdf.set_font('Helvetica', '', 9)
    pdf.cell(95, 6, format_datetime(context.get('reviewed_at', 'N/A')), 1, new_x=XPos.RIGHT, new_y=YPos.TOP, fill=False)
    pdf.cell(95, 6, str(len(context.get('matches', []))), 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=False)

    pdf.ln(5)


def _draw_match_card(pdf, match: dict, index: int):
    """Draw a single match card."""
    from fpdf.enums import XPos, YPos

    # Check if we need a page break
    if pdf.get_y() > 250:
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

    start_y = pdf.get_y()

    # Match header
    pdf.set_fill_color(247, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    pdf.rect(10, start_y, 190, 10, 'FD')

    pdf.set_xy(12, start_y + 2)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(45, 55, 72)
    pdf.cell(10, 6, f'{index}', 0, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(40, 6, 'Code Match', 0, new_x=XPos.RIGHT, new_y=YPos.TOP)

    # Similarity badge
    similarity = match.get('similarity', 0) or 0
    sim_pct = round(similarity * 100, 1)

    if sim_pct >= 70:
        pdf.set_fill_color(255, 245, 245)
        pdf.set_text_color(197, 48, 48)
        pdf.set_draw_color(254, 178, 178)
    elif sim_pct >= 40:
        pdf.set_fill_color(255, 255, 240)
        pdf.set_text_color(151, 90, 22)
        pdf.set_draw_color(246, 224, 94)
    else:
        pdf.set_fill_color(240, 255, 244)
        pdf.set_text_color(39, 103, 73)
        pdf.set_draw_color(154, 230, 180)

    pdf.set_xy(160, start_y + 2)
    pdf.cell(30, 6, f'{sim_pct}% similar', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)

    pdf.ln(1)

    # Code table header
    pdf.set_fill_color(235, 248, 255)
    pdf.set_text_color(43, 108, 176)
    pdf.set_font('Helvetica', 'B', 7)
    pdf.cell(95, 6, f"File A - {match.get('file1', {}).get('filename', '')}", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, fill=True)

    pdf.set_fill_color(250, 245, 255)
    pdf.set_text_color(107, 70, 193)
    pdf.cell(95, 6, f"File B - {match.get('file2', {}).get('filename', '')}", 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)

    # Code content
    pdf.set_font('Courier', '', 7)
    pdf.set_text_color(45, 55, 72)

    file1_html = match.get('file1_html', '')
    file2_html = match.get('file2_html', '')

    _draw_code_columns(pdf, file1_html, file2_html)

    # Footer
    pdf.set_fill_color(247, 250, 252)
    pdf.set_text_color(113, 128, 150)
    pdf.set_font('Helvetica', '', 7)
    f1 = match.get('file1', {})
    f2 = match.get('file2', {})
    footer_text = f"File A: lines {f1.get('start_line', '-')}-{f1.get('end_line', '-')}    File B: lines {f2.get('start_line', '-')}-{f2.get('end_line', '-')}"
    pdf.cell(190, 6, footer_text, 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)

    pdf.ln(3)


def _draw_code_columns(pdf, html1: str, html2: str):
    """Draw two columns of code with highlighted matches."""
    from fpdf.enums import XPos, YPos

    # Parse HTML to extract text and highlight info
    lines1 = _parse_html_to_lines(html1)
    lines2 = _parse_html_to_lines(html2)

    max_lines = max(len(lines1), len(lines2))
    row_height = 4

    for i in range(max_lines):
        y = pdf.get_y()

        # Check for page break
        if y > 280:
            pdf.add_page()
            y = pdf.get_y()

        # File A column
        pdf.set_xy(10, y)
        if i < len(lines1):
            line = lines1[i]
            if line['highlight']:
                pdf.set_fill_color(254, 252, 191)
                pdf.set_text_color(0, 0, 0)
            else:
                pdf.set_fill_color(252, 252, 252)
                pdf.set_text_color(45, 55, 72)
            pdf.cell(95, row_height, line['text'][:60], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, fill=True)
        else:
            pdf.cell(95, row_height, '', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, fill=False)

        # File B column
        if i < len(lines2):
            line = lines2[i]
            if line['highlight']:
                pdf.set_fill_color(254, 252, 191)
                pdf.set_text_color(0, 0, 0)
            else:
                pdf.set_fill_color(252, 252, 252)
                pdf.set_text_color(45, 55, 72)
            pdf.cell(95, row_height, line['text'][:60], 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        else:
            pdf.cell(95, row_height, '', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=False)


def _parse_html_to_lines(html: str) -> list:
    """Parse HTML string to extract lines with highlight info.

    Returns list of dicts: {'text': str, 'highlight': bool}
    """
    lines = []
    for line in html.split('\n'):
        # Remove HTML tags and extract text
        import re
        is_highlight = '<span' in line and 'highlight' in line
        text = re.sub(r'<[^>]+>', '', line)
        text = text.strip()
        if text:
            lines.append({'text': text, 'highlight': is_highlight})
    return lines


def _draw_no_matches(pdf):
    """Draw the 'no matches found' section."""
    from fpdf.enums import XPos, YPos

    pdf.ln(10)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(45, 55, 72)
    pdf.cell(0, 10, 'No Matches Found', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')

    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(113, 128, 150)
    pdf.cell(0, 6, 'No plagiarized code fragments were detected.', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.ln(10)


def _draw_pair_comparison(pdf, context: dict):
    """Draw side-by-side pair comparison with multi-colored match regions."""
    from fpdf.enums import XPos, YPos

    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(45, 55, 72)
    pdf.cell(0, 6, 'Pair Comparison', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    file_a_lines = context.get('file_a_lines', [])
    file_b_lines = context.get('file_b_lines', [])
    matches = context.get('matches', [])

    if not file_a_lines or not file_b_lines or not matches:
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(113, 128, 150)
        pdf.cell(0, 6, 'No data available for pair comparison.', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return

    # Assign colors to matches
    for i, m in enumerate(matches):
        m['color'] = MATCH_COLORS[i % len(MATCH_COLORS)]

    # Get all match regions with colors
    match_regions = []
    for m in matches:
        f1 = m.get('file1', {})
        f2 = m.get('file2', {})
        match_regions.append({
            'file1_start': f1.get('start_line', 1),
            'file1_end': f1.get('end_line', 1),
            'file2_start': f2.get('start_line', 1),
            'file2_end': f2.get('end_line', 1),
            'color': m['color']
        })

    # Determine snippet range (all matches + context)
    context_lines = 5
    min_line_a = max(1, min(r['file1_start'] for r in match_regions) - context_lines)
    max_line_a = min(len(file_a_lines), max(r['file1_end'] for r in match_regions) + context_lines)
    min_line_b = max(1, min(r['file2_start'] for r in match_regions) - context_lines)
    max_line_b = min(len(file_b_lines), max(r['file2_end'] for r in match_regions) + context_lines)

    # Draw side-by-side
    row_height = 4
    pdf.set_font('Courier', '', 7)
    max_lines = max(max_line_a - min_line_a + 1, max_line_b - min_line_b + 1)

    for i in range(max_lines):
        y = pdf.get_y()
        if y > 280:
            pdf.add_page()
            y = pdf.get_y()

        # File A column
        pdf.set_xy(10, y)
        a_line = min_line_a + i
        if a_line <= max_line_a and a_line <= len(file_a_lines):
            escaped = html_escape.escape(file_a_lines[a_line - 1].rstrip("\n"))
            # Check if line is in any match region
            fill = (252, 252, 252)  # Default
            for r in match_regions:
                if r['file1_start'] <= a_line <= r['file1_end']:
                    fill = r['color']
                    break
            pdf.set_fill_color(*fill)
            pdf.set_text_color(45, 55, 72)
            pdf.cell(95, row_height, f"{a_line:4d}: {escaped[:55]}", 1, new_x=XPos.RIGHT, new_y=YPos.TOP, fill=True)
        else:
            pdf.cell(95, row_height, '', 1, new_x=XPos.RIGHT, new_y=YPos.TOP, fill=False)

        # File B column
        b_line = min_line_b + i
        if b_line <= max_line_b and b_line <= len(file_b_lines):
            escaped = html_escape.escape(file_b_lines[b_line - 1].rstrip("\n"))
            # Check if line is in any match region
            fill = (252, 252, 252)  # Default
            for r in match_regions:
                if r['file2_start'] <= b_line <= r['file2_end']:
                    fill = r['color']
                    break
            pdf.set_fill_color(*fill)
            pdf.set_text_color(45, 55, 72)
            pdf.cell(95, row_height, f"{b_line:4d}: {escaped[:55]}", 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        else:
            pdf.cell(95, row_height, '', 1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=False)

    pdf.ln(5)


def _draw_footer(pdf, context: dict):
    """Draw the footer."""
    from fpdf.enums import XPos, YPos

    pdf.set_y(-15)
    pdf.set_draw_color(226, 232, 240)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())

    pdf.set_font('Courier', 'B', 8)
    pdf.set_text_color(45, 55, 72)
    pdf.set_xy(10, pdf.get_y() + 2)
    pdf.cell(40, 5, 'plagi', 0, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_text_color(72, 187, 120)
    pdf.cell(20, 5, 'type', 0, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(5, 5, '_', 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(150, pdf.get_y() - 5)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(160, 174, 192)
    reviewed_at = context.get('reviewed_at', 'N/A')
    detection_source = context.get('detection_source', 'auto')
    pdf.cell(50, 5, f"Generated on {reviewed_at} - {detection_source} detection", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')


async def html_to_pdf_fpdf2(html_content: str) -> bytes:
    """Convert HTML to PDF using fpdf2 (simplified - renders basic HTML).

    Note: For best results, use generate_pdf_fpdf2() with context dict instead.
    """
    # This is a simplified fallback - for production use generate_pdf_fpdf2()
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', '', 12)

    # Strip HTML tags and add content
    import re
    text = re.sub(r'<[^>]+>', '', html_content)
    pdf.multi_cell(0, 10, text)

    return bytes(pdf.output())


async def bulk_html_to_pdf(html_list):
    """
    Convert multiple HTML strings to PDFs using the configured backend.

    Args:
        html_list: List of (filename, html_content) tuples

    Returns:
        List of (filename, pdf_bytes) tuples
    """
    backend = get_pdf_backend()

    if backend == "playwright":
        return await _bulk_playwright(html_list)
    elif backend == "fpdf2":
        return await _bulk_fpdf2(html_list)
    else:
        return await _bulk_weasyprint(html_list)


async def _bulk_fpdf2(html_list):
    """Bulk convert using fpdf2 (sequential)."""
    results = []
    for filename, html_content in html_list:
        pdf_bytes = await html_to_pdf_fpdf2(html_content)
        results.append((filename, pdf_bytes))
    return results


async def _bulk_playwright(html_list):
    """Bulk convert using Playwright with shared browser."""
    from playwright.async_api import async_playwright

    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--no-sandbox'])
        for filename, html_content in html_list:
            page = await browser.new_page()
            await page.set_content(html_content)
            pdf_bytes = await page.pdf(
                format='A4',
                print_background=True,
                margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'}
            )
            await page.close()
            results.append((filename, pdf_bytes))

        await browser.close()

    return results


async def _bulk_weasyprint(html_list):
    """Bulk convert using WeasyPrint (sequential)."""
    from weasyprint import HTML

    results = []
    for filename, html_content in html_list:
        pdf_bytes = await run_in_threadpool(
            lambda h=html_content: HTML(string=h).write_pdf()
        )
        results.append((filename, pdf_bytes))

    return results


async def _bulk_weasyprint(html_list: list[tuple[str, str]]) -> list[tuple[str, bytes]]:
    """Bulk convert using WeasyPrint (sequential)."""
    from weasyprint import HTML

    results = []
    for filename, html_content in html_list:
        pdf_bytes = await run_in_threadpool(
            lambda h=html_content: HTML(string=h).write_pdf()
        )
        results.append((filename, pdf_bytes))

    return results


def highlight_match(
    lines: list[str],
    start_line: int,
    start_col: int,
    end_line: int,
    end_col: int,
) -> str:
    """
    Highlight matching region in a list of lines.
    Lines are 1-indexed, columns are 1-indexed.
    Returns a string with line numbers and highlighted spans.
    """
    result = []
    for i, line in enumerate(lines):
        line_num = i + 1
        escaped = html_escape.escape(line.rstrip("\n"))

        if start_line <= line_num <= end_line:
            if line_num == start_line and line_num == end_line:
                before = escaped[: start_col - 1]
                match = escaped[start_col - 1 : end_col - 1]
                after = escaped[end_col - 1 :]
                escaped = f"{before}<span class=\"highlight\">{match}</span>{after}"
            elif line_num == start_line:
                before = escaped[: start_col - 1]
                match = escaped[start_col - 1 :]
                escaped = f"{before}<span class='highlight'>{match}</span>"
            elif line_num == end_line:
                match = escaped[: end_col - 1]
                after = escaped[end_col - 1 :]
                escaped = f"<span class='highlight'>{match}</span>{after}"
            else:
                escaped = f"<span class='highlight'>{escaped}</span>"

        result.append(f"{line_num:4d}: {escaped}")

    return "\n".join(result)


async def read_file_content(file_path: str) -> list[str]:
    """Read file content as a list of lines."""
    async with aiofiles.open(file_path, "r") as f:
        content = await f.read()
    return content.splitlines(keepends=False)


async def build_report_payload(
    result_data: dict,
    file_a_data: dict,
    file_b_data: dict,
    assignment_data: dict,
    matches: list[dict],
    reviewer_email: str | None,
    file_a_lines: list[str] | None = None,
    file_b_lines: list[str] | None = None,
) -> dict:
    """Build the payload dict for the PDF template.

    Args:
        result_data: Dict with result metadata
        file_a_data: Dict with file_a metadata
        file_b_data: Dict with file_b metadata
        assignment_data: Dict with assignment metadata
        matches: List of match dicts
        reviewer_email: Reviewer email or None
        file_a_lines: Optional pre-loaded file_a lines (to avoid re-reading)
        file_b_lines: Optional pre-loaded file_b lines (to avoid re-reading)
    """
    import sys
    import json
    import ast
    import logging
    logger = logging.getLogger(__name__)

    if matches is None:
        matches = []
    elif isinstance(matches, str):
        try:
            matches = json.loads(matches)
        except:
            try:
                matches = ast.literal_eval(matches)
            except:
                matches = []
    elif not isinstance(matches, list):
        matches = []

    print(f"DEBUG build_payload: Reading files...", flush=True, file=sys.stderr)

    # Read files if not provided - handle errors gracefully
    if file_a_lines is None:
        try:
            file_a_lines = await read_file_content(file_a_data["file_path"])
            print(f"DEBUG build_payload: Read file_a ({len(file_a_lines)} lines)", flush=True, file=sys.stderr)
        except Exception as e:
            logger.warning(f"Could not read file_a {file_a_data['file_path']}: {e}")
            file_a_lines = []

    if file_b_lines is None:
        try:
            file_b_lines = await read_file_content(file_b_data["file_path"])
            print(f"DEBUG build_payload: Read file_b ({len(file_b_lines)} lines)", flush=True, file=sys.stderr)
        except Exception as e:
            logger.warning(f"Could not read file_b {file_b_data['file_path']}: {e}")
            file_b_lines = []
    
    # Extract lines to include (matched lines + context)
    CONTEXT_LINES = 5  # Number of context lines before/after match
    
    def get_lines_to_include(lines, matches, file_key):
        """Get set of line numbers to include (matched lines + context)."""
        lines_to_include = set()
        for match in matches:
            # Handle case where match might be a string
            if isinstance(match, str):
                try:
                    match = json.loads(match)
                except:
                    try:
                        match = ast.literal_eval(match)
                    except:
                        continue

            if not isinstance(match, dict):
                continue

            file_loc = match.get(file_key, {})
            if not isinstance(file_loc, dict):
                continue

            start_line = file_loc.get("start_line", 1)
            end_line = file_loc.get("end_line", 1)

            # Add context lines
            for line_num in range(max(1, start_line - CONTEXT_LINES), min(len(lines) + 1, end_line + CONTEXT_LINES + 1)):
                lines_to_include.add(line_num)

        return lines_to_include
    
    # Get lines to include for both files
    file_a_lines_to_include = get_lines_to_include(file_a_lines, matches, "file1")
    file_b_lines_to_include = get_lines_to_include(file_b_lines, matches, "file2")
    
    # Build HTML with only relevant lines
    def build_file_html(lines, lines_to_include):
        """Build HTML with only the specified lines (with line numbers)."""
        if not lines or not lines_to_include:
            return "No content available"
        
        result = []
        for i, line in enumerate(lines):
            line_num = i + 1
            if line_num in lines_to_include:
                escaped = html_escape.escape(line.rstrip("\n"))
                result.append(f"{line_num:4d}: {escaped}")
        return "\n".join(result)
    
    file_a_html = build_file_html(file_a_lines, file_a_lines_to_include)
    file_b_html = build_file_html(file_b_lines, file_b_lines_to_include)
    print(f"DEBUG build_payload: file_a_html size={len(file_a_html)}, file_b_html size={len(file_b_html)}", flush=True, file=sys.stderr)
    # Parse matches if it's a string (JSONB might return string representation)
    if isinstance(matches, str):
        import json
        try:
            matches = json.loads(matches)
        except json.JSONDecodeError:
            import ast
            matches = ast.literal_eval(matches)
    
    processed_matches = []
    for i, match in enumerate(matches):
        try:
            # Handle case where match might be a string
            if isinstance(match, str):
                import json
                try:
                    match = json.loads(match)
                except json.JSONDecodeError:
                    import ast
                    match = ast.literal_eval(match)
            
            file1_loc = match.get("file1", {}) if isinstance(match, dict) else {}
            file2_loc = match.get("file2", {}) if isinstance(match, dict) else {}
            
            # Handle case where file1_loc or file2_loc might be strings
            if isinstance(file1_loc, str):
                try:
                    file1_loc = json.loads(file1_loc)
                except json.JSONDecodeError:
                    import ast
                    file1_loc = ast.literal_eval(file1_loc)
            if isinstance(file2_loc, str):
                try:
                    file2_loc = json.loads(file2_loc)
                except json.JSONDecodeError:
                    import ast
                    file2_loc = ast.literal_eval(file2_loc)

            file1_html = generate_snippet_html(
                file_a_lines,
                file1_loc.get("start_line", 1),
                file1_loc.get("end_line", 1),
                file1_loc.get("start_col", 1),
                file1_loc.get("end_col", 1),
            )

            file2_html = generate_snippet_html(
                file_b_lines,
                file2_loc.get("start_line", 1),
                file2_loc.get("end_line", 1),
                file2_loc.get("start_col", 1),
                file2_loc.get("end_col", 1),
            )

            processed_matches.append({
                "file1_html": file1_html,
                "file2_html": file2_html,
                "similarity": match.get("similarity"),
                "file1": file1_loc,
                "file2": file2_loc,
            })
        except Exception as e:
            logger.warning(f"Error processing match {i}: {e}")
            continue

    print(f"DEBUG build_payload: file_a_html size={len(file_a_html)}, file_b_html size={len(file_b_html)}", flush=True, file=sys.stderr)
    
    print(f"DEBUG build_payload: file_a_html size={len(file_a_html)}, file_b_html size={len(file_b_html)}", flush=True, file=sys.stderr)
    
    return {
        "assignment": assignment_data,
        "file_a": {
            "filename": file_a_data["filename"],
            "uploaded": file_a_data["created_at"],
            "html": file_a_html,
        },
        "file_b": {
            "filename": file_b_data["filename"],
            "uploaded": file_b_data["created_at"],
            "html": file_b_html,
        },
        "file_a_lines": file_a_lines,
        "file_b_lines": file_b_lines,
        "reviewer": reviewer_email,
        "reviewed_at": result_data.get("reviewed_at") or "N/A",
        "matches": processed_matches,
    }