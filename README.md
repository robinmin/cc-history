# cc-history - Claude Code History Converter

A tiny python script to convert Claude Code's conversation history into Markdown files.

## Usage
Converts Claude Code JSONL files to organized markdown files. Usage:
```bash
./get_cc_hist.py <output_folder>
```

## Architecture:
The script is now organized into 4 clear functional sections:

### 1. 🔧 UTILITY FUNCTIONS

Basic helpers for file and data processing:

- sanitize_filename() - Safe filename generation
- format_timestamp() - Time formatting
- extract_project_name() - Project name extraction
- clean_tool_output() - ANSI code and formatting removal

### 2. 📝 CONTENT PROCESSORS

Specialized handlers for different message content types:

- process_text_content() - Plain text processing
- process_tool_use_content() - Tool usage formatting
- process_tool_result_content() - Tool result cleaning
- format_content() - Main content router

### 3. 🎯 MESSAGE FILTERS

Logic to determine what content to include/skip:

- should_skip_message() - Empty message filtering
- extract_session_metadata() - Header metadata extraction

### 4. 🎨 OUTPUT FORMATTERS

Markdown generation for different sections:

- format_header() - Session header generation
- format_user_message() - User message styling
- format_assistant_message() - Assistant response styling
- format_tool_heavy_response() - Tool collapsible sections
- generate_markdown() - Main orchestrator

### 5. 🚀 MAIN PIPELINE

File processing orchestration:

- process_jsonl_file() - Single file conversion
- find_jsonl_files() - File discovery
- main() - CLI interface

🎯 Benefits of This Architecture

- ✅ Easy to extend: Want a new content type? Add a processor function
- ✅ Easy to modify: Need different filtering? Update the filters section
- ✅ Easy to customize: Want different styling? Modify the formatters
- ✅ Easy to debug: Each section has clear responsibilities
- ✅ Easy to test: Individual functions can be tested separately

The script maintains all previous functionality while being much more maintainable and extensible! 🚀
