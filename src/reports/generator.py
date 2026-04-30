"""
Report generation - PDF report building and rendering.
"""

import html as html_escape
import io
import os
from typing import Any, AsyncGenerator

import aiofiles
from fastapi.concurrency import run_in_threadpool
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape="html",
)


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
    """Convert HTML content to PDF using WeasyPrint."""
    import logging
    import sys
    logger = logging.getLogger(__name__)
    try:
        print(f"DEBUG html_to_pdf: Starting conversion ({len(html_content)} bytes)", flush=True, file=sys.stderr)
        result = await run_in_threadpool(
            lambda: HTML(string=html_content).write_pdf()
        )
        print(f"DEBUG html_to_pdf: Done ({len(result)} bytes)", flush=True, file=sys.stderr)
        return result
    except Exception as e:
        print(f"DEBUG html_to_pdf: ERROR {e}", flush=True, file=sys.stderr)
        logger.error(f"PDF conversion error: {e}")
        raise


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
) -> dict:
    """Build the payload dict for the PDF template."""
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

    # Read files - handle errors gracefully
    try:
        file_a_lines = await read_file_content(file_a_data["file_path"])
        print(f"DEBUG build_payload: Read file_a ({len(file_a_lines)} lines)", flush=True, file=sys.stderr)
    except Exception as e:
        logger.warning(f"Could not read file_a {file_a_data['file_path']}: {e}")
        file_a_lines = []
    
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
        for match in matches[:10]:  # Limit to first 10 matches
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
    for i, match in enumerate(matches[:10]):  # Limit to first 10 matches
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

            file1_html = highlight_match(
                file_a_lines,
                file1_loc.get("start_line", 1),
                file1_loc.get("start_col", 1),
                file1_loc.get("end_line", 1),
                file1_loc.get("end_col", 1),
            )

            file2_html = highlight_match(
                file_b_lines,
                file2_loc.get("start_line", 1),
                file2_loc.get("start_col", 1),
                file2_loc.get("end_line", 1),
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
            "html": file_a_html,  # Only matched lines + context
        },
        "file_b": {
            "filename": file_b_data["filename"],
            "uploaded": file_b_data["created_at"],
            "html": file_b_html,  # Only matched lines + context
        },
        "reviewer": reviewer_email,
        "reviewed_at": result_data.get("reviewed_at") or "N/A",
        "detection_source": result_data.get("detection_source") or "auto",
        "matches": processed_matches,
    }