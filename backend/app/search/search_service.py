"""High performance search execution, pagination, and CSV export."""

import csv
import io
import sqlite3
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from backend.app.db.database import Database
from backend.app.search.query_compiler import QueryCompiler, QueryAST

@dataclass
class SearchResult:
    total_count: int
    page: int
    page_size: int
    items: List[Dict[str, Any]]
    facets: Dict[str, Any]

class SearchService:
    """Executes validated searches and computes mailbox facets."""

    def __init__(self, db: Database):
        self.db = db
        self.compiler = QueryCompiler()

    def search(
        self,
        ast: QueryAST,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "received_at",
        sort_dir: str = "DESC"
    ) -> SearchResult:
        """Execute paginated search query and return result with metadata."""
        valid_sort_cols = {
            "received_at": "messages.received_at",
            "size_bytes": "messages.size_bytes",
            "subject": "messages.subject",
            "sender_address": "messages.sender_address"
        }
        order_col = valid_sort_cols.get(sort_by, "messages.received_at")
        order_dir = "ASC" if sort_dir.upper() == "ASC" else "DESC"
        
        offset = max(0, (page - 1) * page_size)
        
        with self.db.connect() as conn:
            cursor = conn.cursor()
            
            # 1. Total count
            count_sql, count_params = self.compiler.compile_sql(ast, count_only=True)
            cursor.execute(count_sql, count_params)
            total_count = cursor.fetchone()[0]
            
            # 2. Paginated results
            data_sql, data_params = self.compiler.compile_sql(ast, count_only=False)
            data_sql += f" ORDER BY {order_col} {order_dir} LIMIT ? OFFSET ?;"
            data_params.extend([page_size, offset])
            
            cursor.execute(data_sql, data_params)
            rows = cursor.fetchall()
            
            items = []
            for r in rows:
                items.append({
                    "id": r["id"],
                    "account_id": r["account_id"],
                    "provider_message_id": r["provider_message_id"],
                    "folder_id": r["folder_id"],
                    "thread_id": r["thread_id"],
                    "subject": r["subject"],
                    "sender_name": r["sender_name"],
                    "sender_address": r["sender_address"],
                    "sender_domain": r["sender_domain"],
                    "received_at": r["received_at"],
                    "is_read": bool(r["is_read"]),
                    "is_starred": bool(r["is_starred"]),
                    "is_important": bool(r["is_important"]),
                    "has_attachments": bool(r["has_attachments"]),
                    "size_bytes": r["size_bytes"],
                    "snippet": r["snippet"],
                    "category": r["category_name"],
                    "category_color": r["category_color"]
                })
                
            # 3. Facets summary
            facets = self._compute_facets(conn, ast)
            
            return SearchResult(
                total_count=total_count,
                page=page,
                page_size=page_size,
                items=items,
                facets=facets
            )

    def _compute_facets(self, conn: sqlite3.Connection, ast: QueryAST) -> Dict[str, Any]:
        """Compute aggregate facets (category distribution, total bytes)."""
        cursor = conn.cursor()
        base_sql, params = self.compiler.compile_sql(ast, count_only=False)
        
        facet_sql = f"""
            WITH matched AS ({base_sql})
            SELECT 
                COUNT(*) as count,
                COALESCE(SUM(size_bytes), 0) as total_size,
                COALESCE(category_name, 'unknown') as cat,
                COUNT(DISTINCT sender_address) as distinct_senders
            FROM matched
            GROUP BY cat;
        """
        cursor.execute(facet_sql, params)
        category_breakdown = {}
        total_size = 0
        total_matched = 0
        
        for row in cursor.fetchall():
            count, size, cat, _ = row[0], row[1], row[2], row[3]
            category_breakdown[cat] = count
            total_size += size
            total_matched += count
            
        return {
            "total_matched": total_matched,
            "total_bytes": total_size,
            "categories": category_breakdown
        }

    def export_csv(self, ast: QueryAST, max_records: int = 10000) -> str:
        """Export search results to a CSV formatted string."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            sql, params = self.compiler.compile_sql(ast, count_only=False)
            sql += " ORDER BY messages.received_at DESC LIMIT ?;"
            params.append(max_records)
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Message ID", "Date", "Sender Name", "Sender Address",
                "Domain", "Subject", "Category", "Read", "Starred",
                "Has Attachments", "Size (Bytes)"
            ])
            for r in rows:
                writer.writerow([
                    r["id"], r["received_at"], r["sender_name"], r["sender_address"],
                    r["sender_domain"], r["subject"], r["category_name"],
                    1 if r["is_read"] else 0, 1 if r["is_starred"] else 0,
                    1 if r["has_attachments"] else 0, r["size_bytes"]
                ])
            return output.getvalue()
