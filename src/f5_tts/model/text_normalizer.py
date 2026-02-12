
import os
import logging
from typing import Optional
from pathlib import Path

# Try importing WeTextProcessing
# Note: The package name on PyPI is WeTextProcessing, but it installs as 'tn' and 'itn' modules
try:
    from tn.chinese.normalizer import Normalizer
    _HAS_WETEXTPROCESSING = True
except ImportError:
    _HAS_WETEXTPROCESSING = False

logger = logging.getLogger("f5tts")

class TextNormalizer:
    _instance = None
    _normalizer = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TextNormalizer, cls).__new__(cls)
        return cls._instance

    def initialize(self, cache_dir: Optional[str] = None, language: str = "zh"):
        """Initialize the WeTextProcessing Normalizer."""
        if not _HAS_WETEXTPROCESSING:
            logger.warning("WeTextProcessing not installed. Text normalization disabled.")
            return

        if self._normalizer is not None:
            return

        try:
            if cache_dir is None:
                # Use a default cache directory within the package or user home
                cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "f5_tts", "tn_cache")
            
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Initializing WeTextProcessing Normalizer (lang={language})...")
            # The Normalizer in tn.chinese.normalizer does not accept language argument
            self._normalizer = Normalizer(cache_dir=cache_dir)
            logger.info("WeTextProcessing Normalizer initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize WeTextProcessing: {e}")
            self._normalizer = None

    def normalize(self, text: str) -> str:
        """
        Normalize text using WeTextProcessing (e.g., convert numbers to Chinese characters).
        If initialization failed or library missing, returns original text.
        """
        if self._normalizer is None:
            return text
        
        try:
            return self._normalizer.normalize(text)
        except Exception as e:
            logger.warning(f"Text normalization failed for input '{text}': {e}")
            return text

# Global helper function
_global_normalizer = TextNormalizer()

def normalize_text(text: str) -> str:
    """Global function to normalize text."""
    # Ensure initialized with defaults if not already
    if _HAS_WETEXTPROCESSING and _global_normalizer._normalizer is None:
        _global_normalizer.initialize()
    
    return _global_normalizer.normalize(text)
