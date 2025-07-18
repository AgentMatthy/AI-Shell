#!/usr/bin/env python

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm, Prompt

class ConversationManager:
    """Manages conversation persistence, auto-save, and recovery"""
    
    def __init__(self, config: Dict, ui_manager=None):
        self.config = config
        self.console = Console()
        self.ui_manager = ui_manager
        self.incognito_mode = False
        
        # Configuration settings
        conv_settings = config.get("conversations", {})
        self.auto_save_interval = conv_settings.get("auto_save_interval", 5)
        self.max_recent = conv_settings.get("max_recent", 10)
        self.resume_on_startup = conv_settings.get("resume_on_startup", True)
        
        # Storage paths
        storage_path = conv_settings.get("storage_path", "~/.ai-shell/conversations")
        self.base_path = Path(storage_path).expanduser()
        self.active_path = self.base_path / "active.json"
        self.recent_path = self.base_path / "recent"
        self.saved_path = self.base_path / "saved"
        self.archive_path = self.base_path / "archive"
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Tracking variables
        self.interaction_count = 0
        self.current_session = {
            "id": self._generate_session_id(),
            "started_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "payload": [],
            "metadata": {
                "original_request": "",
                "status": "active",
                "summary": "",
                "last_used": datetime.now().isoformat()
            }
        }
    
    def _ensure_directories(self):
        """Create necessary directories if they don't exist"""
        for path in [self.base_path, self.recent_path, self.saved_path, self.archive_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID"""
        return f"session_{int(time.time())}"
    
    def _get_session_summary(self, messages: List[Dict]) -> str:
        """Generate a brief summary of the conversation based on first user message"""
        if not messages:
            return "Empty conversation"
        
        # Find the first user message to use as summary
        for message in messages:
            if message.get("role") == "user":
                content = message.get("content", "")
                # Truncate to first 50 characters for display
                if len(content) > 50:
                    return content[:47] + "..."
                return content
        
        return "System-only conversation"
    
    def _save_session_to_file(self, filepath: Path, session: Dict):
        """Save session data to a file"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(session, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.console.print(f"[red]Error saving session: {e}[/red]")
    
    def _load_session_from_file(self, filepath: Path) -> Optional[Dict]:
        """Load session data from a file"""
        try:
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.console.print(f"[red]Error loading session: {e}[/red]")
        return None
    
    def check_for_resume(self) -> Optional[Dict]:
        """Check if there's an active conversation to resume"""
        if not self.resume_on_startup:
            return None
        
        session = self._load_session_from_file(self.active_path)
        if not session or not session.get("payload"):
            return None
        
        # Check if session is recent (within 24 hours)
        try:
            last_updated = datetime.fromisoformat(session.get("last_updated", ""))
            hours_ago = (datetime.now() - last_updated).total_seconds() / 3600
            
            if hours_ago > 24:
                return None
            
            # Show resume prompt
            summary = session.get("metadata", {}).get("summary", "")
            if not summary:
                summary = self._get_session_summary(session.get("payload", []))
            
            time_str = "just now" if hours_ago < 0.1 else f"{int(hours_ago)} hour{'s' if hours_ago > 1 else ''} ago"
            
            self.console.print(f"\n[yellow]Found previous conversation from {time_str}:[/yellow]")
            self.console.print(f"[dim]{summary}[/dim]")
            
            if Confirm.ask("Resume previous session?", default=True):
                return session
                
        except Exception as e:
            self.console.print(f"[red]Error checking resume: {e}[/red]")
        
        return None
    
    def resume_session(self, session: Dict) -> List[Dict]:
        """Resume a conversation session"""
        self.current_session = session
        self.current_session["metadata"]["status"] = "resumed"
        self.current_session["last_updated"] = datetime.now().isoformat()
        self.current_session["metadata"]["last_used"] = datetime.now().isoformat()
        
        payload = session.get("payload", [])
        
        # Show brief context
        self.console.print("[green]✓ Session resumed successfully[/green]")
        if payload:
            original_request = session.get("metadata", {}).get("original_request", "")
            if original_request:
                self.console.print(f"[dim]Original request: {original_request}[/dim]")
        
        # Display the conversation messages if ui_manager is available
        if self.ui_manager and payload:
            self.ui_manager.display_conversation_messages(payload)
        
        return payload
    
    def update_payload(self, payload: List[Dict], original_request: str = ""):
        """Update current session with new payload data"""
        self.current_session["payload"] = payload
        self.current_session["last_updated"] = datetime.now().isoformat()
        
        # Always update last_used when payload is updated (active conversation)
        self.current_session["metadata"]["last_used"] = datetime.now().isoformat()
        
        if original_request and not self.current_session["metadata"]["original_request"]:
            self.current_session["metadata"]["original_request"] = original_request
        
        # Update summary
        self.current_session["metadata"]["summary"] = self._get_session_summary(payload)
        
        self.interaction_count += 1
        
        # Auto-save if interval reached
        if self.interaction_count % self.auto_save_interval == 0:
            self._auto_save()
    
    def set_incognito_mode(self, incognito_mode: bool):
        """Set incognito mode state"""
        self.incognito_mode = incognito_mode
    
    def _auto_save(self):
        """Automatically save the current session"""
        # Skip saving in incognito mode
        if self.incognito_mode:
            return
        self._save_session_to_file(self.active_path, self.current_session)
    
    def save_conversation(self, name: Optional[str] = None) -> bool:
        """Save current conversation with optional name"""
        if self.incognito_mode:
            self.console.print("[yellow]Cannot save conversations in incognito mode[/yellow]")
            return False
            
        if not self.current_session["payload"]:
            self.console.print("[yellow]No conversation to save[/yellow]")
            return False
        
        if not name:
            name = Prompt.ask("Enter name for this conversation", 
                            default=f"conversation_{int(time.time())}")
        
        # Sanitize filename
        safe_name = "".join(c for c in name if c.isalnum() or c in ('-', '_', ' ')).strip()
        safe_name = safe_name.replace(' ', '_')
        
        filepath = self.saved_path / f"{safe_name}.json"
        
        # Check if file exists
        if filepath.exists():
            if not Confirm.ask(f"Conversation '{safe_name}' already exists. Overwrite?"):
                return False
        
        # Save the conversation
        save_session = self.current_session.copy()
        save_session["metadata"]["status"] = "saved"
        save_session["metadata"]["saved_at"] = datetime.now().isoformat()
        save_session["metadata"]["saved_name"] = safe_name
        
        self._save_session_to_file(filepath, save_session)
        self.console.print(f"[green]✓ Conversation saved as '{safe_name}'[/green]")
        return True
    
    def load_conversation(self, name: Optional[str] = None) -> Optional[List[Dict]]:
        """Load a saved conversation"""
        if not name:
            # Show available conversations
            self.list_conversations()
            name = Prompt.ask("Enter conversation name to load")
        
        if not name:
            return None
        
        # Try to find the conversation file
        safe_name = "".join(c for c in name if c.isalnum() or c in ('-', '_', ' ')).strip()
        safe_name = safe_name.replace(' ', '_')
        
        filepath = self.saved_path / f"{safe_name}.json"
        
        if not filepath.exists():
            self.console.print(f"[red]Conversation '{name}' not found[/red]")
            return None
        
        session = self._load_session_from_file(filepath)
        if not session:
            return None
        
        # Archive current session if it has content
        if self.current_session["payload"]:
            self._move_to_recent()
        
        # Load the new session
        self.current_session = session
        self.current_session["metadata"]["status"] = "loaded"
        self.current_session["last_updated"] = datetime.now().isoformat()
        self.current_session["metadata"]["last_used"] = datetime.now().isoformat()
        
        payload = session.get("payload", [])
        self.console.print(f"[green]✓ Loaded conversation '{name}'[/green]")
        
        # Display the conversation messages if ui_manager is available
        if self.ui_manager and payload:
            self.ui_manager.display_conversation_messages(payload)
        
        return payload
    
    def list_conversations(self):
        """Display all saved conversations"""
        table = Table(title="Saved Conversations")
        table.add_column("Name", style="cyan")
        table.add_column("Date", style="dim")
        table.add_column("Summary", style="white")
        
        # Get saved conversations
        saved_files = list(self.saved_path.glob("*.json"))
        saved_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        for filepath in saved_files:
            session = self._load_session_from_file(filepath)
            if session:
                name = filepath.stem
                saved_at = session.get("metadata", {}).get("saved_at", "")
                if saved_at:
                    try:
                        date_obj = datetime.fromisoformat(saved_at)
                        date_str = date_obj.strftime("%Y-%m-%d %H:%M")
                    except:
                        date_str = "Unknown"
                else:
                    date_str = "Unknown"
                
                summary = session.get("metadata", {}).get("summary", "")
                table.add_row(name, date_str, summary)
        
        if not saved_files:
            self.console.print("[yellow]No saved conversations found[/yellow]")
        else:
            self.console.print(table)

    def list_recent_conversations(self):
        """Display recent conversations with easy-to-use indices"""
        table = Table(title="Recent Conversations")
        table.add_column("#", style="yellow", width=3)
        table.add_column("Last Used", style="dim")
        table.add_column("Summary", style="white")
        table.add_column("Messages", style="cyan", width=8)
        
        # Get recent conversations
        recent_files = list(self.recent_path.glob("*.json"))
        recent_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not recent_files:
            self.console.print("[yellow]No recent conversations found[/yellow]")
            return []
        
        # Store file mapping for loading
        file_mapping = []
        
        for i, filepath in enumerate(recent_files, 1):
            session = self._load_session_from_file(filepath)
            if session:
                file_mapping.append(filepath)
                
                # Get last used time (prefer last_used over last_updated)
                last_used = session.get("metadata", {}).get("last_used", "")
                if not last_used:
                    last_used = session.get("last_updated", "")
                
                if last_used:
                    try:
                        date_obj = datetime.fromisoformat(last_used)
                        now = datetime.now()
                        time_diff = now - date_obj
                        
                        if time_diff.days > 0:
                            date_str = f"{time_diff.days}d ago"
                        elif time_diff.seconds > 3600:
                            hours = time_diff.seconds // 3600
                            date_str = f"{hours}h ago"
                        elif time_diff.seconds > 60:
                            minutes = time_diff.seconds // 60
                            date_str = f"{minutes}m ago"
                        else:
                            date_str = "just now"
                    except:
                        date_str = "unknown"
                else:
                    date_str = "unknown"
                
                summary = session.get("metadata", {}).get("summary", "No summary")
                if len(summary) > 50:
                    summary = summary[:47] + "..."
                
                message_count = len(session.get("payload", []))
                
                table.add_row(str(i), date_str, summary, str(message_count))
        
        self.console.print(table)
        self.console.print(f"\n[dim]Use '/load <number>' to load a conversation by its index number[/dim]")
        return file_mapping
    
    def load_recent_conversation(self, index: int) -> Optional[List[Dict]]:
        """Load a recent conversation by index from the list"""
        recent_files = list(self.recent_path.glob("*.json"))
        recent_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not recent_files:
            self.console.print("[yellow]No recent conversations found[/yellow]")
            return None
        
        if index < 1 or index > len(recent_files):
            self.console.print(f"[red]Invalid index. Please choose a number between 1 and {len(recent_files)}[/red]")
            return None
        
        filepath = recent_files[index - 1]  # Convert to 0-based index
        session = self._load_session_from_file(filepath)
        
        if not session:
            self.console.print("[red]Failed to load conversation[/red]")
            return None
        
        # Archive current session if it has content
        if self.current_session["payload"]:
            self._move_to_recent()
        
        # Load the recent session
        self.current_session = session
        self.current_session["metadata"]["status"] = "loaded"
        self.current_session["last_updated"] = datetime.now().isoformat()
        self.current_session["metadata"]["last_used"] = datetime.now().isoformat()
        
        summary = session.get("metadata", {}).get("summary", "No summary")
        self.console.print(f"[green]✓ Loaded recent conversation: {summary}[/green]")
        
        payload = session.get("payload", [])
        # Display the conversation messages if ui_manager is available
        if self.ui_manager and payload:
            self.ui_manager.display_conversation_messages(payload)
        
        return payload
    
    def archive_conversation(self) -> bool:
        """Archive the current conversation"""
        if not self.current_session["payload"]:
            self.console.print("[yellow]No conversation to archive[/yellow]")
            return False
        
        # Move to archive
        archive_session = self.current_session.copy()
        archive_session["metadata"]["status"] = "archived"
        archive_session["metadata"]["archived_at"] = datetime.now().isoformat()
        
        filename = f"{self.current_session['id']}.json"
        self._save_session_to_file(self.archive_path / filename, archive_session)
        
        # Clear current session
        self._start_new_session()
        
        self.console.print("[green]Conversation archived[/green]")
        return True
    
    def delete_conversation(self, name: Optional[str] = None) -> bool:
        """Delete a saved conversation"""
        if not name:
            self.list_conversations()
            name = Prompt.ask("Enter conversation name to delete")
        
        if not name:
            return False
        
        safe_name = "".join(c for c in name if c.isalnum() or c in ('-', '_', ' ')).strip()
        safe_name = safe_name.replace(' ', '_')
        
        filepath = self.saved_path / f"{safe_name}.json"
        
        if not filepath.exists():
            self.console.print(f"[red]Conversation '{name}' not found[/red]")
            return False
        
        if Confirm.ask(f"Delete conversation '{name}'?", default=False):
            try:
                filepath.unlink()
                self.console.print(f"[green]✓ Deleted conversation '{name}'[/green]")
                return True
            except Exception as e:
                self.console.print(f"[red]Error deleting conversation: {e}[/red]")
        
        return False
    
    def _move_to_recent(self):
        """Move current session to recent folder"""
        if not self.current_session["payload"]:
            return
        
        # Skip saving in incognito mode
        if self.incognito_mode:
            return
        
        recent_session = self.current_session.copy()
        recent_session["metadata"]["status"] = "recent"
        recent_session["metadata"]["moved_to_recent_at"] = datetime.now().isoformat()
        
        filename = f"{self.current_session['id']}.json"
        self._save_session_to_file(self.recent_path / filename, recent_session)
        
        # Clean up old recent files
        self._cleanup_recent()
    
    def _cleanup_recent(self):
        """Keep only the most recent conversations"""
        recent_files = list(self.recent_path.glob("*.json"))
        if len(recent_files) > self.max_recent:
            # Sort by modification time and remove oldest
            recent_files.sort(key=lambda x: x.stat().st_mtime)
            for old_file in recent_files[:-self.max_recent]:
                try:
                    old_file.unlink()
                except (OSError, PermissionError) as e:
                    self.console.print(f"[yellow]Warning: Could not delete old conversation file {old_file.name}: {e}[/yellow]")
    
    def _start_new_session(self):
        """Start a new conversation session"""
        self.current_session = {
            "id": self._generate_session_id(),
            "started_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "payload": [],
            "metadata": {
                "original_request": "",
                "status": "active",
                "summary": "",
                "last_used": datetime.now().isoformat()
            }
        }
        self.interaction_count = 0
    
    def clear_conversation(self):
        """Clear current conversation and start fresh"""
        # Move current to recent if it has content
        if self.current_session["payload"]:
            self._move_to_recent()
        
        # Start new session
        self._start_new_session()
        
        # Clear active file
        if self.active_path.exists():
            try:
                self.active_path.unlink()
            except:
                pass
    
    def save_and_exit(self):
        """Save conversation and prepare for exit"""
        if self.current_session["payload"]:
            # Move to recent
            self._move_to_recent()
            
            # Clear active file
            if self.active_path.exists():
                try:
                    self.active_path.unlink()
                except:
                    pass
        
        self.console.print("[green]Conversation saved[/green]")
    
    def get_status_info(self) -> Dict:
        """Get current conversation status information"""
        last_used = self.current_session["metadata"].get("last_used", "")
        if last_used:
            try:
                date_obj = datetime.fromisoformat(last_used)
                last_used_formatted = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except:
                last_used_formatted = last_used
        else:
            last_used_formatted = "Never"
        
        return {
            "session_id": self.current_session["id"],
            "started_at": self.current_session["started_at"],
            "last_used": last_used_formatted,
            "message_count": len(self.current_session["payload"]),
            "interactions": self.interaction_count,
            "status": self.current_session["metadata"]["status"],
            "original_request": self.current_session["metadata"]["original_request"]
        }
