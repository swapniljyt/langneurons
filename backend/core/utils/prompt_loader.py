from pathlib import Path
import os

class PromptLoader:
    """
    Utility class to load system prompts from the prompts directory.
    Uses 'str.format' syntax for templating.
    """
    
    _PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

    @classmethod
    def get_prompt(cls, relative_path: str, **kwargs) -> str:
        """
        Load a prompt file and optionally format it with kwargs.
        
        Args:
            relative_path (str): Path relative to brain_src/prompts/ (e.g. 'system/activation.md')
            **kwargs: Variables to inject into the prompt template.
            
        Returns:
            str: The loaded (and formatted) prompt string.
        """
        prompt_path = cls._PROMPTS_DIR / relative_path
        
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
            
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
            
        try:
            if kwargs:
                return template.format(**kwargs)
            return template
        except KeyError as e:
            raise KeyError(f"Missing key for prompt template '{relative_path}': {e}")
        except ValueError as e:
            raise ValueError(f"Error formatting prompt '{relative_path}': {e}")

# Example usage:
# prompt = PromptLoader.get_prompt("system/context_check.md")
