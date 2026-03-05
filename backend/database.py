# -*- coding: utf-8 -*-
"""
database.py — SQLAlchemy 数据库连接与会话管理
使用 SQLite 作为本地开发数据库，连接字符串可通过 .env 配置替换为生产数据库。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool

# SQLite 本地数据库文件，存储在项目根目录
SQLALCHEMY_DATABASE_URL = "sqlite:///./smartdiag.db"

# StaticPool 避免多线程下 SQLite "check_same_thread" 问题
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# 会话工厂：每次请求创建独立会话，autocommit=False 保证事务安全
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """所有 ORM 模型的公共基类，通过继承此类即可纳入元数据管理"""
    # 允许旧式 Column() 写法与 Python 类型注解共存（SQLAlchemy 2.0 兼容）
    __allow_unmapped__ = True


def get_db():
    """
    FastAPI 依赖注入函数，提供请求级别的数据库会话。
    使用 try/finally 确保无论请求是否抛出异常，会话都会被正确关闭。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
