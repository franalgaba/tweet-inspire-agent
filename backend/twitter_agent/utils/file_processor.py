"""Process text files from content directory for context."""

import os
from pathlib import Path
from typing import Optional


class FileProcessor:
    """Process and extract content from text files."""

    SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".rst"}

    def __init__(self, content_dir: str = "content"):
        """
        Initialize file processor.

        Args:
            content_dir: Directory containing content files
        """
        self.content_dir = Path(content_dir)

    def process_directory(self) -> dict[str, str]:
        """
        Process all text files in the content directory.

        Returns:
            Dictionary mapping filenames to their content
        """
        if not self.content_dir.exists():
            return {}

        content_map = {}
        for file_path in self.content_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    # Use relative path as key
                    rel_path = file_path.relative_to(self.content_dir)
                    content_map[str(rel_path)] = content
                except Exception as e:
                    # Skip files that can't be read
                    continue

        return content_map

    def get_content_summary(self, max_chars: int = 5000) -> str:
        """
        Get a summary of all content files.

        Args:
            max_chars: Maximum characters to include in summary

        Returns:
            Combined content summary
        """
        content_map = self.process_directory()
        if not content_map:
            return "No content files found in directory."

        summary_parts = []
        current_length = 0

        for filename, content in content_map.items():
            if current_length >= max_chars:
                break

            file_summary = f"\n--- Content from {filename} ---\n{content}\n"
            if current_length + len(file_summary) > max_chars:
                # Truncate last file
                remaining = max_chars - current_length
                file_summary = file_summary[:remaining] + "\n[... truncated]"
                summary_parts.append(file_summary)
                break
            else:
                summary_parts.append(file_summary)
                current_length += len(file_summary)

        return "".join(summary_parts)

    def extract_interests(self) -> list[str]:
        """
        Extract common topics/interests from content files.

        This is a simple implementation. In production, you might use
        NLP techniques like keyword extraction or topic modeling.

        Returns:
            List of identified interests/topics
        """
        content_map = self.process_directory()
        if not content_map:
            return []

        # Simple keyword extraction (can be enhanced with NLP)
        all_text = " ".join(content_map.values()).lower()

        # Common interest keywords (this could be more sophisticated)
        common_interests = [
            "technology",
            "programming",
            "ai",
            "machine learning",
            "python",
            "javascript",
            "web development",
            "design",
            "productivity",
            "business",
            "startup",
            "marketing",
            "content",
            "writing",
            "reading",
            "travel",
            "food",
            "fitness",
            "health",
            "music",
            "art",
            "photography",
        ]

        found_interests = []
        for interest in common_interests:
            if interest in all_text:
                found_interests.append(interest)

        return found_interests

    def get_files_count(self) -> int:
        """Get the number of content files found."""
        return len(self.process_directory())

