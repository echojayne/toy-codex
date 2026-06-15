from pathlib import Path
from itertools import islice
from tools import ToolDefinition

MAX_FILE_ROWS = 200
MAX_FILE_CHARS = 20_000

READ_FILE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "File path relative to the workspace root"
        },
        "line_index": {"type": "integer", "minimum": 0},
        "way": {
            "type": "string",
            "enum": ["head", "tail", "middle"],
        },
    },
    "required": ["path"],
    "additionalProperties": False,
}

MAX_LIST_ENTRIES = 200

LIST_FILES_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Directory path relative to the workspace root"
        },
        "depth": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5,
            "description": "Maximum directory traversal depth",
        },
    },
    "required": [],
    "additionalProperties": False,
}

MAX_SEARCH_RESULTS = 100
MAX_SEARCH_FILES = 1_000
MAX_SEARCH_FILE_BYTES = 1_000_000
MAX_MATCH_LINE_CHARS = 500

SEARCH_TEXT_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Literal text to search for",
        },
        "path": {
            "type": "string",
            "description": "File or directory relative to the workspace root",
        },
        "case_sensitive": {
            "type": "boolean",
            "description": "Whether matching is case-sensitive",
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}

def create_read_file_tool(workspace_root: Path) -> ToolDefinition:
    if not workspace_root.is_dir():
        raise ValueError(f"Workspace root {workspace_root} is not a directory")
    
    def read_file_handler(arguments: dict[str, object]) -> str:

        path_value = arguments.get("path")
        line_index = arguments.get("line_index", 0)
        way = arguments.get("way", "head")

        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError("path must be a non-empty string")

        if not isinstance(line_index, int) or isinstance(line_index, bool):
            raise ValueError("line_index must be an integer")

        if line_index < 0:
            raise ValueError("line_index must not be negative")

        if not isinstance(way, str):
            raise ValueError("way must be a string")

        root = workspace_root.resolve()
        target = (root / path_value).resolve()

        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValueError("Path is outside the workspace") from error

        if not target.is_file():
            raise ValueError(f"File not found: {target}")

        if way == "head":
            start = line_index
            end = line_index + MAX_FILE_ROWS

        elif way == "tail":
            start = max(0, line_index - MAX_FILE_ROWS + 1)
            end = line_index + 1

        elif way == "middle":
            before = MAX_FILE_ROWS // 2
            start = max(0, line_index - before)
            end = start + MAX_FILE_ROWS

        else:
            raise ValueError("way must be 'head', 'tail', or 'middle'")

        with target.open(encoding="utf-8") as file:
            selected_lines = islice(file, start, end)

            output: list[str] = []
            current_chars = 0
            truncated = False

            for actual_index, line in enumerate(selected_lines, start=start):
                numbered_line = f"{actual_index + 1}: {line}"
                remaining = MAX_FILE_CHARS - current_chars

                if len(numbered_line) > remaining:
                    output.append(numbered_line[:remaining])
                    truncated = True
                    break

                output.append(numbered_line)
                current_chars += len(numbered_line)

            if truncated:
                output.append("\n[Output truncated]")

            return "".join(output)

    return ToolDefinition(
        name="read_file",
        description="Read a text file inside the workspace",
        parameters=READ_FILE_PARAMETERS,
        handler=read_file_handler,
    )



def create_list_files_tool(workspace_root: Path) -> ToolDefinition:

    if not workspace_root.is_dir():
        raise ValueError(f"Workspace root {workspace_root} is not a directory") 

    def list_files_handler(arguments: dict[str, object]) -> str:

        path_value = arguments.get("path", ".")
        depth = arguments.get("depth", 2)

        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError("path must be a non-empty string")
        
        if not isinstance(depth, int) or isinstance(depth, bool):
            raise ValueError("depth must be an integer")

        if not 1 <= depth <= 5:
            raise ValueError("depth must be between 1 and 5")

        root = workspace_root.resolve()
        target = (root / path_value).resolve()

        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValueError("Path is outside the workspace") from error

        if not target.is_dir():
            raise ValueError(f"Directory not found: {target}")

        entries: list[str] = []
        scan_limit = MAX_LIST_ENTRIES + 1

        def walk(directory: Path, current_depth: int) -> None:
            if current_depth > depth or len(entries) >= scan_limit:
                return

            children = sorted(directory.iterdir(), key=lambda item: item.name.casefold())

            for child in children:
                if len(entries) >= scan_limit:
                    return

                relative_path = child.relative_to(root)

                if child.is_symlink():
                    entries.append(f"{relative_path} -> [symlink]")
                    continue

                if child.is_dir():
                    entries.append(f"{relative_path}/")
                    walk(child, current_depth + 1)
                else:
                    entries.append(str(relative_path))

        walk(target, 1)        

        if not entries:
            return "[Directory is empty]"

        truncated = len(entries) > MAX_LIST_ENTRIES
        entries = entries[:MAX_LIST_ENTRIES]

        if truncated:
            entries.append("[Output truncated]")

        return "\n".join(entries)

    return ToolDefinition(
        name="list_files",
        description="List files and directories inside the workspace",
        parameters=LIST_FILES_PARAMETERS,
        handler=list_files_handler,
    )

def iter_files(path: Path):
    if path.is_symlink():
        return

    if path.is_file():
        yield path
        return

    for child in sorted(path.iterdir(), key=lambda item: item.name.casefold()):
        if child.is_symlink():
            continue
        if child.is_dir():
            yield from iter_files(child)
        elif child.is_file():
            yield child

def create_search_text_tool(workspace_root: Path) -> ToolDefinition:

    if not workspace_root.is_dir():
        raise ValueError(f"Workspace root {workspace_root} is not a directory")

    def search_text_handle(arguments: dict[str, object]) -> str:

        query = arguments.get("query")
        path_value = arguments.get("path", ".")
        case_sensitive = arguments.get("case_sensitive", False)

        if not isinstance(query, str) or not query:
            raise ValueError("query must be a non-empty string")

        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError("path must be a non-empty string")

        if not isinstance(case_sensitive, bool):
            raise ValueError("case_sensitive must be a boolean")

        needle = query if case_sensitive else query.casefold()

        root = workspace_root.resolve()
        target = (root / path_value).resolve()
        file_path = target
        results: list[str] = []

        with file_path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                candidate = line if case_sensitive else line.casefold()

                if needle not in candidate:
                    continue

                displayed_line = line.rstrip("\r\n")
                if len(displayed_line) > MAX_MATCH_LINE_CHARS:
                    displayed_line = displayed_line[:MAX_MATCH_LINE_CHARS] + "..."

                relative_path = file_path.relative_to(workspace_root)
                results.append(
                    f"{relative_path}:{line_number}: {displayed_line}"
                )

                if len(results) >= MAX_SEARCH_RESULTS:
                    truncated = True
                    return

            if not results:
                return "[No matches found]"

            if truncated:
                results.append("[Output truncated]")

            return "\n".join(results)

    return ToolDefinition(
        name="search_text",
        description="Search text",
        parameters=SEARCH_TEXT_PARAMETERS,
        handler=search_text_handle,
    )