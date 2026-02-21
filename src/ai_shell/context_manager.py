#!/usr/bin/env python

"""Context management for AI Shell - handles message ID tracking, pruning, distilling, and truncation"""

import re
from rich.console import Console

from .constants import (
    DEFAULT_AUTO_TRUNCATE_THRESHOLD,
    DEFAULT_TRUNCATE_HEAD_LINES,
    DEFAULT_TRUNCATE_TAIL_LINES,
)


class ContextManager:
    """Manages conversation context - message IDs, pruning, distilling, and truncation"""
    
    def __init__(self, config):
        self.config = config
        self.console = Console()
        self._next_id = 1
    
    def reset(self):
        """Reset the ID counter (used when conversation is cleared)"""
        self._next_id = 1
    
    def assign_metadata(self, message, label=None):
        """Assign context management metadata to a message dict"""
        message["_msg_id"] = self._next_id
        self._next_id += 1
        message["_prunable"] = True
        message["_state"] = "normal"  # normal | truncated | distilled | pruned
        message["_original_content"] = None
        message["_label"] = label or self._extract_label(message.get("content", ""))
    
    def _extract_label(self, content):
        """Extract a short human-readable label from a SYSTEM MESSAGE"""
        if not content:
            return "System message"
        
        # Try to extract command name
        cmd_match = re.search(r"Command executed:\s*(.+?)(?:\n|$)", content)
        if cmd_match:
            cmd = cmd_match.group(1).strip()
            if len(cmd) > 60:
                cmd = cmd[:57] + "..."
            return f"Command output: {cmd}"
        
        # Try to extract web search query
        search_match = re.search(r"Web search executed for:\s*(.+?)(?:\n|$)", content)
        if search_match:
            query = search_match.group(1).strip()
            if len(query) > 60:
                query = query[:57] + "..."
            return f"Web search: {query}"
        
        # Try to extract declined command
        decline_match = re.search(r"User declined to run the command:\s*(.+?)(?:\n|$)", content)
        if decline_match:
            cmd = decline_match.group(1).strip()
            if len(cmd) > 50:
                cmd = cmd[:47] + "..."
            return f"User declined: {cmd}"
        
        # Pattern-based labels
        if "Task completed" in content:
            return "Task completion"
        if "Task failed" in content or "task status check failed" in content:
            return "Task failure"
        if "empty response" in content.lower():
            return "Empty response handling"
        if "not yet complete" in content.lower():
            return "Task continuation"
        if "multiple" in content.lower() and ("commands" in content.lower() or "actions" in content.lower()):
            return "Multiple actions error"
        if "Web search failed" in content:
            search_match = re.search(r"failed for query:\s*(.+?)(?:\n|$)", content)
            if search_match:
                query = search_match.group(1).strip()
                if len(query) > 50:
                    query = query[:47] + "..."
                return f"Web search failed: {query}"
            return "Web search failed"
        if "Context management" in content:
            return "Context management confirmation"
        
        # Fallback
        preview = content[:50].replace('\n', ' ').strip()
        return f"System message: {preview}"
    
    def estimate_tokens(self, content):
        """Rough token estimation (chars / 4)"""
        if not content:
            return 0
        return len(content) // 4
    
    def get_total_tokens(self, payload):
        """Estimate total tokens in the payload"""
        return sum(self.estimate_tokens(msg.get("content", "")) for msg in payload)
    
    def get_prunable_list(self, payload):
        """Generate the <prunable-messages> block for injection into the system prompt"""
        lines = []
        for msg in payload:
            if not msg.get("_prunable"):
                continue
            state = msg.get("_state", "normal")
            if state == "pruned":
                continue  # Already pruned, nothing left to manage
            
            msg_id = msg["_msg_id"]
            label = msg.get("_label", "System message")
            tokens = self.estimate_tokens(msg.get("content", ""))
            
            state_info = ""
            if state == "truncated":
                state_info = " [truncated, can untruncate]"
            elif state == "distilled":
                state_info = " [already distilled]"
            
            lines.append(f"{msg_id}: {label}{state_info} (~{tokens} tokens)")
        
        if not lines:
            return ""
        
        total_tokens = self.get_total_tokens(payload)
        header = f"Total estimated context: ~{total_tokens} tokens"
        return f"<prunable-messages>\n{header}\n" + "\n".join(lines) + "\n</prunable-messages>"
    
    def prune(self, payload, msg_ids):
        """Prune messages by ID - replace content with short marker"""
        pruned_info = []
        for msg in payload:
            msg_id = msg.get("_msg_id")
            if msg_id is not None and msg_id in msg_ids and msg.get("_prunable"):
                state = msg.get("_state", "normal")
                if state == "pruned":
                    continue  # Already pruned
                
                label = msg.get("_label", "System message")
                # Store original content if not already stored
                if msg.get("_original_content") is None:
                    msg["_original_content"] = msg["content"]
                msg["content"] = f"[PRUNED] {label}"
                msg["_state"] = "pruned"
                pruned_info.append((msg_id, label))
        
        return pruned_info
    
    def distill(self, payload, msg_id, summary):
        """Distill a message - replace content with AI's summary"""
        for msg in payload:
            if msg.get("_msg_id") == msg_id and msg.get("_prunable"):
                state = msg.get("_state", "normal")
                if state == "pruned":
                    return None  # Can't distill a pruned message
                
                label = msg.get("_label", "System message")
                # Store original content if not already stored
                if msg.get("_original_content") is None:
                    msg["_original_content"] = msg["content"]
                msg["content"] = f"[DISTILLED] {label}\nSummary: {summary}"
                msg["_state"] = "distilled"
                return (msg_id, label)
        
        return None
    
    def auto_truncate(self, content, threshold=None, head_lines=None, tail_lines=None):
        """
        Auto-truncate long output.
        Returns (content_to_use, was_truncated, original_content).
        original_content is None if not truncated.
        """
        if threshold is None:
            threshold = DEFAULT_AUTO_TRUNCATE_THRESHOLD
        if head_lines is None:
            head_lines = DEFAULT_TRUNCATE_HEAD_LINES
        if tail_lines is None:
            tail_lines = DEFAULT_TRUNCATE_TAIL_LINES
        
        if not content or len(content) <= threshold:
            return content, False, None
        
        lines = content.split('\n')
        total_lines = len(lines)
        
        if total_lines <= (head_lines + tail_lines):
            return content, False, None
        
        head = lines[:head_lines]
        tail = lines[-tail_lines:]
        omitted = total_lines - head_lines - tail_lines
        
        truncated = '\n'.join(head)
        truncated += f"\n\n... [{omitted} lines omitted - use context_untruncate to view full output] ...\n\n"
        truncated += '\n'.join(tail)
        
        return truncated, True, content
    
    def untruncate(self, payload, msg_id):
        """Restore full content for a truncated message"""
        for msg in payload:
            if msg.get("_msg_id") == msg_id and msg.get("_prunable"):
                if msg.get("_state") != "truncated":
                    return None  # Not truncated
                
                original = msg.get("_original_content")
                if not original:
                    return None
                
                label = msg.get("_label", "System message")
                msg["content"] = original
                msg["_original_content"] = None
                msg["_state"] = "normal"
                return (msg_id, label)
        
        return None
    
    def prepare_messages_for_api(self, payload):
        """Strip all _* metadata fields and return clean messages for the API"""
        clean = []
        for msg in payload:
            clean.append({"role": msg["role"], "content": msg["content"]})
        return clean
    
    def restore_ids_from_saved(self, payload):
        """After loading a saved conversation, restore the ID counter from existing message IDs"""
        max_id = 0
        for msg in payload:
            msg_id = msg.get("_msg_id", 0)
            if msg_id > max_id:
                max_id = msg_id
        self._next_id = max_id + 1
