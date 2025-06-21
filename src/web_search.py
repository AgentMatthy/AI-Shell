#!/usr/bin/env python

import json
from typing import Dict, Any, Optional
from rich.console import Console


class WebSearchManager:
    """Manager class for web search functionality using Tavily"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.console = Console()
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Tavily client if API key is configured"""
        try:
            tavily_config = self.config.get("tavily", {})
            api_key = tavily_config.get("api_key")
            
            if not api_key or api_key == "your_tavily_api_key_here":
                self.console.print("[yellow]Warning: Tavily API key not configured. Web search disabled.[/yellow]")
                return
            
            from tavily import TavilyClient
            self.client = TavilyClient(api_key)
            
        except ImportError:
            self.console.print("[yellow]Warning: Tavily package not installed. Run 'pip install tavily-python' to enable web search.[/yellow]")
        except Exception as e:
            self.console.print(f"[red]Error initializing Tavily client: {e}[/red]")
    
    def is_available(self) -> bool:
        """Check if web search is available"""
        return self.client is not None
    
    def search(self, query: str, max_results: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Perform web search using Tavily"""
        if not self.is_available():
            return None
        
        try:
            # Get configuration settings
            tavily_config = self.config.get("tavily", {})
            
            # Use config values or defaults
            search_max_results = max_results or tavily_config.get("max_results", 5)
            search_depth = tavily_config.get("search_depth", "basic")
            include_answer = tavily_config.get("include_answer", True)
            include_raw_content = tavily_config.get("include_raw_content", False)
            include_domains = tavily_config.get("include_domains", [])
            exclude_domains = tavily_config.get("exclude_domains", [])
            
            with self.console.status(f"[bold cyan]Searching...[/bold cyan]", spinner_style="cyan"):
                # Build search parameters
                search_params = {
                    "query": query,
                    "max_results": search_max_results,
                    "search_depth": search_depth,
                    "include_answer": include_answer,
                    "include_raw_content": include_raw_content
                }
                
                # Add domain filters if specified
                if include_domains:
                    search_params["include_domains"] = include_domains
                if exclude_domains:
                    search_params["exclude_domains"] = exclude_domains
                
                response = self.client.search(**search_params)
            
            return response
            
        except Exception as e:
            self.console.print(f"[red]Web search error: {e}[/red]")
            return None
    
    def format_search_results(self, response: Dict[str, Any]) -> str:
        """Format search results for display"""
        if not response:
            return "No search results available."
        
        formatted = []
        
        # Add the answer if available
        if response.get("answer"):
            formatted.append(f"**Answer:** {response['answer']}\n")
        
        # Add search results
        results = response.get("results", [])
        if results:
            formatted.append("**Search Results:**")
            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                url = result.get("url", "")
                content = result.get("content", "No content available")
                
                # Truncate content if too long
                if len(content) > 300:
                    content = content[:300] + "..."
                
                formatted.append(f"\n{i}. **{title}**")
                formatted.append(f"   URL: {url}")
                formatted.append(f"   {content}")
        
        return "\n".join(formatted)

