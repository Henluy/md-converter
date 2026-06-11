"""Markdown post-processing pipeline.

All converters emit raw markdown that often carries HTML residue (Pandoc
EPUB output is a notorious offender). The processors here turn that raw
output into clean GitHub-flavoured markdown before it's written to disk.
"""

from app.processors.markdown_cleaner import CleanResult, clean_markdown
from app.processors.quality import QualityAssessment, assess_quality

__all__ = ["CleanResult", "QualityAssessment", "assess_quality", "clean_markdown"]
