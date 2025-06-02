# combine_scripts.py

import argparse
from pathlib import Path
import sys

# Default directories to exclude from search
DEFAULT_EXCLUDE_DIRS = {
    '.venv',
    'env',
    '__pycache__',
    '.pytest_cache',
    'output_scripts',
    'checkpoints'
}

# Файлы каких расширений включать в сборку
INCLUDE_EXTS = {'.py', '.md', '.yaml', '.yml', '.txt'}

def find_files(root: Path, exclude_dirs: set[str], include_exts: set[str]) -> list[Path]:
    """
    Recursively find files with given extensions in root, 
    excluding any in exclude_dirs and this script itself.
    Returns a sorted list of file paths.
    """
    files = []
    print(f"\n🔍 Scanning directory: {root}")
    print(f"📁 Excluding directories: {exclude_dirs}\n")
    print(f"📄 Including extensions: {include_exts}\n")
    this_script = Path(__file__).resolve()
    
    for file in sorted(root.rglob('*')):
        # Пропуск по расширению
        if file.suffix not in include_exts:
            continue
        # Пропуск из exclude директорий
        file_str = str(file)
        if any(f"/{ex}/" in file_str or file_str.startswith(f"{ex}/") for ex in exclude_dirs):
            print(f"❌ Excluded (dir): {file_str}")
            continue
        # Пропуск самого себя
        if file.resolve() == this_script:
            print(f"❌ Excluded (self): {file_str}")
            continue
        print(f"✅ Included: {file_str}")
        files.append(file)
    print(f"\n📊 Found {len(files)} files")
    return files

def main():
    parser = argparse.ArgumentParser(
        description="Combine project files (.py, .md, .yaml) into one file with auto-numbered headings."
    )
    parser.add_argument(
        '-r', '--root', type=Path, default=Path.cwd(),
        help='Project root directory to scan'
    )
    parser.add_argument(
        '-o', '--output', type=Path, default=Path('combined_scripts.py'),
        help='Path for the combined output file'
    )
    parser.add_argument(
        '-e', '--exclude', nargs='*', default=list(DEFAULT_EXCLUDE_DIRS),
        help='List of directory names to exclude'
    )
    parser.add_argument(
        '-x', '--exts', nargs='*', default=list(INCLUDE_EXTS),
        help='List of file extensions to include (e.g., .py .md .yaml)'
    )
    args = parser.parse_args()

    root = args.root.resolve()
    output_path = args.output
    exclude_dirs = set(args.exclude)
    include_exts = set(args.exts)

    files = find_files(root, exclude_dirs, include_exts)
    if not files:
        print("No matching files found.", file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open('w', encoding='utf-8') as fout:
        fout.write("# Combined project files\n\n")
        for idx, file in enumerate(files, start=1):
            rel = file.relative_to(root)
            fout.write(f"# {idx:03d} - {rel}\n")
            fout.write(file.read_text(encoding='utf-8'))
            fout.write("\n\n")

    print(f"✅ Combined {len(files)} files into {output_path}")

if __name__ == '__main__':
    main()
