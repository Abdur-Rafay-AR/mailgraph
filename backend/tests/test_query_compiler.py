import pytest
from backend.app.search.query_compiler import QueryCompiler, QueryCondition, QueryAST

def test_compile_basic_and_condition():
    compiler = QueryCompiler()
    ast = QueryAST(
        account_ids=[1],
        all=[
            QueryCondition(field="sender_domain", op="eq", value="acme-corp.com"),
            QueryCondition(field="is_read", op="eq", value=True)
        ]
    )
    sql, params = compiler.compile_sql(ast)
    assert "messages.account_id IN (?)" in sql
    assert "messages.is_read = ?" in sql
    assert 1 in params
    assert 1 in params  # True as int 1

def test_sql_injection_defense():
    compiler = QueryCompiler()
    ast = QueryAST(
        all=[
            QueryCondition(field="sender_domain", op="eq", value="' OR '1'='1")
        ]
    )
    sql, params = compiler.compile_sql(ast)
    # The literal injection string must be passed strictly as a parameter, not raw SQL
    assert "' OR '1'='1" in params
    assert "' OR '1'='1" not in sql

def test_compile_protection_exclusions():
    compiler = QueryCompiler()
    ast = QueryAST(
        account_ids=[1],
        all=[QueryCondition(field="sender_domain", op="eq", value="stripe.com")],
        exclude_protected=True
    )
    sql, params = compiler.compile_sql(ast)
    assert "protection_rules" in sql
    assert "is_protected = 1" in sql

def test_compile_fts_match():
    compiler = QueryCompiler()
    ast = QueryAST(
        search_term="Quarterly Roadmap"
    )
    sql, params = compiler.compile_sql(ast)
    assert "messages_fts" in sql
    assert "MATCH ?" in sql
    assert '"Quarterly Roadmap"*' in params or 'Quarterly Roadmap' in params
