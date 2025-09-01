#!/usr/bin/env python3
"""
Claude Code History Converter

Converts Claude Code JSONL files to organized markdown files.
Usage: ./get_cc_hist.py <output_folder>

Architecture:
- Content Processors: Handle different types of message content (text, tools, results)
- Message Filters: Determine what messages to include/skip
- Output Formatters: Generate markdown for different sections
- Main Pipeline: Orchestrate the conversion process

This modular design makes it easy to:
- Add new content types (extend Content Processors)
- Change filtering logic (modify Message Filters)
- Adjust output format (update Output Formatters)
"""

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


# ============================================================================
# UTILITY FUNCTIONS - Basic helpers for file and data processing
# ============================================================================


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe filesystem usage."""
    # Remove/replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # Limit length
    if len(filename) > 100:
        filename = filename[:97] + "..."
    return filename


def format_timestamp(timestamp: str) -> str:
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return timestamp


def extract_project_name(cwd: str) -> str:
    """Extract project name from working directory."""
    if cwd:
        return Path(cwd).name
    return "unknown_project"


# ============================================================================
# CONTENT PROCESSORS - Handle different types of message content
# ============================================================================


def process_text_content(text_content: str) -> str:
    """Process plain text content."""
    if not isinstance(text_content, str):
        return ""

    # Clean ANSI codes and excessive whitespace
    cleaned_text = clean_tool_output(text_content)
    cleaned_text = "\n".join(line.strip() for line in cleaned_text.split("\n") if line.strip())
    return cleaned_text


def process_tool_use_content(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """Process tool usage content."""
    result = [f"**Tool Used:** {tool_name}"]

    if tool_input:
        # Format JSON more compactly for common tools
        indent_level = 2 if len(str(tool_input)) < 200 else 1
        result.append(f"```json\n{json.dumps(tool_input, indent=indent_level)}\n```")

    return "\n\n".join(result)


def process_tool_result_content(tool_result: Any) -> str:
    """Process tool result content."""
    if isinstance(tool_result, str):
        # Clean up tool result output
        cleaned_result = clean_tool_output(tool_result)
        # Truncate very long tool results
        if len(cleaned_result) > 2000:
            cleaned_result = cleaned_result[:2000] + "\n... (truncated)"
        return f"🔧Tool Result:\n```\n{cleaned_result}\n```"
    else:
        # If it's not a string, convert to JSON
        return f"🔧Tool Result:\n```json\n{json.dumps(tool_result, indent=2)}\n```"


def format_content(content: Any) -> str:
    """Format message content to markdown using specialized processors."""
    # Handle simple string content
    if isinstance(content, str):
        return clean_tool_output(content)

    # Handle list content (typical Claude Code format)
    if isinstance(content, list):
        result = []
        for item in content:
            if isinstance(item, dict):
                content_type = item.get("type")

                # Process different content types with dedicated handlers
                if content_type == "text":
                    text_content = item.get("text", "")
                    processed_text = process_text_content(text_content)
                    if processed_text:
                        result.append(processed_text)

                elif content_type == "tool_use":
                    tool_name = item.get("name", "unknown")
                    tool_input = item.get("input", {})
                    processed_tool_use = process_tool_use_content(tool_name, tool_input)
                    result.append(processed_tool_use)

                elif content_type == "tool_result":
                    tool_result = item.get("content", "")
                    processed_tool_result = process_tool_result_content(tool_result)
                    result.append(processed_tool_result)

            else:
                # Handle non-dict items in the list
                result.append(str(item))

        return "\n\n".join(result)

    # Fallback for other content types
    return str(content)


def clean_tool_output(output: str) -> str:
    """Clean tool output by removing line numbers, tabs, and console colors."""
    if not output:
        return output

    lines = output.split("\n")
    cleaned_lines = []

    for line in lines:
        # Remove all ANSI escape sequences (more comprehensive pattern)
        # This handles color codes, cursor movements, and other control sequences
        line = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", line)
        line = re.sub(r"\[[\d;]*m", "", line)  # Handle sequences like [38;2;153;153;153m

        # Remove line numbers pattern like "1→", "    10→", etc.
        line = re.sub(r"^\s*\d+→", "", line)

        # Remove leading tabs that were after line numbers
        if line.startswith("\t"):
            line = line[1:]

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


# ============================================================================
# MAIN PIPELINE - Orchestrate the conversion process
# ============================================================================


def process_jsonl_file(jsonl_path: Path, output_dir: Path) -> Optional[str]:
    """Process a single JSONL file and convert to markdown."""
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            return None

        messages = []
        summary = ""
        project_name = "unknown"
        session_id = ""

        for line in lines:
            try:
                entry = json.loads(line.strip())

                # Extract summary from first line if available
                if entry.get("type") == "summary":
                    summary = entry.get("summary", "")
                    leaf_uuid = entry.get("leafUuid", "")
                    continue

                # Extract project info
                if entry.get("cwd"):
                    project_name = extract_project_name(entry["cwd"])
                if entry.get("sessionId"):
                    session_id = entry["sessionId"]

                messages.append(entry)

            except json.JSONDecodeError:
                continue

        if not messages:
            return None

        # Generate output filename
        if summary:
            filename = sanitize_filename(f"{project_name}_{summary}")
        else:
            filename = f"{project_name}_{session_id[:8]}"

        output_file = output_dir / f"{filename}.md"

        # Skip if file already exists
        if output_file.exists():
            print(f"Skipping existing file: {output_file}")
            return "skipped"

        # Generate markdown content
        markdown_content = generate_markdown(messages, summary, project_name, session_id)

        # Write markdown file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        print(f"Created: {output_file}")
        return str(output_file)

    except Exception as e:
        print(f"Error processing {jsonl_path}: {e}")
        return None


# ============================================================================
# MESSAGE FILTERS - Determine what messages to include
# ============================================================================


def should_skip_message(msg: Dict[str, Any]) -> bool:
    """Determine if a message should be skipped."""
    message_content = msg.get("message", {})
    content = message_content.get("content", "")
    formatted_content = format_content(content)

    # Skip if content is blank after processing
    return not formatted_content.strip()


def extract_session_metadata(messages: List[Dict]) -> Dict[str, str]:
    """Extract session metadata for the header."""
    timestamps = [msg.get("timestamp") for msg in messages if msg.get("timestamp")]
    metadata = {}

    if timestamps:
        start_time = format_timestamp(timestamps[0])
        end_time = format_timestamp(timestamps[-1])
        start_parts = start_time.split()
        end_parts = end_time.split()

        if len(start_parts) > 1 and len(end_parts) > 1:
            metadata["time_range"] = f"⏰ {start_parts[1]} - {end_parts[1]}"

    return metadata


# ============================================================================
# OUTPUT FORMATTERS - Generate markdown for different sections
# ============================================================================


def format_header(summary: str, project_name: str, session_id: str, metadata: Dict[str, str]) -> str:
    """Format the markdown header section."""
    markdown = f"# 💬 {summary or 'Claude Code Session'}\n\n"

    # Build metadata line
    metadata_parts = [f"📁 **{project_name}**", f"🆔 `{session_id[:8]}...`"]
    if "time_range" in metadata:
        metadata_parts.append(metadata["time_range"])

    markdown += f"<sub>{' • '.join(metadata_parts)}</sub>\n\n"
    return markdown


def format_user_message(msg: Dict[str, Any]) -> str:
    """Format a user message section."""
    message_content = msg.get("message", {})
    content = message_content.get("content", "")
    formatted_content = format_content(content)
    timestamp = msg.get("timestamp", "")

    # Format timestamp for display
    formatted_time = format_timestamp(timestamp)
    time_parts = formatted_time.split()
    time_display = time_parts[1] if len(time_parts) > 1 else formatted_time

    # Build user message section
    markdown = f"### 👤 <sub> {time_display}</sub>\n\n"
    markdown += f"> **{formatted_content}**\n\n"

    return markdown


def format_assistant_message(msg: Dict[str, Any]) -> str:
    """Format an assistant message section."""
    message_content = msg.get("message", {})
    content = message_content.get("content", "")
    formatted_content = format_content(content)
    timestamp = msg.get("timestamp", "")

    # Format timestamp for display
    formatted_time = format_timestamp(timestamp)
    time_parts = formatted_time.split()
    time_display = time_parts[1] if len(time_parts) > 1 else formatted_time

    # Build assistant message section
    markdown = f"### 🤖 <sub> {time_display}</sub>\n\n"

    # Handle tool-heavy responses with collapsible sections
    if "Tool Used:" in formatted_content:
        markdown += format_tool_heavy_response(formatted_content)
    else:
        markdown += f"{formatted_content}\n\n"

    return markdown


def format_tool_heavy_response(formatted_content: str) -> str:
    """Format assistant responses containing tool usage."""
    markdown = ""
    parts = formatted_content.split("**Tool Used:**")

    if len(parts) > 1:
        # Regular response part
        if parts[0].strip():
            markdown += f"{parts[0].strip()}\n\n"

        # Tool usage parts with collapsible details
        for tool_part in parts[1:]:
            tool_lines = tool_part.split("\n")
            tool_name = tool_lines[0].strip() if tool_lines else "Unknown"

            markdown += f"<details>\n<summary><sub>🔧 <em>{tool_name}</em></sub></summary>\n\n"

            # Add JSON content if present
            json_start = tool_part.find("```json")
            if json_start != -1:
                json_end = tool_part.find("```", json_start + 7)
                if json_end != -1:
                    json_content = tool_part[json_start : json_end + 3]
                    markdown += f"{json_content}\n\n"

            # Add tool result if present
            result_start = tool_part.find("🔧Tool Result:")
            if result_start != -1:
                result_content = tool_part[result_start + 16 :].strip()
                if result_content.startswith("\n```"):
                    result_content = clean_tool_output(result_content)
                    markdown += f"**Result:**\n{result_content}\n\n"

            markdown += "</details>\n\n"
    else:
        markdown += f"{formatted_content}\n\n"

    return markdown


def generate_markdown(messages: List[Dict], summary: str, project_name: str, session_id: str) -> str:
    """Generate markdown content from messages using modular processors."""

    # Extract metadata
    metadata = extract_session_metadata(messages)

    # Generate header
    markdown = format_header(summary, project_name, session_id, metadata)

    # Process each message with appropriate formatter
    for i, msg in enumerate(messages):
        # Skip empty messages
        if should_skip_message(msg):
            continue

        msg_type = msg.get("type", "unknown")

        # Format message based on type
        if msg_type == "user":
            markdown += format_user_message(msg)
        elif msg_type == "assistant":
            markdown += format_assistant_message(msg)

        # Add separator between messages (except for last message)
        if i < len(messages) - 1:
            markdown += "---\n\n"

    return markdown


def find_jsonl_files(claude_dir: Path) -> List[Path]:
    """Find all JSONL files in Claude Code directory."""
    jsonl_files = []

    if not claude_dir.exists():
        print(f"Claude Code directory not found: {claude_dir}")
        return jsonl_files

    # Search in projects subdirectories
    projects_dir = claude_dir / "projects"
    if projects_dir.exists():
        for jsonl_file in projects_dir.rglob("*.jsonl"):
            jsonl_files.append(jsonl_file)

    return jsonl_files


def main():
    """Main function."""
    if len(sys.argv) != 2:
        print("Usage: ./get_cc_hist.py <output_folder>")
        sys.exit(1)

    output_folder = Path(sys.argv[1])
    claude_dir = Path.home() / ".claude"

    # Create output directory if it doesn't exist
    output_folder.mkdir(parents=True, exist_ok=True)

    print(f"Searching for JSONL files in: {claude_dir}")
    print(f"Output directory: {output_folder}")

    # Find all JSONL files
    jsonl_files = find_jsonl_files(claude_dir)

    if not jsonl_files:
        print("No JSONL files found in Claude Code directory.")
        return

    print(f"Found {len(jsonl_files)} JSONL files")

    # Process each file
    processed_count = 0
    skipped_count = 0

    for jsonl_path in jsonl_files:
        result = process_jsonl_file(jsonl_path, output_folder)
        if result == "skipped":
            skipped_count += 1
        elif result:
            processed_count += 1

    print(f"\nConversion complete!")
    print(f"Processed: {processed_count} files")
    print(f"Skipped (already exists): {skipped_count} files")
    print(f"Total JSONL files: {len(jsonl_files)}")


if __name__ == "__main__":
    main()
