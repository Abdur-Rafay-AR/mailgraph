"""Multi-resolution graph aggregation service for Cytoscape.js network visualization."""

import sqlite3
from typing import Dict, Any, List, Optional
from backend.app.db.database import Database

CATEGORY_COLORS: Dict[str, str] = {
    "important": "#ef4444",
    "personal": "#10b981",
    "work": "#3b82f6",
    "university": "#8b5cf6",
    "transactional": "#06b6d4",
    "receipt_invoice": "#f59e0b",
    "security": "#dc2626",
    "calendar": "#6366f1",
    "notification": "#64748b",
    "newsletter": "#14b8a6",
    "promotional": "#ec4899",
    "social": "#f97316",
    "automated_report": "#475569",
    "cold_outreach": "#78716c",
    "unknown": "#94a3b8"
}

class GraphService:
    """Computes aggregated graph topologies and node metrics."""

    def __init__(self, db: Database):
        self.db = db

    def get_graph(
        self,
        account_id: Optional[int] = None,
        level: str = "domain",
        selected_domain: Optional[str] = None,
        selected_sender_id: Optional[int] = None,
        category: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate Cytoscape.js compatible graph data structure."""
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        
        with self.db.connect() as conn:
            cursor = conn.cursor()
            
            where_conditions = [
                "1=1",
                "(m.folder_id IS NULL OR m.folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam')))"
            ]
            params: List[Any] = []
            
            if account_id:
                where_conditions.append("m.account_id = ?")
                params.append(account_id)
            if category:
                where_conditions.append("c.name = ?")
                params.append(category)
            if start_date:
                where_conditions.append("m.received_at >= ?")
                params.append(start_date)
            if end_date:
                where_conditions.append("m.received_at <= ?")
                params.append(end_date)
                
            where_clause = " AND ".join(where_conditions)
            
            if level == "domain":
                self._build_domain_graph(cursor, where_clause, params, nodes, edges)
            elif level == "sender":
                self._build_sender_graph(cursor, where_clause, params, selected_domain, nodes, edges)
            elif level == "thread":
                self._build_thread_graph(cursor, where_clause, params, selected_sender_id, nodes, edges)
                
        return {
            "elements": {
                "nodes": nodes,
                "edges": edges
            }
        }

    def _build_domain_graph(
        self,
        cursor: sqlite3.Cursor,
        where_clause: str,
        params: List[Any],
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> None:
        query = f"""
            SELECT 
                s.domain,
                COUNT(m.id) as message_count,
                COUNT(DISTINCT s.id) as sender_count,
                COALESCE(SUM(m.size_bytes), 0) as total_bytes,
                COALESCE(SUM(CASE WHEN m.is_read = 0 THEN 1 ELSE 0 END), 0) as unread_count,
                MIN(m.received_at) as first_seen,
                MAX(m.received_at) as last_seen,
                COALESCE(c.name, 'unknown') as dominant_category
            FROM senders s
            JOIN messages m ON s.id = m.sender_id
            LEFT JOIN message_categories mc ON m.id = mc.message_id
            LEFT JOIN categories c ON mc.category_id = c.id
            WHERE {where_clause}
            GROUP BY s.domain
            ORDER BY message_count DESC
            LIMIT 100;
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Central Hub Node representing Mailbox
        nodes.append({
            "data": {
                "id": "hub:mailbox",
                "label": "Mailbox Hub",
                "node_type": "hub",
                "message_count": sum(r[1] for r in rows),
                "total_bytes": sum(r[3] for r in rows),
                "unread_count": sum(r[4] for r in rows),
                "color": "#38bdf8"
            }
        })
        
        for r in rows:
            domain, count, senders_cnt, bytes_cnt, unread_cnt, first_seen, last_seen, cat = r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]
            domain_id = f"domain:{domain}"
            color = CATEGORY_COLORS.get(cat, "#94a3b8")
            
            nodes.append({
                "data": {
                    "id": domain_id,
                    "label": domain,
                    "node_type": "domain",
                    "domain": domain,
                    "message_count": count,
                    "sender_count": senders_cnt,
                    "total_bytes": bytes_cnt,
                    "unread_count": unread_cnt,
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                    "category": cat,
                    "color": color
                }
            })
            
            # Edge between Mailbox Hub and Domain
            edges.append({
                "data": {
                    "id": f"edge:hub->{domain_id}",
                    "source": "hub:mailbox",
                    "target": domain_id,
                    "edge_type": "belongs_to_account",
                    "weight": count
                }
            })

    def _build_sender_graph(
        self,
        cursor: sqlite3.Cursor,
        where_clause: str,
        params: List[Any],
        selected_domain: Optional[str],
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> None:
        domain_filter = " AND s.domain = ?" if selected_domain else ""
        query_params = list(params)
        if selected_domain:
            query_params.append(selected_domain)
            
        query = f"""
            SELECT 
                s.id,
                s.normalized_address,
                s.display_name,
                s.domain,
                s.is_protected,
                COUNT(m.id) as message_count,
                COALESCE(SUM(m.size_bytes), 0) as total_bytes,
                COALESCE(SUM(CASE WHEN m.is_read = 0 THEN 1 ELSE 0 END), 0) as unread_count,
                MIN(m.received_at) as first_seen,
                MAX(m.received_at) as last_seen,
                COALESCE(c.name, 'unknown') as dominant_category
            FROM senders s
            JOIN messages m ON s.id = m.sender_id
            LEFT JOIN message_categories mc ON m.id = mc.message_id
            LEFT JOIN categories c ON mc.category_id = c.id
            WHERE {where_clause} {domain_filter}
            GROUP BY s.id
            ORDER BY message_count DESC
            LIMIT 150;
        """
        cursor.execute(query, query_params)
        rows = cursor.fetchall()
        
        domains_seen = set()
        for r in rows:
            sid, addr, name, dom, is_prot, count, bytes_cnt, unread_cnt, first_seen, last_seen, cat = r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10]
            dom_id = f"domain:{dom}"
            if dom not in domains_seen:
                domains_seen.add(dom)
                nodes.append({
                    "data": {
                        "id": dom_id,
                        "label": dom,
                        "node_type": "domain",
                        "domain": dom,
                        "color": "#60a5fa"
                    }
                })
                
            sender_id = f"sender:{sid}"
            display = name or addr.split("@")[0]
            color = CATEGORY_COLORS.get(cat, "#94a3b8")
            
            nodes.append({
                "data": {
                    "id": sender_id,
                    "label": display,
                    "node_type": "sender",
                    "sender_id": sid,
                    "address": addr,
                    "display_name": name,
                    "domain": dom,
                    "is_protected": bool(is_prot),
                    "message_count": count,
                    "total_bytes": bytes_cnt,
                    "unread_count": unread_cnt,
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                    "category": cat,
                    "color": color
                }
            })
            
            edges.append({
                "data": {
                    "id": f"edge:{dom_id}->{sender_id}",
                    "source": dom_id,
                    "target": sender_id,
                    "edge_type": "belongs_to_domain",
                    "weight": count
                }
            })

    def _build_thread_graph(
        self,
        cursor: sqlite3.Cursor,
        where_clause: str,
        params: List[Any],
        selected_sender_id: Optional[int],
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> None:
        sender_filter = " AND m.sender_id = ?" if selected_sender_id else ""
        query_params = list(params)
        if selected_sender_id:
            query_params.append(selected_sender_id)
            
        query = f"""
            SELECT 
                t.id,
                t.subject_normalized,
                t.message_count,
                t.first_message_at,
                t.last_message_at,
                m.sender_id,
                s.normalized_address
            FROM threads t
            JOIN messages m ON t.id = m.thread_id
            JOIN senders s ON m.sender_id = s.id
            WHERE {where_clause} {sender_filter}
            GROUP BY t.id
            ORDER BY t.message_count DESC
            LIMIT 80;
        """
        cursor.execute(query, query_params)
        rows = cursor.fetchall()
        
        senders_seen = set()
        for r in rows:
            tid, subj, count, f_at, l_at, sid, s_addr = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
            s_node_id = f"sender:{sid}"
            if sid not in senders_seen:
                senders_seen.add(sid)
                nodes.append({
                    "data": {
                        "id": s_node_id,
                        "label": s_addr,
                        "node_type": "sender",
                        "sender_id": sid,
                        "color": "#38bdf8"
                    }
                })
                
            t_node_id = f"thread:{tid}"
            nodes.append({
                "data": {
                    "id": t_node_id,
                    "label": subj or "(Conversation)",
                    "node_type": "thread",
                    "thread_id": tid,
                    "message_count": count,
                    "first_message_at": f_at,
                    "last_message_at": l_at,
                    "color": "#a855f7"
                }
            })
            
            edges.append({
                "data": {
                    "id": f"edge:{s_node_id}->{t_node_id}",
                    "source": s_node_id,
                    "target": t_node_id,
                    "edge_type": "participates_in_thread",
                    "weight": count
                }
            })
