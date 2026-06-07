from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DashScope API
    dashscope_api_key: str = ""

    # LLM
    llm_model: str = "qwen3-max"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_timeout: int = 120
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.1

    # Embedding
    embedding_model: str = "bge-large-zh-v1.5"
    embedding_base_url: str = "http://127.0.0.1:8001/v1"
    embedding_api_key: str = "placeholder"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 10
    embedding_max_input_length: int = 800
    embedding_query_prefix: str = "为这个句子生成表示以用于检索相关文章："

    # PostgreSQL (application database)
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = ""
    postgres_db: str = "chat_db"

    # Milvus
    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530

    # Neo4j
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # Redis
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # Auth
    auth_enabled: bool = True

    # Query rewrite
    query_rewrite_enabled: bool = False
    query_rewrite_count: int = 3

    # Reranker
    rerank_api_url: str = "http://127.0.0.1:8001/v1/rerank"
    rerank_api_key: str = ""
    rerank_model: str = "bge-reranker-large"
    rerank_fetch_multiplier: int = 1

    # Encryption
    encryption_key: str = ""

    # Metadata sync
    metadata_sync_interval_hours: int = 24

    # Learning
    learning_l2_max_concurrency: int = 5
    learning_job_timeout_minutes: int = 60

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
