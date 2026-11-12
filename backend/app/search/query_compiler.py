"""Secure, parameterized Query AST Compiler for MailGraph."""

import re
from dataclasses import dataclass, field
from typing import List, Any, Tuple, Optional, Dict

ALLOWED_FIELDS: Dict[str, str] = {
    "sender_address": "messages.sender_address",
    "sender_domain": "senders.domain",
    "received_at": "messages.received_at",
    "sent_at": "messages.sent_at",
    "is_read": "messages.is_read",
    "is_starred": "messages.is_starred",
    "is_important": "messages.is_important",
    "has_attachments": "messages.has_attachments",
    "size_bytes": "messages.size_bytes",
    "folder_id": "messages.folder_id",
    "thread_id": "messages.thread_id",
    "category": "categories.name",
    "subject": "messages.subject"
}

ALLOWED_OPS = {"eq", "neq", "contains", "before", "after", "gt", "lt", "gte", "lte", "in"}

@dataclass
class QueryCondition:
    field: str
    op: str
    value: Any

@dataclass
class QueryAST:
    version: int = 1
    account_ids: Optional[List[int]] = None
    all: List[QueryCondition] = field(default_factory=list)
    any: List[QueryCondition] = field(default_factory=list)
    none: List[QueryCondition] = field(default_factory=list)
    search_term: Optional[str] = None
    exclude_protected: bool = True

class QueryCompiler:
    """Compiles validated QueryAST instances into parameterized SQL clauses."""

    def compile_sql(self, ast: QueryAST, count_only: bool = False) -> Tuple[str, List[Any]]:
        """
        Returns (sql_query, params_list).
        Guarantees parameterized query execution with zero SQL injection risk.
        """
        where_clauses: List[str] = []
        params: List[Any] = []
        
        # 1. Account isolation
        if ast.account_ids:
            placeholders = ", ".join("?" for _ in ast.account_ids)
            where_clauses.append(f"messages.account_id IN ({placeholders})")
            params.extend(ast.account_ids)
            
        # 2. Text Search with SQLite FTS5
        if ast.search_term and ast.search_term.strip():
            term = ast.search_term.strip()
            # Clean special FTS characters to avoid query syntax errors
            clean_term = re.sub(r'["\*\^]', '', term)
            where_clauses.append("messages.id IN (SELECT message_id FROM messages_fts WHERE messages_fts MATCH ?)")
            params.append(f'"{clean_term}"*')
            
        # 3. AND conditions (all)
        if ast.all:
            and_clauses = []
            for cond in ast.all:
                clause, p = self._compile_condition(cond)
                and_clauses.append(clause)
                params.extend(p)
            where_clauses.append(f"({' AND '.join(and_clauses)})")
            
        # 4. OR conditions (any)
        if ast.any:
            or_clauses = []
            for cond in ast.any:
                clause, p = self._compile_condition(cond)
                or_clauses.append(clause)
                params.extend(p)
            where_clauses.append(f"({' OR '.join(or_clauses)})")
            
        # 5. NOT conditions (none)
        if ast.none:
            not_clauses = []
            for cond in ast.none:
                clause, p = self._compile_condition(cond)
                not_clauses.append(f"NOT ({clause})")
                params.extend(p)
            where_clauses.append(f"({' AND '.join(not_clauses)})")
            
        # 6. Protection exclusions
        if ast.exclude_protected:
            prot_clause = """(
                (messages.sender_id IS NULL OR messages.sender_id NOT IN (SELECT id FROM senders WHERE is_protected = 1))
                AND messages.sender_address NOT IN (SELECT rule_value FROM protection_rules WHERE rule_type = 'sender' AND enabled = 1)
                AND NOT EXISTS (
                    SELECT 1 FROM protection_rules pr
                    WHERE pr.rule_type = 'domain' AND pr.enabled = 1
                    AND (messages.sender_address LIKE '%@' || pr.rule_value OR messages.sender_address LIKE '%.' || pr.rule_value)
                )
                AND messages.is_starred = 0
                AND messages.is_important = 0
            )"""
            where_clauses.append(prot_clause)
            
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Build base SQL with safe LEFT JOINs
        if count_only:
            sql = f"""
                SELECT COUNT(DISTINCT messages.id)
                FROM messages
                LEFT JOIN senders ON messages.sender_id = senders.id
                LEFT JOIN message_categories ON messages.id = message_categories.message_id
                LEFT JOIN categories ON message_categories.category_id = categories.id
                WHERE {where_sql}
            """
        else:
            sql = f"""
                SELECT DISTINCT messages.id, messages.account_id, messages.provider_message_id,
                       messages.folder_id, messages.thread_id, messages.subject,
                       messages.sender_name, messages.sender_address, messages.received_at,
                       messages.is_read, messages.is_starred, messages.is_important,
                       messages.has_attachments, messages.size_bytes, messages.snippet,
                       senders.domain as sender_domain,
                       categories.name as category_name, categories.color as category_color
                FROM messages
                LEFT JOIN senders ON messages.sender_id = senders.id
                LEFT JOIN message_categories ON messages.id = message_categories.message_id
                LEFT JOIN categories ON message_categories.category_id = categories.id
                WHERE {where_sql}
            """
            
        return sql, params

    def _compile_condition(self, cond: QueryCondition) -> Tuple[str, List[Any]]:
        if cond.field not in ALLOWED_FIELDS:
            raise ValueError(f"Disallowed field in query AST: {cond.field}")
        if cond.op not in ALLOWED_OPS:
            raise ValueError(f"Disallowed operator in query AST: {cond.op}")
            
        col = ALLOWED_FIELDS[cond.field]
        op = cond.op
        val = cond.value
        
        if op == "eq":
            if isinstance(val, bool):
                return f"{col} = ?", [1 if val else 0]
            return f"{col} = ?", [val]
        elif op == "neq":
            if isinstance(val, bool):
                return f"{col} != ?", [1 if val else 0]
            return f"{col} != ?", [val]
        elif op == "contains":
            return f"{col} LIKE ?", [f"%{val}%"]
        elif op == "before":
            return f"{col} < ?", [val]
        elif op == "after":
            return f"{col} > ?", [val]
        elif op in ("gt", "gte", "lt", "lte"):
            sql_op = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
            return f"{col} {sql_op} ?", [val]
        elif op == "in":
            if not isinstance(val, (list, tuple)) or not val:
                return "1=0", []
            placeholders = ", ".join("?" for _ in val)
            return f"{col} IN ({placeholders})", list(val)
            
        raise ValueError(f"Unhandled condition operator: {op}")
