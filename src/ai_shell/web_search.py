#!/usr/bin/env python

from typing import Dict, Any, Optional
from openai import OpenAI

from .theme import create_console, get_theme


class WebSearchManager:
    """Manager class for web search functionality using a configurable search model (e.g. perplexity/sonar-pro)"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.theme = get_theme(config)
        self.console = create_console(config)
        self.client = None
        self.search_model = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI-compatible client for the search model"""
        try:
            search_config = self.config.get("web_search", {})
            
            # Check if web search is enabled
            if not search_config.get("enabled", False):
                return
            
            # Get the search model name
            self.search_model = search_config.get("model", "")
            if not self.search_model:
                self.console.print("[warning]Warning: No search model configured. Web search disabled.[/warning]")
                return
            
            # Use search-specific API settings, or fall back to main API settings
            api_url = search_config.get("api_url", "") or self.config.get("api", {}).get("url", "")
            api_key = search_config.get("api_key", "") or self.config.get("api", {}).get("api_key", "")
            
            if not api_url or not api_key:
                self.console.print("[warning]Warning: API configuration missing for search model. Web search disabled.[/warning]")
                return
            
            self.client = OpenAI(
                api_key=api_key,
                base_url=api_url
            )
            
        except Exception as e:
            self.console.print(f"[error]Error initializing search model client: {e}[/error]")
    
    def is_available(self) -> bool:
        """Check if web search is available"""
        return self.client is not None and self.search_model is not None
    
    def search(self, query: str) -> Optional[str]:
        """Perform web search by querying the search model"""
        if not self.is_available():
            return None
        
        t = self.theme
        try:
            search_config = self.config.get("web_search", {})
            system_prompt = search_config.get("system_prompt", 
                "You are a web search assistant. Answer the user's question with current, accurate information. "
                "Include relevant sources, URLs, and specific details. Be thorough but concise."
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
            
            with self.console.status(f"[bold accent]Searching with {self.search_model}...[/bold accent]", spinner_style=t["accent"]):
                response = self.client.chat.completions.create(
                    model=self.search_model,
                    messages=messages,
                    stream=False
                )
            
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
            
            return None
            
        except Exception as e:
            self.console.print(f"[error]Web search error: {e}[/error]")
            return None
    
    def format_search_results(self, response: str) -> str:
        """Format search results for display - the response is already formatted text from the search model"""
        if not response:
            return "No search results available."
        return response
